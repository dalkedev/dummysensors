from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List


class Capture:
    """Simple sink for records per type (and per device if needed)."""

    def __init__(self):
        self.per_type: Dict[str, List[dict]] = defaultdict(list)
        self.per_device: Dict[str, List[dict]] = defaultdict(list)

    def writer_for_type(self, k: str):
        def _w(rec: dict):
            self.per_type[rec["type"]].append(rec)
            self.per_device[rec["device_id"]].append(rec)

        return _w

    def router(self, mapping: Dict[str, Callable]):
        """Return function: type->writer (with '*' default)."""
        default = mapping.get("*", lambda rec: None)

        def _route(rec: dict):
            w = mapping.get(rec["type"], default)
            w(rec)

        return _route
