from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# ---------- helpers ----------


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


class OU:
    """
    Ornstein–Uhlenbeck: mean-reverting noise.
    x_{t+dt} = x_t + theta*(mu - x_t)*dt + sigma*sqrt(dt)*N(0,1)
    """

    def __init__(self, mu=0.0, theta=0.5, sigma=0.5, x0=0.0, rng: random.Random | None = None):
        self.mu = mu
        self.theta = theta
        self.sigma = sigma
        self.x = x0
        self.rng = rng if rng is not None else random.Random()

    def step(self, dt: float) -> float:
        # dt w sekundach; model w skali sekundowej
        if dt <= 0:
            dt = 1e-3
        dx = self.theta * (self.mu - self.x) * dt + self.sigma * math.sqrt(dt) * self.rng.gauss(
            0, 1.0
        )
        self.x += dx
        return self.x


# ---------- Temperature ----------


@dataclass
class TemperatureSensor:
    """
    Temperature (°C): daily sine wave + OU noise.
    """

    type: str = field(default="temp", init=False)
    min_val: float = 15.0
    max_val: float = 30.0
    period_s: float = 24 * 3600
    # shape of the sine wave: phase shift so max is in the evening
    phase_shift: float = -4 * 3600  # max temp at evening
    noise_theta: float = 0.05
    noise_sigma: float = 0.3
    rng: random.Random = field(default_factory=random.Random, repr=False, compare=False)

    def __post_init__(self):
        if self.min_val > self.max_val:
            self.min_val, self.max_val = self.max_val, self.min_val
        mid = 0.5 * (self.min_val + self.max_val)
        amp = 0.5 * (self.max_val - self.min_val)
        self._mid = mid
        self._amp = amp
        self._ou = OU(mu=0.0, theta=self.noise_theta, sigma=self.noise_sigma, x0=0.0, rng=self.rng)
        self._t_prev = None

    def read(self, t_s: float | None = None) -> float:
        t = 0.0 if t_s is None else t_s
        base = self._mid + self._amp * math.sin(
            2 * math.pi * ((t + self.phase_shift) % self.period_s) / self.period_s
        )
        # step OU
        dt = 0.0 if self._t_prev is None else max(1e-3, t - self._t_prev)
        n = self._ou.step(dt)
        self._t_prev = t
        return base + n


# ---------- Vibration ----------


@dataclass
class VibrationSensor:
    type: str = "vibration"
    base_hz: float = 50.0
    amp: float = 1.0
    noise_theta: float = 2.0
    noise_sigma: float = 0.05
    spike_prob: float = 0.001
    spike_scale: float = 4.0
    rng: random.Random = field(default_factory=random.Random, repr=False, compare=False)

    def __post_init__(self):
        self._ou = OU(mu=0.0, theta=self.noise_theta, sigma=self.noise_sigma, x0=0.0, rng=self.rng)
        self._t_prev = None

    def read(self, t_s: float | None = None) -> float:
        t = 0.0 if t_s is None else t_s
        sig = self.amp * math.sin(2 * math.pi * self.base_hz * t)
        dt = 0.0 if self._t_prev is None else max(1e-4, t - self._t_prev)
        sig += self._ou.step(dt)
        self._t_prev = t
        # occasional spike
        if self.rng.random() < self.spike_prob:
            sig += self.rng.choice((-1, 1)) * self.spike_scale * self.amp
        return sig


# ---------- PV / Energy ----------


@dataclass
class IrradianceSensor:
    """
    Solar irradiance (W/m2): half-sine day profile + slow OU clouds.
    """

    type: str = "irradiance"
    peak: float = 900.0
    day_period_s: float = 24 * 3600
    sunrise: float = 6 * 3600
    sunset: float = 18 * 3600
    cloud_theta: float = 1 / 600.0  # slow changes
    cloud_sigma: float = 0.05
    rng: random.Random = field(default_factory=random.Random, repr=False, compare=False)

    def __post_init__(self):
        self._cloud = OU(
            mu=0.0, theta=self.cloud_theta, sigma=self.cloud_sigma, x0=0.0, rng=self.rng
        )
        self._t_prev = None

    def _day_frac(self, t: float) -> float:
        # 0 at night, 1 at day; half-sine between sunrise..sunset
        tday = t % self.day_period_s
        if tday < self.sunrise or tday > self.sunset:
            return 0.0
        span = self.sunset - self.sunrise
        x = (tday - self.sunrise) / span  # 0..1
        return math.sin(math.pi * x)  # 0..1

    def read(self, t_s: float | None = None) -> float:
        t = 0.0 if t_s is None else t_s
        frac = self._day_frac(t)
        dt = 0.0 if self._t_prev is None else max(1e-3, t - self._t_prev)
        clouds = clamp(1.0 + self._cloud.step(dt), 0.2, 1.2)  # „clouds” 0.2..1.2
        self._t_prev = t
        return max(0.0, self.peak * frac * clouds)


