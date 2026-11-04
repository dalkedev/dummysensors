import csv
import json
import os

from dummysensors.config import run_from_config


def test_config_yaml_creates_outputs(tmp_path):
    # prepare config
    cfg_path = tmp_path / "config.example.yaml"
    cfg_path.write_text(
        """
rate: 2
count: 5
partition_by: type

outputs:
  - type: jsonl
    for: temp
    path: temp.jsonl
  - type: csv
    for: vibration
    path: vibration.csv

devices:
  - id: engine-A
    sensors:
      - kind: temp
        count: 1
      - kind: vibration
        count: 1
"""
    )

    # run
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        run_from_config(str(cfg_path))
    finally:
        os.chdir(cwd)

    # check outputs
    temp_file = tmp_path / "temp.jsonl"
    vib_file = tmp_path / "vibration.csv"

    assert temp_file.exists()
    assert vib_file.exists()

    # check JSONL
    with open(temp_file, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert all("value" in rec for rec in lines)

    # check CSV
    with open(vib_file, newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
    assert reader[0] == ["ts_ms", "device_id", "sensor_id", "type", "value"]
    assert len(reader) > 1
