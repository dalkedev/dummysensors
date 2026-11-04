from __future__ import annotations

import math

from dummysensors import VibrationSensor


def test_vibration_basic():
    amp = 1.0
    vib = VibrationSensor(
        base_hz=8.0,
        amp=amp,
        noise_theta=2.0,
        noise_sigma=0.05,
        spike_prob=0.0,  # ← disable spikes for a stable test
        spike_scale=4.0,
    )
    dt = 0.001
    n = 1500
    vals = [vib.read(i * dt) for i in range(n)]

    assert all(math.isfinite(v) for v in vals)
    mean = sum(vals) / len(vals)
    assert abs(mean) < 0.2

    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var)
    assert 0.4 <= std <= 1.2

    # allow for OU noise, but not spikes
    mx, mn = max(vals), min(vals)
    max_allowed = amp + 4 * 0.05
    min_allowed = -amp - 4 * 0.05
    assert mn >= min_allowed and mx <= max_allowed, (
        f"values exceeded expected bounds: "
        f"min={mn}, max={mx}, allowed=({min_allowed}, {max_allowed})"
    )
