from __future__ import annotations

from collections import Counter
from itertools import cycle

from dummysensors.orchestrator import run_stream


class FakeClock:
    def __init__(self, wake_jitter=(0.0,), first_sleep_leap=0.0):
        self.value = 0.0
        self.jitter = cycle(wake_jitter)
        self.first_sleep_leap = first_sleep_leap

    def now(self):
        return self.value

    def sleep(self, delay):
        self.value += delay + next(self.jitter) + self.first_sleep_leap
        self.first_sleep_leap = 0.0


def run_with_clock(monkeypatch, clock, *, rate_hz, total_count, sensor_rates):
    monkeypatch.setattr("dummysensors.orchestrator.time.perf_counter", clock.now)
    monkeypatch.setattr("dummysensors.orchestrator.time.sleep", clock.sleep)
    records = []
    run_stream(
        spec_str="",
        rate_hz=rate_hz,
        duration_s=None,
        total_count=total_count,
        writer_for_type={"*": records.append},
        devices_cfg=[
            {
                "id": "A",
                "sensors": [
                    {"kind": "temp", "rate_hz": rate, "params": {"noise_sigma": 0}}
                    for rate in sensor_rates
                ],
            }
        ],
    )
    return records


def test_sampling_rates_survive_variable_wake_jitter(monkeypatch):
    records = run_with_clock(
        monkeypatch,
        FakeClock(wake_jitter=(0.00003, 0.00017, 0.00001, 0.00009)),
        rate_hz=10,
        total_count=1000,
        sensor_rates=(None, 10, 5),
    )

    assert Counter(record["sensor_id"] for record in records) == {
        "temp-0": 1000,
        "temp-1": 1000,
        "temp-2": 500,
    }


def test_sampling_rates_do_not_accumulate_float_drift(monkeypatch):
    records = run_with_clock(
        monkeypatch,
        FakeClock(),
        rate_hz=30,
        total_count=3000,
        sensor_rates=(None, 10),
    )

    assert Counter(record["sensor_id"] for record in records) == {
        "temp-0": 3000,
        "temp-1": 1000,
    }


def test_large_clock_leap_skips_missed_slots_without_bursting(monkeypatch):
    records = run_with_clock(
        monkeypatch,
        FakeClock(first_sleep_leap=5),
        rate_hz=10,
        total_count=61,
        sensor_rates=(10,),
    )

    timestamps = [record["ts_ms"] for record in records]
    assert len(records) == 12
    assert timestamps[0] == 0
    assert timestamps[1] >= 5000
    assert len(timestamps) == len(set(timestamps))
