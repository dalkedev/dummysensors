from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from .io import csv_writer, jsonl_writer
from .orchestrator import run_stream

DEFAULT_CONFIG_CANDIDATES = (
    "config.sensors.yaml",
    "config.sensors.yml",
    "dummysensors.yaml",
    "dummysensors.yml",
)


def find_config_path(start: str | None = None) -> str | None:
    """Return first matching config file path from DEFAULT_CONFIG_CANDIDATES in `start` or CWD."""
    base = Path(start) if start else Path.cwd()
    for name in DEFAULT_CONFIG_CANDIDATES:
        cand = base / name
        if cand.exists():
            return str(cand)
    return None


def _writer_for_decl(decl: dict):
    fmt = str(decl.get("type", "jsonl")).lower()
    path = decl.get("path")
    if fmt == "csv":
        if not path:
            raise ValueError("CSV output requires 'path' in config.")
        return csv_writer(str(path))
    return jsonl_writer(path)  # stdout if path is None


def run_from_config(path: str) -> None:
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise RuntimeError("Install PyYAML to use --config (pip install pyyaml)") from e

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    rate = float(cfg.get("rate", 5))
    duration = cfg.get("duration")
    count = cfg.get("count")
    partition_by = cfg.get("partition_by", "none")

    # writers
    writers: Dict[str, Callable[[dict], None]] = {}
    for out in cfg.get("outputs", []):
        k = out.get("for", "*")
        writers[k] = _writer_for_decl(out)

    # pass full devices tree (with params/priority/rate_hz)
    devices_cfg: list[dict[str, Any]] = cfg.get("devices", [])

    # for backward compatibility we still build a spec_str
    parts = []
    for dev in devices_cfg:
        sid = dev["id"]
        items = []
        for s in dev.get("sensors", []):
            items.append(f"{s['kind']}*{int(s.get('count', 1))}")
        parts.append(f"device={sid}: " + ",".join(items))
    spec_str = "; ".join(parts)

    run_stream(
        spec_str=spec_str,
        rate_hz=rate,
        duration_s=duration,
        total_count=count,
        writer_for_type=writers,
        partition_by=partition_by,
        devices_cfg=devices_cfg,
    )
