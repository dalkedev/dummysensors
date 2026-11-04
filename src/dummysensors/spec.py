from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class SensorSpec:
    kind: str
    count: int
    params: dict


@dataclass
class DeviceSpec:
    id: str
    sensors: List[SensorSpec]


def parse_spec(spec: str) -> list[DeviceSpec]:
    devices: list[DeviceSpec] = []
    for chunk in [c.strip() for c in spec.split(";") if c.strip()]:
        left, right = chunk.split(":", 1)
        # left: "device=engine-A"
        dev_id = left.split("=", 1)[1].strip()
        sensor_specs: list[SensorSpec] = []
        for item in right.split(","):
            item = item.strip()
            if not item:
                continue
            if "*" in item:
                kind, count = item.split("*", 1)
                sensor_specs.append(SensorSpec(kind=kind.strip(), count=int(count), params={}))
            else:
                sensor_specs.append(SensorSpec(kind=item, count=1, params={}))
        devices.append(DeviceSpec(id=dev_id, sensors=sensor_specs))
    return devices
