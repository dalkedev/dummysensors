from __future__ import annotations

import pytest

from dummysensors.orchestrator import run_stream


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, delay):
        self.value += delay


@pytest.fixture
def clock(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr("dummysensors.orchestrator.time.perf_counter", clock.now)
    monkeypatch.setattr("dummysensors.orchestrator.time.sleep", clock.sleep)
    return clock


def test_pv_reuses_latest_irradiance_between_producer_samples(clock):
    records = []
    run_stream(
        spec_str="",
        rate_hz=4,
        duration_s=None,
        total_count=9,
        writer_for_type={"*": records.append},
        devices_cfg=[
            {
                "id": "plant",
                "sensors": [
                    {
                        "kind": "irradiance",
                        "rate_hz": 1,
                        "params": {
                            "day_period_s": 4,
                            "sunrise": 0,
                            "sunset": 4,
                            "cloud_sigma": 0,
                        },
                    },
                    {"kind": "pv_power", "params": {"noise_sigma": 0}},
                ],
            }
        ],
    )

    pv = {record["ts_ms"]: record["value"] for record in records if record["type"] == "pv_power"}
    assert pv[1000] > 0
    for timestamp in (1250, 1500, 1750):
        assert pv[timestamp] == pytest.approx(pv[1000])


def test_soc_reuses_latest_load_separately_for_each_device(clock):
    records = []
    run_stream(
        spec_str="",
        rate_hz=4,
        duration_s=None,
        total_count=9,
        writer_for_type={"*": records.append},
        devices_cfg=[
            {
                "id": device,
                "sensors": [
                    {
                        "kind": "load",
                        "rate_hz": 1,
                        "params": {
                            "base_kw": load,
                            "morning_kw": 0,
                            "evening_kw": 0,
                            "noise_sigma": 0,
                        },
                    },
                    {"kind": "soc", "params": {"capacity_kwh": 1, "discharge_eff": 1}},
                ],
            }
            for device, load in (("A", 2), ("B", 1))
        ],
    )

    for device, load in (("A", 2), ("B", 1)):
        soc = [
            record["value"]
            for record in records
            if record["device_id"] == device and record["type"] == "soc"
        ]
        assert len(soc) == 9
        assert all(current < previous for previous, current in zip(soc, soc[1:]))
        assert soc[-1] == pytest.approx(50 - 100 * load * 2 / 3600)
