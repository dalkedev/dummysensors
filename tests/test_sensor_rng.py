import random

import pytest

from dummysensors.sensors import (
    OU,
    IrradianceSensor,
    LoadSensor,
    PVPowerSensor,
    TemperatureSensor,
    VibrationSensor,
)

STOCHASTIC_SENSORS = [
    TemperatureSensor,
    VibrationSensor,
    IrradianceSensor,
    LoadSensor,
    PVPowerSensor,
]
TIMES = (43200.0, 43200.1, 43200.4, 43200.9, 43201.1, 43201.7)


def readings(sensor):
    if isinstance(sensor, PVPowerSensor):
        return [sensor.read(t, irradiance=750.0) for t in TIMES]
    return [sensor.read(t) for t in TIMES]


@pytest.mark.parametrize("sensor_class", STOCHASTIC_SENSORS)
def test_same_seed_replays_sensor_at_exact_times(sensor_class):
    first = sensor_class(rng=random.Random(821))
    second = sensor_class(rng=random.Random(821))

    assert readings(first) == readings(second)


@pytest.mark.parametrize("sensor_class", STOCHASTIC_SENSORS)
def test_different_seeds_change_sensor_readings(sensor_class):
    first = sensor_class(rng=random.Random(821))
    second = sensor_class(rng=random.Random(822))

    assert readings(first) != readings(second)


@pytest.mark.parametrize("sensor_class", STOCHASTIC_SENSORS)
@pytest.mark.parametrize("seed", [None, 821])
def test_sensor_reads_leave_global_random_state_unchanged(sensor_class, seed):
    before = random.getstate()
    kwargs = {} if seed is None else {"rng": random.Random(seed)}
    sensor = sensor_class(**kwargs)
    readings(sensor)

    assert random.getstate() == before


@pytest.mark.parametrize("sensor_class", STOCHASTIC_SENSORS)
def test_sensor_consumes_supplied_random_stream(sensor_class):
    supplied = random.Random(821)
    expected = random.Random(821)
    kwargs = {"rng": supplied}
    if sensor_class is VibrationSensor:
        # Exercise both the spike decision and its sign, as well as OU noise.
        kwargs["spike_prob"] = 1.0
    sensor = sensor_class(**kwargs)

    readings(sensor)
    for _ in TIMES:
        expected.gauss(0, 0.05 if sensor_class is PVPowerSensor else 1.0)
        if sensor_class is VibrationSensor:
            expected.random()
            expected.choice((-1, 1))

    assert supplied.getstate() == expected.getstate()


def test_ou_replays_and_consumes_supplied_random_stream():
    supplied = random.Random(821)
    expected = random.Random(821)
    first = OU(rng=supplied)
    second = OU(rng=random.Random(821))
    intervals = (0.0, 0.1, 0.3, 0.5, 0.2, 0.6)

    assert [first.step(dt) for dt in intervals] == [second.step(dt) for dt in intervals]
    for _ in intervals:
        expected.gauss(0, 1.0)
    assert supplied.getstate() == expected.getstate()


def test_default_ou_does_not_consume_global_random_stream():
    before = random.getstate()
    process = OU()
    process.step(0.1)

    assert random.getstate() == before


@pytest.mark.parametrize("sensor_class", STOCHASTIC_SENSORS)
def test_default_sensors_have_independent_random_streams(sensor_class):
    first = sensor_class()
    second = sensor_class()
    untouched = second.rng.getstate()

    readings(first)

    assert first.rng is not second.rng
    assert second.rng.getstate() == untouched


def test_seeded_vibration_replays_spikes():
    first = VibrationSensor(spike_prob=1.0, rng=random.Random(821))
    second = VibrationSensor(spike_prob=1.0, rng=random.Random(821))

    assert readings(first) == readings(second)
