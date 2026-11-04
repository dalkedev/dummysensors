import json
import os

from dummysensors.config import find_config_path, run_from_config


def test_find_config_path_prefers_config_sensors_yaml(tmp_path):
    # prepare two files – should prefer config.sensors.yaml
    (tmp_path / "config.yaml").write_text("rate: 1\ncount: 1\ndevices: []\n", encoding="utf-8")
    (tmp_path / "config.sensors.yaml").write_text(
        "rate: 1\ncount: 1\ndevices: []\n", encoding="utf-8"
    )

    p = find_config_path(str(tmp_path))
    assert p is not None and p.endswith("config.sensors.yaml")


def test_run_from_config_creates_outputs_via_discovery(tmp_path):
    # write a config file in tmp dir
    (tmp_path / "config.sensors.yaml").write_text(
        """\
rate: 1
count: 2
partition_by: type
outputs:
  - type: jsonl
    for: temp
    path: temp.jsonl
  - type: csv
    for: vibration
    path: vib.csv
devices:
  - id: A
    sensors:
      - kind: temp
        count: 1
      - kind: vibration
        count: 1
""",
        encoding="utf-8",
    )

    # run with discovery
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        cfg = find_config_path()
        assert cfg is not None
        run_from_config(cfg)
    finally:
        os.chdir(cwd)

    # assert files created
    temp_file = tmp_path / "temp.jsonl"
    vib_file = tmp_path / "vib.csv"

    assert temp_file.exists()
    assert vib_file.exists()

    # JSONL parses
    first_line = temp_file.read_text(encoding="utf-8").splitlines()[0]
    json.loads(first_line)

    # CSV has header
    header = vib_file.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("ts_ms,device_id,sensor_id,type,value")
