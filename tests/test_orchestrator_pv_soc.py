from __future__ import annotations

from dummysensors.orchestrator import run_stream

from .utils import Capture


def _writers(capture: Capture):
    # Route everything to a single sink (you can split per-type if needed)
    return {"*": capture.router({"*": capture.writer_for_type("*")})}


def test_pv_pipeline_day_night_like_behaviour():
    """
    Mini-day: day_period_s=2s, sunrise=0.5, sunset=1.5, so ~1.0s is 'noon'.
    Expect pv_power to become > 0 when irradiance > 0.
    """
    cap = Capture()
    devices_cfg = [
        {
            "id": "plant-1",
            "sensors": [
                {
                    "kind": "irradiance",
                    "count": 1,
                    "priority": 0,
                    "params": {"peak": 900.0, "day_period_s": 2.0, "sunrise": 0.5, "sunset": 1.5},
                },
                {
                    "kind": "pv_power",
                    "count": 1,
                    "priority": 1,
                    "params": {"stc_kw": 5.0, "inverter_eff": 0.95, "p_kw_max": 4.8},
                },
            ],
        }
    ]

    run_stream(
        spec_str="device=plant-1: irradiance*1,pv_power*1",
        rate_hz=10.0,  # 0.1s tick
        duration_s=None,
        total_count=30,  # ~3s -> should cover night->day->night
        writer_for_type={"*": cap.router({"*": cap.writer_for_type("*")})},
        partition_by="none",
        devices_cfg=devices_cfg,
    )

    irr_vals = [r["value"] for r in cap.per_type["irradiance"]]
    pv_vals = [r["value"] for r in cap.per_type["pv_power"]]

    # Did pv_power ever go above zero?
    assert any(v > 0.05 for v in pv_vals), (
        "pv_power never went above zero despite non-zero irradiance"
    )
    # Irradiance should have both >0 (day) and =0 (night) moments
    assert any(v == 0 for v in irr_vals) and any(v > 100 for v in irr_vals)


def test_soc_integration_charge_and_discharge():
    """
    Two runs:
      1) Surplus PV -> SoC increases.
      2) Deficit (load > pv) -> SoC decreases.
    """
    # 1) Charging (surplus)
    cap1 = Capture()
    devices_cfg1 = [
        {
            "id": "plant-1",
            "sensors": [
                {
                    "kind": "irradiance",
                    "count": 1,
                    "priority": 0,
                    "params": {"peak": 900.0, "day_period_s": 2.0, "sunrise": 0.5, "sunset": 1.5},
                },
                {
                    "kind": "pv_power",
                    "count": 1,
                    "priority": 1,
                    "params": {"stc_kw": 6.0, "p_kw_max": 5.5},
                },
                {
                    "kind": "load",
                    "count": 1,
                    "priority": 2,
                    "params": {
                        "base_kw": 0.1,
                        "morning_kw": 0.0,
                        "evening_kw": 0.0,
                        "day_period_s": 2.0,
                    },
                },
                {
                    "kind": "soc",
                    "count": 1,
                    "priority": 3,
                    "params": {"capacity_kwh": 5.0, "soc0": 50.0},
                },
            ],
        }
    ]
    run_stream(
        spec_str="device=plant-1: irradiance*1,pv_power*1,load*1,soc*1",
        rate_hz=10.0,
        duration_s=None,
        total_count=30,
        writer_for_type={"*": cap1.router({"*": cap1.writer_for_type("*")})},
        partition_by="none",
        devices_cfg=devices_cfg1,
    )
    soc_vals1 = [r["value"] for r in cap1.per_type["soc"]]
    assert soc_vals1[-1] > soc_vals1[0], "SoC did not increase under PV surplus"

    # 2) Discharging (deficit) – disable PV and use higher load
    cap2 = Capture()
    devices_cfg2 = [
        {
            "id": "plant-1",
            "sensors": [
                {
                    "kind": "load",
                    "count": 1,
                    "priority": 2,
                    "params": {
                        "base_kw": 2.0,
                        "morning_kw": 0.0,
                        "evening_kw": 0.0,
                        "day_period_s": 2.0,
                    },
                },
                {
                    "kind": "soc",
                    "count": 1,
                    "priority": 3,
                    "params": {"capacity_kwh": 5.0, "soc0": 80.0},
                },
            ],
        }
    ]
    run_stream(
        spec_str="device=plant-1: load*1,soc*1",
        rate_hz=10.0,
        duration_s=None,
        total_count=20,
        writer_for_type={"*": cap2.router({"*": cap2.writer_for_type("*")})},
        partition_by="none",
        devices_cfg=devices_cfg2,
    )
    soc_vals2 = [r["value"] for r in cap2.per_type["soc"]]
    assert soc_vals2[-1] < soc_vals2[0], "SoC did not decrease under net deficit"
