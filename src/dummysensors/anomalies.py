"""Deterministic, time-windowed faults for generated sensor readings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from math import isfinite
from numbers import Real


def _validate_number(name: str, value: float, *, nonnegative: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        finite = isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be a finite number")
    if nonnegative and value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _validate_id(name: str, value: str | None, *, wildcard: bool = False) -> None:
    if wildcard and value is None:
        return
    if not isinstance(value, str) or not value:
        suffix = " or None" if wildcard else ""
        raise ValueError(f"{name} must be a nonempty string{suffix}")


@dataclass(frozen=True)
class Anomaly:
    """A fault active during [start_s, end_s), optionally restricted to exact IDs.

    Spikes add ``offset``; drift adds ``rate_per_s * (t_s - start_s)``.
    A matching dropout suppresses a reading regardless of other active faults.
    """

    kind: str
    start_s: float
    end_s: float
    device_id: str | None = None
    sensor_id: str | None = None
    offset: float = 0.0
    rate_per_s: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or self.kind not in {"spike", "dropout", "drift"}:
            raise ValueError("kind must be one of: spike, dropout, drift")
        _validate_number("start_s", self.start_s, nonnegative=True)
        _validate_number("end_s", self.end_s, nonnegative=True)
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        _validate_id("device_id", self.device_id, wildcard=True)
        _validate_id("sensor_id", self.sensor_id, wildcard=True)
        _validate_number("offset", self.offset)
        _validate_number("rate_per_s", self.rate_per_s)


class AnomalyInjector:
    """Apply immutable anomaly definitions without modifying their input collection."""

    def __init__(self, anomalies: Iterable[Anomaly] = ()) -> None:
        try:
            definitions = tuple(anomalies)
        except TypeError as exc:
            raise ValueError("anomalies must be an iterable of Anomaly objects") from exc
        for index, anomaly in enumerate(definitions):
            if not isinstance(anomaly, Anomaly):
                raise ValueError(f"anomalies entry {index} must be an Anomaly object")
        self._anomalies = definitions

    @classmethod
    def from_config(cls, entries: list[Mapping[str, object]]) -> AnomalyInjector:
        """Parse a YAML-style list of mappings, rejecting invalid definitions eagerly."""
        if not isinstance(entries, list):
            raise ValueError("anomalies must be a list of mappings")
        allowed = {field.name for field in fields(Anomaly)}
        required = {"kind", "start_s", "end_s"}
        anomalies = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise ValueError(f"anomalies entry {index} must be a mapping")
            unknown = set(entry) - allowed
            if unknown:
                names = ", ".join(sorted(str(key) for key in unknown))
                raise ValueError(f"anomalies entry {index} has unknown fields: {names}")
            missing = required - set(entry)
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"anomalies entry {index} is missing required fields: {names}")
            try:
                anomalies.append(Anomaly(**entry))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"anomalies entry {index}: {exc}") from exc
        return cls(anomalies)

    def apply(self, value: float, t_s: float, device_id: str, sensor_id: str) -> float | None:
        """Return the adjusted reading, or None when an active dropout matches."""
        _validate_number("value", value)
        _validate_number("t_s", t_s, nonnegative=True)
        _validate_id("device_id", device_id)
        _validate_id("sensor_id", sensor_id)
        adjustment = 0.0
        for anomaly in self._anomalies:
            if not anomaly.start_s <= t_s < anomaly.end_s:
                continue
            if anomaly.device_id is not None and anomaly.device_id != device_id:
                continue
            if anomaly.sensor_id is not None and anomaly.sensor_id != sensor_id:
                continue
            if anomaly.kind == "dropout":
                return None
            if anomaly.kind == "spike":
                adjustment += anomaly.offset
            elif anomaly.kind == "drift":
                adjustment += anomaly.rate_per_s * (t_s - anomaly.start_s)
        adjusted = value + adjustment
        _validate_number("adjusted value", adjusted)
        return adjusted
