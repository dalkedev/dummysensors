from __future__ import annotations

import csv
import json
import os
import sys
from typing import Callable


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def jsonl_writer(path: str | None) -> Callable[[dict], None]:
    if not path:
        # stdout
        return lambda rec: (sys.stdout.write(json.dumps(rec) + "\n"), None)[1]
    _ensure_dir(path)
    f = open(path, "a", encoding="utf-8", buffering=1)
    return lambda rec: (f.write(json.dumps(rec) + "\n"), None)[1]


def csv_writer(path, header=("ts_ms", "device_id", "sensor_id", "type", "value")):
    _ensure_dir(path)
    f = open(path, "w", newline="", encoding="utf-8", buffering=1)
    w = csv.writer(f)
    cols = list(header)
    w.writerow(cols)
    f.flush()
    os.fsync(f.fileno())

    def _write(rec: dict) -> None:
        w.writerow([rec.get(c, "") for c in cols])
        f.flush()
        os.fsync(f.fileno())

    return _write
