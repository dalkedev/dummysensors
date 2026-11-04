from __future__ import annotations

import os
from pathlib import Path

from dummysensors.config import run_from_config

YAML = """
rate: 10
count: 30
partition_by: type

outputs:
  - type: jsonl
    for: temp
    path: temp.jsonl
  - type: jsonl
    for: pv_power
    path: pv.jsonl

devices:
  - id: plant-1
    sensors:
      - kind: irradiance
        count: 1
        priority: 0
        params:
          peak: 800
          day_period_s: 2.0
          sunrise: 0.0
          sunset: 2.0
      - kind: pv_power
        count: 1
        priority: 1
        params:
          stc_kw: 4.0
          p_kw_max: 3.8
      - kind: temp
        count: 1
        priority: 5
        rate_hz: 5
"""


def test_run_from_config_with_params_priority_and_rate(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "config.sensors.yaml"
    cfg.write_text(YAML.strip(), encoding="utf-8")
    cwd0 = os.getcwd()
    os.chdir(tmp_path)
    try:
        run_from_config(str(cfg))
        assert (tmp_path / "temp.jsonl").exists()
        assert (tmp_path / "pv.jsonl").exists()

        # sanity: pliki nie są puste
        assert (tmp_path / "temp.jsonl").stat().st_size > 0
        assert (tmp_path / "pv.jsonl").stat().st_size > 0
    finally:
        os.chdir(cwd0)
