import json

import pytest

from dummysensors.cli import main
from dummysensors.config import run_from_config

BASE = """
rate: 1
count: 4
seed: 37
simulation_times: [0, 1, 2, 3]
outputs:
  - {type: jsonl, path: records.jsonl}
devices:
  - id: A
    sensors:
      - kind: temp
        params: {min_val: 20, max_val: 20, noise_sigma: 0}
  - id: B
    sensors:
      - kind: temp
        params: {min_val: 20, max_val: 20, noise_sigma: 0}
"""


def test_yaml_faults_and_seeded_replay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "faults.yaml"
    path.write_text(
        BASE
        + """
anomalies:
  - {kind: spike, start_s: 1, end_s: 3, device_id: A, sensor_id: temp-0, offset: 5}
  - {kind: drift, start_s: 1, end_s: 4, device_id: A, rate_per_s: 2}
  - {kind: dropout, start_s: 2, end_s: 3, device_id: B}
""",
        encoding="utf-8",
    )
    main(["run", "--config", str(path)])
    result = (tmp_path / "records.jsonl").read_bytes()
    records = [json.loads(line) for line in result.splitlines()]
    assert [(r["ts_ms"], r["value"]) for r in records if r["device_id"] == "A"] == [
        (0, 20),
        (1000, 25),
        (2000, 27),
        (3000, 24),
    ]
    assert [r["ts_ms"] for r in records if r["device_id"] == "B"] == [0, 1000, 3000]
    (tmp_path / "records.jsonl").unlink()  # JSONL intentionally appends by default
    run_from_config(str(path))
    assert (tmp_path / "records.jsonl").read_bytes() == result


@pytest.mark.parametrize(
    "extra",
    [
        "anomalies: null",
        "anomalies: [{kind: spike, start_s: 1, end_s: 0}]",
        "anomalies: [{kind: typo, start_s: 0, end_s: 1}]",
        "seed: true",
        "simulation_times: [0, 0, 1, 2]",
        "simulation_times: [0, 1]",
    ],
)
def test_bad_scenario_does_not_truncate_outputs(tmp_path, monkeypatch, extra):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "records.csv"
    output.write_text("keep me", encoding="utf-8")
    path = tmp_path / "faults.yaml"
    path.write_text(
        BASE.replace("type: jsonl, path: records.jsonl", "type: csv, path: records.csv")
        + "\n"
        + extra,
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        run_from_config(str(path))
    assert output.read_text(encoding="utf-8") == "keep me"


def test_cli_run_accepts_seed_without_changing_spec(monkeypatch):
    calls = []
    monkeypatch.setattr("dummysensors.cli.run_stream", lambda *a, **kw: calls.append((a, kw)))
    main(["run", "--spec", "device=A: temp*1", "--count", "2", "--seed", "17"])
    assert calls[0][0] == ("device=A: temp*1",)
    assert calls[0][1]["seed"] == 17


def test_generate_seed_replays_values_for_same_elapsed_times(monkeypatch, capsys):
    def sample(seed):
        clock = iter((100.0, 100.25, 100.5, 101.0))
        monkeypatch.setattr("dummysensors.cli.time.perf_counter", lambda: next(clock))
        main(["generate", "--count", "3", "--rate", "0", "--seed", str(seed)])
        return [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert sample(5) == sample(5)
    assert sample(5) != sample(6)


@pytest.mark.parametrize("optional_faults", ["", "anomalies: []\n"])
def test_yaml_without_fault_configuration_retains_legacy_numeric_device_ids(
    tmp_path, monkeypatch, optional_faults
):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "legacy.yaml"
    path.write_text(
        """
rate: 0
count: 1
outputs:
  - {type: jsonl, path: records.jsonl}
devices:
  - id: 7
    sensors:
      - kind: temp
""",
        encoding="utf-8",
    )
    with path.open("a", encoding="utf-8") as stream:
        stream.write(optional_faults)
    run_from_config(str(path))
    record = json.loads((tmp_path / "records.jsonl").read_text(encoding="utf-8"))
    assert record["device_id"] == 7


def test_active_faults_validate_actual_device_ids_before_opening_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "records.csv"
    output.write_text("keep me", encoding="utf-8")
    path = tmp_path / "invalid-target.yaml"
    path.write_text(
        """
rate: 0
count: 1
anomalies:
  - {kind: spike, start_s: 0, end_s: 1, offset: 10}
outputs:
  - {type: csv, path: records.csv}
devices:
  - id: 7
    sensors:
      - kind: temp
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="device.*id.*string"):
        run_from_config(str(path))
    assert output.read_text(encoding="utf-8") == "keep me"