@dataclass
class PVPowerSensor:
    """
    Inverter AC power (kW). Simple model:
    P = min(P_dc * eff, p_kw_max)
    where P_dc ≈ irradiance/1000 * p_kw_stc (power at 1000 W/m²),
    and eff ≈ overall efficiency (0..1).
    """

    type: str = "pv_power"
    stc_kw: float = 5.0  # power STC at 1000 W/m2
    inverter_eff: float = 0.95
    p_kw_max: float = 4.8  # limit of the power inverter
    noise_sigma: float = 0.05
    rng: random.Random = field(default_factory=random.Random, repr=False, compare=False)

    def read(self, t_s: float | None = None, irradiance: float | None = None) -> float:
        if irradiance is None:
            # fallback: if no irradiance given, return 0
            return 0.0
        p_dc = (irradiance / 1000.0) * self.stc_kw
        p_ac = min(self.p_kw_max, max(0.0, p_dc * self.inverter_eff))
        return max(0.0, p_ac + self.rng.gauss(0, self.noise_sigma))


@dataclass
class LoadSensor:
    """
    Consumption (kW). Two daily peaks: morning and evening + OU.
    """

    type: str = "load_kw"
    base_kw: float = 0.5
    morning_kw: float = 0.8
    evening_kw: float = 1.2
    day_period_s: float = 24 * 3600
    noise_theta: float = 1 / 120.0
    noise_sigma: float = 0.05
    rng: random.Random = field(default_factory=random.Random, repr=False, compare=False)

    def __post_init__(self):
        self._ou = OU(mu=0.0, theta=self.noise_theta, sigma=self.noise_sigma, x0=0.0, rng=self.rng)
        self._t_prev = None

    def read(self, t_s: float | None = None) -> float:
        t = 0.0 if t_s is None else t_s
        x = (t % self.day_period_s) / self.day_period_s

        # two bumps: morning ~0.25 (6:00), evening ~0.75 (18:00)
        def bump(mu, sigma):
            return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

        morning = self.morning_kw * bump(0.25, 0.07)  # ~6:00
        evening = self.evening_kw * bump(0.75, 0.10)  # ~18:00
        base = self.base_kw + morning + evening
        dt = 0.0 if self._t_prev is None else max(1e-3, t - self._t_prev)
        n = self._ou.step(dt)
        self._t_prev = t
        return max(0.0, base + n)


@dataclass
class BatterySoCSensor:
    """
    Battery state-of-charge (SoC) simulator (%). Integrates the power balance.
    capacity [kWh], charge/discharge efficiency, power limits.
    Convention: positive 'battery_power' = discharge (supplying kW to the load),
    negative = charge.
    """

    type: str = "soc"
    capacity_kwh: float = 10.0
    soc0: float = 50.0
    charge_eff: float = 0.95
    discharge_eff: float = 0.95
    p_charge_max_kw: float = 3.0
    p_discharge_max_kw: float = 3.0

    def __post_init__(self):
        self._soc = clamp(self.soc0, 0.0, 100.0)
        self._t_prev = None

    def step(self, t_s: float, net_power_kw: float) -> float:
        """
        net_power_kw: positive when there’s an energy deficit (need to discharge), negative when there’s a surplus (can charge).
        """
        if self._t_prev is None:
            self._t_prev = t_s
            return self._soc

        dt_h = max(1e-6, (t_s - self._t_prev) / 3600.0)  # hours
        self._t_prev = t_s

        soc = self._soc
        if net_power_kw > 0:  # discharge
            p = min(net_power_kw, self.p_discharge_max_kw)
            delta_kwh = p * dt_h / self.discharge_eff
            soc -= 100.0 * (delta_kwh / self.capacity_kwh)
        elif net_power_kw < 0:  # charge
            p = min(-net_power_kw, self.p_charge_max_kw)
            delta_kwh = p * dt_h * self.charge_eff
            soc += 100.0 * (delta_kwh / self.capacity_kwh)

        self._soc = clamp(soc, 0.0, 100.0)
        return self._soc


# ! Note: PVPowerSensor and BatterySoCSensor require context (irradiance / power balance).
# ^ The orchestrator can use them if you build a pipeline (e.g., irradiance first, then PV).
