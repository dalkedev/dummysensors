from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from dummysensors.anomalies import Anomaly, AnomalyInjector


@pytest.mark.parametrize(("t_s", "expected"), [(0.0, 10.0), (2.0, 13.0), (3.0, 13.0), (4.0, 10.0)])
def test_spike_uses_half_open_time_interval(t_s, expected):
    injector = AnomalyInjector([Anomaly("spike", 2.0, 4.0, offset=3.0)])
    assert injector.apply(10.0, t_s, "A", "temp-1") == expected


@pytest.mark.parametrize(("t_s", "expected"), [(2.0, 10.0), (3.5, 7.0), (5.0, 10.0)])
def test_negative_drift_is_relative_to_window_start(t_s, expected):
    injector = AnomalyInjector([Anomaly("drift", 2.0, 5.0, rate_per_s=-2.0)])
    assert injector.apply(10.0, t_s, "A", "temp-1") == expected


@pytest.mark.parametrize(
    ("device_id", "sensor_id", "actual_device", "actual_sensor", "expected"),
    [
        (None, None, "A", "temp-1", 12.0),
        ("A", None, "A", "humidity-1", 12.0),
        (None, "temp-1", "B", "temp-1", 12.0),
        ("A", "temp-1", "A", "temp-1", 12.0),
        ("A", None, "AA", "temp-1", 10.0),
        (None, "temp-1", "A", "temp-10", 10.0),
        ("A", "temp-1", "B", "temp-1", 10.0),
        ("A", "temp-1", "A", "temp-2", 10.0),
    ],
)
def test_targets_use_wildcards_or_exact_ids(
    device_id, sensor_id, actual_device, actual_sensor, expected
):
    injector = AnomalyInjector(
        [Anomaly("spike", 0, 5, device_id=device_id, sensor_id=sensor_id, offset=2)]
    )
    assert injector.apply(10, 1, actual_device, actual_sensor) == expected


def test_overlapping_spikes_and_drifts_sum():
    injector = AnomalyInjector(
        [
            Anomaly("spike", 0, 5, offset=4),
            Anomaly("spike", 0, 5, offset=-1),
            Anomaly("drift", 1, 5, rate_per_s=2),
            Anomaly("drift", 2, 5, rate_per_s=-3),
        ]
    )
    assert injector.apply(10, 3, "A", "temp-1") == 14


@pytest.mark.parametrize("dropout_first", [False, True])
def test_matching_dropout_takes_precedence_over_offsets(dropout_first):
    anomalies = [Anomaly("spike", 0, 5, offset=100), Anomaly("dropout", 1, 3)]
    if dropout_first:
        anomalies.reverse()
    injector = AnomalyInjector(anomalies)
    assert injector.apply(10, 1, "A", "temp-1") is None
    assert injector.apply(10, 3, "A", "temp-1") == 110


def test_unmatched_dropout_does_not_remove_a_value():
    injector = AnomalyInjector([Anomaly("dropout", 0, 5, device_id="B")])
    assert injector.apply(10, 1, "A", "temp-1") == 10


def test_default_and_empty_config_are_identity_injectors():
    assert AnomalyInjector().apply(-4.5, 0, "A", "temp-1") == -4.5
    assert AnomalyInjector.from_config([]).apply(10, 1, "A", "temp-1") == 10


def test_anomaly_is_immutable_and_injector_copies_its_input():
    anomaly = Anomaly("spike", 0, 5, offset=3)
    anomalies = [anomaly]
    injector = AnomalyInjector(anomalies)
    with pytest.raises(FrozenInstanceError):
        anomaly.offset = 99
    anomalies.clear()
    assert injector.apply(10, 1, "A", "temp-1") == 13


def test_injector_accepts_an_iterable():
    injector = AnomalyInjector(Anomaly("spike", 0, 5, offset=n) for n in (1, 2))
    assert injector.apply(10, 1, "A", "temp-1") == 13


def test_from_config_parses_all_fields_without_mutating_input():
    entries = [
        {
            "kind": "drift",
            "start_s": 1,
            "end_s": 5,
            "device_id": "A",
            "sensor_id": "temp-1",
            "offset": -9,
            "rate_per_s": -2,
        },
        {"kind": "spike", "start_s": 0, "end_s": 3, "offset": 4},
    ]
    original = deepcopy(entries)
    injector = AnomalyInjector.from_config(entries)
    assert entries == original
    entries[0]["rate_per_s"] = 50
    entries.clear()
    assert injector.apply(10, 2, "A", "temp-1") == 12


@pytest.mark.parametrize("kind", ["unknown", "Spike", "", None, 1, [], {}])
def test_rejects_invalid_kinds(kind):
    with pytest.raises(ValueError, match="kind"):
        Anomaly(kind, 0, 1)


