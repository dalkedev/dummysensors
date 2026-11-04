from __future__ import annotations

import copy
import random

import pytest

import dummysensors
from dummysensors.orchestrator import run_stream


def capture(*, devices=None, anomalies=None, times=(0, 1, 2, 3), seed=None, spec=""):
    records = []
    run_stream(
        spec,
        rate_hz=1,
        duration_s=None,
        total_count=len(times),
        writer_for_type={"*": records.append},
        devices_cfg=devices,
        anomalies=anomalies,
        simulation_times=times,
        seed=seed,
    )
    return records


def constant_devices():
    return [
        {
            "id": d,
            "sensors": [
                {
                    "kind": "temp",
                    "count": 2,
                    "params": {
                        "min_val": 20,
                        "max_val": 20,
                        "noise_sigma": 0,
                    },
                }
            ],
        }
        for d in ("A", "B")
    ]


def injector(*rules):
    return dummysensors.AnomalyInjector([dummysensors.Anomaly(**rule) for rule in rules])


def test_targeted_faults_keep_record_contract_and_half_open_window():
    records = capture(
        devices=constant_devices(),
        anomalies=injector(
            dict(kind="spike", start_s=1, end_s=3, offset=10, device_id="A", sensor_id="temp-1"),
            dict(
                kind="drift", start_s=1, end_s=3, rate_per_s=-2, device_id="B", sensor_id="temp-0"
            ),
        ),
    )
    by_sensor = {
        (d, s): [r["value"] for r in records if (r["device_id"], r["sensor_id"]) == (d, s)]
        for d in ("A", "B")
        for s in ("temp-0", "temp-1")
    }
    assert by_sensor == {
        ("A", "temp-0"): [20] * 4,
        ("A", "temp-1"): [20, 30, 30, 20],
        ("B", "temp-0"): [20, 20, 18, 20],
        ("B", "temp-1"): [20] * 4,
    }
    assert all(set(r) == {"ts_ms", "device_id", "sensor_id", "type", "value"} for r in records)
    assert all(isinstance(r["value"], float) for r in records)


def energy_devices():
    return [
        {
            "id": d,
            "sensors": [
                {
                    "kind": "irradiance",
                    "rate_hz": 0.5,
                    "params": {"day_period_s": 8, "sunrise": 0, "sunset": 8, "cloud_sigma": 0},
                },
                {"kind": "pv_power", "params": {"noise_sigma": 0}},
                {
                    "kind": "load",
                    "params": {"base_kw": load, "morning_kw": 0, "evening_kw": 0, "noise_sigma": 0},
                },
                {"kind": "soc", "params": {"capacity_kwh": 1, "discharge_eff": 1}},
            ],
        }
        for d, load in (("A", 2), ("B", 1))
    ]


@pytest.mark.parametrize(
    "kind,parameters",
    [("dropout", {}), ("spike", {"offset": 1000}), ("drift", {"rate_per_s": 1000})],
)
@pytest.mark.parametrize("sensor_id", ["irradiance-0", "pv_power-0", "load-0"])
def test_faults_do_not_pollute_cached_pv_or_soc_dependencies(kind, parameters, sensor_id):
    baseline = capture(devices=energy_devices(), times=tuple(range(9)), seed=42)
    changed = capture(
        devices=energy_devices(),
        times=tuple(range(9)),
        seed=42,
        anomalies=injector(
            dict(kind=kind, start_s=1, end_s=7, device_id="A", sensor_id=sensor_id, **parameters)
        ),
    )
    assert [r for r in changed if (r["device_id"], r["sensor_id"]) != ("A", sensor_id)] == [
        r for r in baseline if (r["device_id"], r["sensor_id"]) != ("A", sensor_id)
    ]
    assert [r for r in changed if r["device_id"] == "B"] == [
        r for r in baseline if r["device_id"] == "B"
    ]
    if kind == "dropout" and sensor_id == "irradiance-0":
        assert [
            r["ts_ms"] for r in changed if r["device_id"] == "A" and r["type"] == "irradiance"
        ] == [0, 8000]


def test_dropout_still_steps_soc_and_recovers_at_end():
    devices = energy_devices()
    baseline = capture(devices=devices, times=tuple(range(9)), seed=42)
    changed = capture(
        devices=devices,
        times=tuple(range(9)),
        seed=42,
        anomalies=injector(
            dict(kind="dropout", start_s=1, end_s=7, device_id="A", sensor_id="soc-0")
        ),
    )
    assert [r for r in changed if r["device_id"] == "A" and r["type"] == "soc"] == [
        r
        for r in baseline
        if r["device_id"] == "A" and r["type"] == "soc" and r["ts_ms"] in (0, 7000, 8000)
    ]


def test_seed_replay_is_local_and_independent_of_device_order():
    devices = [
        {
            "id": d,
            "sensors": [
                {"kind": k} for k in ("temp", "vibration", "irradiance", "pv_power", "load", "soc")
            ],
        }
        for d in ("A", "B")
    ]
    before = random.getstate()
    original = copy.deepcopy(devices)
    a = capture(devices=devices, seed=123)
    b = capture(devices=list(reversed(devices)), seed=123)
    assert sorted(a, key=lambda r: (r["ts_ms"], r["device_id"], r["sensor_id"])) == sorted(
        b, key=lambda r: (r["ts_ms"], r["device_id"], r["sensor_id"])
    )
    assert a == capture(devices=devices, seed=123)
    assert a != capture(devices=devices, seed=124)
    assert [r for r in a if r["device_id"] == "A"] == capture(devices=devices[:1], seed=123)
    assert random.getstate() == before
    assert devices == original


@pytest.mark.parametrize(
    "times", [(0, 0), (1, 0), (-1, 0), (0, float("nan")), (0, float("inf")), (False, 1), ("0", 1)]
)
def test_replay_rejects_invalid_times_before_emission(times):
    records = []
    with pytest.raises(ValueError):
        run_stream("device=A: temp*1", 1, None, 2, {"*": records.append}, simulation_times=times)
    assert records == []


def test_replay_rejects_count_mismatch_and_invalid_seed():
    with pytest.raises(ValueError):
        run_stream("device=A: temp*1", 1, None, 3, {}, simulation_times=[0, 1])
    for seed in (True, 2.5, "10"):
        with pytest.raises(ValueError):
            capture(spec="device=A: temp*1", seed=seed)


def test_spec_replay_without_config_uses_same_rng_contract():
    assert capture(spec="device=A: temp*1,vibration*1", seed=5) == capture(
        spec="device=A: temp*1,vibration*1", seed=5
    )
