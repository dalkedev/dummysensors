from typing import Any, Callable

from .sensors import (
    BatterySoCSensor,
    IrradianceSensor,
    LoadSensor,
    PVPowerSensor,
    TemperatureSensor,
    VibrationSensor,
)

SENSOR_REGISTRY: dict[str, Callable[..., Any]] = {
    "temp": TemperatureSensor,
    "vibration": VibrationSensor,
    "irradiance": IrradianceSensor,
    "pv_power": PVPowerSensor,
    "load": LoadSensor,
    "soc": BatterySoCSensor,
}


def make_sensor(kind: str, **params):
    cls = SENSOR_REGISTRY.get(kind)
    if not cls:
        raise ValueError(f"Unknown sensor kind: {kind}")
    return cls(**params)