@pytest.mark.parametrize("field", ["start_s", "end_s", "offset", "rate_per_s"])
@pytest.mark.parametrize(
    "bad", [True, False, "1", None, [], float("nan"), float("inf"), -float("inf")]
)
def test_rejects_invalid_numeric_fields(field, bad):
    fields = {"kind": "spike", "start_s": 0, "end_s": 5, field: bad}
    with pytest.raises(ValueError, match=field):
        Anomaly(**fields)


@pytest.mark.parametrize(("start_s", "end_s"), [(-1, 2), (0, -1), (1, 1), (2, 1)])
def test_rejects_invalid_time_windows(start_s, end_s):
    with pytest.raises(ValueError, match="start_s|end_s"):
        Anomaly("spike", start_s, end_s)


@pytest.mark.parametrize("field", ["device_id", "sensor_id"])
@pytest.mark.parametrize("bad", ["", 0, False, [], {}])
def test_rejects_invalid_target_ids(field, bad):
    with pytest.raises(ValueError, match=field):
        Anomaly("spike", 0, 1, **{field: bad})


@pytest.mark.parametrize("entries", [None, {}, "", (), [None], [[]], ["spike"]])
def test_from_config_rejects_invalid_container_types(entries):
    with pytest.raises(ValueError, match="anomal|entry|list|mapping"):
        AnomalyInjector.from_config(entries)


@pytest.mark.parametrize(
    "entry",
    [
        {},
        {"kind": "spike", "start_s": 0},
        {"kind": "spike", "end_s": 1},
        {"start_s": 0, "end_s": 1},
        {"kind": "spike", "start_s": 0, "end_s": 1, "extra": 1},
        {"kind": "spike", "start_s": 0, "end_s": 1, 42: "bad key"},
    ],
)
def test_from_config_rejects_missing_and_unknown_fields(entry):
    with pytest.raises(ValueError, match="entry.*0"):
        AnomalyInjector.from_config([entry])


@pytest.mark.parametrize("field", ["start_s", "end_s", "offset", "rate_per_s"])
@pytest.mark.parametrize("bad", [True, "1", float("nan"), float("inf")])
def test_from_config_validates_numeric_fields_with_entry_context(field, bad):
    entry = {"kind": "spike", "start_s": 0, "end_s": 5, field: bad}
    with pytest.raises(ValueError, match=f"entry.*0.*{field}"):
        AnomalyInjector.from_config([entry])


@pytest.mark.parametrize("anomalies", [None, 1, [None], [{}], ["spike"]])
def test_injector_rejects_malformed_anomalies_before_apply(anomalies):
    with pytest.raises(ValueError, match="anomal"):
        AnomalyInjector(anomalies)


@pytest.mark.parametrize("field", ["value", "t_s"])
@pytest.mark.parametrize("bad", [True, "1", None, float("nan"), float("inf"), -float("inf")])
def test_apply_rejects_invalid_numeric_inputs(field, bad):
    args = {"value": 10, "t_s": 0, "device_id": "A", "sensor_id": "temp-1", field: bad}
    with pytest.raises(ValueError, match=field):
        AnomalyInjector().apply(**args)


def test_apply_rejects_negative_time():
    with pytest.raises(ValueError, match="t_s"):
        AnomalyInjector().apply(10, -1, "A", "temp-1")


@pytest.mark.parametrize("field", ["device_id", "sensor_id"])
@pytest.mark.parametrize("bad", [None, "", False])
def test_apply_requires_nonempty_actual_ids(field, bad):
    args = {"value": 10, "t_s": 0, "device_id": "A", "sensor_id": "temp-1", field: bad}
    with pytest.raises(ValueError, match=field):
        AnomalyInjector().apply(**args)


@pytest.mark.parametrize(
    "anomalies,value,t_s",
    [
        ([Anomaly("spike", 0, 5, offset=1e308)] * 2, 10.0, 1),
        ([Anomaly("spike", 0, 5, offset=1e308)], 1e308, 1),
        ([Anomaly("drift", 0, 5, rate_per_s=1e308)], 10.0, 2),
    ],
)
def test_fault_arithmetic_overflow_is_rejected_before_emission(anomalies, value, t_s):
    with pytest.raises(ValueError, match="adjusted value.*finite"):
        AnomalyInjector(anomalies).apply(value, t_s, "A", "temp-0")


@pytest.mark.parametrize("dropout_first", [True, False])
def test_dropout_wins_even_when_an_offset_would_overflow(dropout_first):
    anomalies = [Anomaly("drift", 0, 5, rate_per_s=1e308), Anomaly("dropout", 0, 5)]
    if dropout_first:
        anomalies.reverse()
    assert AnomalyInjector(anomalies).apply(10, 2, "A", "temp-0") is None
