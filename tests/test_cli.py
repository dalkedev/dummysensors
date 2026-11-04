import json
from typing import ClassVar

import pytest

from dummysensors.cli import main


def test_generate_passes_elapsed_time_to_sensor(monkeypatch, capsys):
    readings = []

    class RecordingTemperatureSensor:
        __dataclass_fields__: ClassVar[dict[str, None]] = {"noise_sigma": None}

        def __init__(self, **kwargs):
            pass

        def read(self, t_s=None):
            readings.append(t_s)
            return 0 if t_s is None else t_s

    clock = iter((100.0, 100.25, 100.5))
    monkeypatch.setattr("dummysensors.cli.TemperatureSensor", RecordingTemperatureSensor)
    monkeypatch.setattr("dummysensors.cli.time.perf_counter", lambda: next(clock))

    main(["generate", "--count", "2", "--rate", "0"])

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert readings == pytest.approx([0.25, 0.5])
    assert [record["ts_ms"] for record in records] == [250, 500]
    assert [record["value"] for record in records] == pytest.approx([0.25, 0.5])
