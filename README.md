# dummysensors

[![PyPI version](https://img.shields.io/pypi/v/dummysensors.svg)](https://pypi.org/project/dummysensors/)
[![CI](https://github.com/dalkedev/dummysensors/actions/workflows/ci.yml/badge.svg)](https://github.com/dalkedev/dummysensors/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight generator of dummy sensor data for IoT and ML testing.
Provides a simple Python API and CLI, supports running multiple sensors in parallel, photovoltaic domain sensors, and splitting output streams into files.

---

## Installation

From PyPI (recommended):

```bash
pip install dummysensors
```

The core uses only the Python standard library (Python 3.9+). For YAML configuration:

```bash
pip install 'dummysensors[config]'
```

---

## Quick Start (API)

```python
from dummysensors import TemperatureSensor, VibrationSensor

# create sensors
temp = TemperatureSensor(min_val=18, max_val=24, noise_sigma=0.2)
vib = VibrationSensor(base_hz=50.0, amp=1.0, noise_sigma=0.05)

print(temp.read())  # e.g. 21.3
print(vib.read(t_s=0.123))  # sinusoidal signal with noise
```

---

## Config file (YAML)

Instead of passing long `--spec` strings, you can define your setup in a YAML file.
Pass the configuration path explicitly, for example `dummy-sensors run --config config.sensors.yaml`.

### Example `config.sensors.yaml`

```yaml
rate: 2
count: 5
partition_by: type

outputs:
  - type: jsonl
    for: temp
    path: out/temp.jsonl
  - type: csv
    for: vibration
    path: out/vibration.csv

devices:
  - id: engine-A
    sensors:
      - kind: temp
        count: 1
      - kind: vibration
        count: 1
  - id: plant-1
    sensors:
      - kind: irradiance
        count: 1
        params: {peak: 900.0, day_period_s: 10.0, sunrise: 0.0, sunset: 10.0}
      - kind: pv_power
        count: 1
        params: {stc_kw: 5.0, inverter_eff: 0.95, p_kw_max: 4.8}
      - kind: load
        count: 1
        params: {base_kw: 0.3, morning_kw: 0.8, evening_kw: 1.2}
      - kind: soc
        count: 1
        params: {capacity_kwh: 10.0, soc0: 50.0}
```

Run with:

```bash
dummy-sensors run --config config.sensors.yaml
```

---

## Quick Start (CLI)

Generate a single temperature stream to JSONL:

```bash
dummy-sensors generate --rate 5 --duration 2 --jsonl out/temp.jsonl
```

Run multiple sensors and devices, split by **type** into separate files:

```bash
dummy-sensors run \
  --rate 5 \
  --count 30 \
  --partition-by type \
  --spec "device=engine-A: temp*1,vibration*2; device=room-101: temp*2" \
  --out "temp=out/temp.jsonl" \
  --out "vibration=out/vib.jsonl" \
  --out "*=stdout"
```

Use `--partition-by type` to route `temp=...` and `vibration=...` mappings, or
`--partition-by device` for mappings such as `engine-A=out/engine.jsonl`.
The default `--partition-by none` uses only the `*` output.
`--count` is the number of global sampling ticks, not the total number of records:
the example above writes 90 temperature records and 60 vibration records.

> 👉 Check out a full demo with live plotting and JSONL logging here:
> [dummysensors demo (ds-test)](https://github.com/dalkedev/ds-test)

---

## Fault injection and deterministic replay (unreleased)

The unreleased checkout on `main` adds time-windowed faults and reproducible
simulation ticks. To try these additions, install `pip install -e '.[config]'`.

```python
from dummysensors import Anomaly, AnomalyInjector
from dummysensors.orchestrator import run_stream

faults = AnomalyInjector(
    [
        Anomaly("spike", 1, 3, device_id="A", sensor_id="temp-0", offset=10),
        Anomaly("drift", 1, 5, device_id="A", sensor_id="temp-0", rate_per_s=2),
        Anomaly("dropout", 3, 4, device_id="A", sensor_id="temp-0"),
    ]
)
records = []
run_stream(
    "device=A: temp*1; device=B: temp*1",
    rate_hz=1,
    duration_s=None,
    total_count=6,
    writer_for_type={"*": records.append},
    anomalies=faults,
    seed=42,
    simulation_times=[0, 1, 2, 3, 4, 5],
)
print(records)
```

`Anomaly(kind, start_s, end_s, device_id=None, sensor_id=None, offset=0,
rate_per_s=0)` defines one fault. Times are seconds since the run started; each
window includes its start and excludes its end: `[start_s, end_s)`.

| Kind | Effect while active |
| --- | --- |
| `spike` | Add the constant `offset` to each matching reading. |
| `drift` | Add `rate_per_s * (t_s - start_s)` to each matching reading. |
| `dropout` | Suppress the matching output record. |

Omitted device or sensor IDs match all IDs in that dimension. Supplied IDs match
exactly; sensor IDs such as `temp-0` are numbered per kind within each device.
Overlapping offsets add together, and any matching dropout wins. Faults modify
output only: the sensor model, cached dependency values and sampling schedule
still advance during a dropout. Irradiance, PV and battery dependencies therefore
use clean model readings. Fault-adjusted values are not clamped to the sensor's
normal range. Fault boundaries must be finite and nonnegative, with `end_s`
greater than `start_s`; offsets and drift rates must be finite.
If fault arithmetic overflows, the run raises `ValueError` before emitting that
record, rather than writing `Infinity`. Earlier records may already have been
written. With a nonempty anomaly list, YAML device IDs must be nonempty strings;
quote numeric-looking IDs. An omitted or empty anomaly list retains legacy ID
handling. Scenario options and those IDs are validated before opening outputs.

`anomalies`, `seed` and `simulation_times` are optional keyword arguments to
`run_stream`. Explicit times must be finite, nonnegative and strictly increasing,
with one entry per global tick. If `total_count` is given, it must match their
length; otherwise a count derived from `duration_s * rate_hz` must match. If
neither count nor duration is supplied, the number of explicit times determines
the tick count. Explicit times bypass waiting while preserving per-sensor rate
scheduling, so a slower sensor need not emit at every listed time.

With the same integer seed, IDs, times and sensor configuration, each stochastic
sensor replays its own local random stream. Streams are derived with SHA-256
from the seed and device/sensor IDs, so adding or reordering unrelated devices
or sensors does not disturb an existing stream when its IDs stay the same.
Python's global random state is untouched. Default runs retain real-time pacing;
a seed alone does not guarantee identical output files because actual elapsed
times can differ.

The runnable [examples/faults.yaml](examples/faults.yaml) uses two devices, fixed
20 °C temperature models and the three faults above:

```bash
dummy-sensors run --config examples/faults.yaml
```

Device A's `temp-0` emits 20, 30 and 32 at seconds 0, 1 and 2, skips second 3,
then emits 26 and 20 at seconds 4 and 5. Device B's temperature stays at 20.
Its vibration stream demonstrates seeded noise. All records go to stdout.
YAML accepts the same anomaly fields in a top-level `anomalies` list, an integer
`seed` and a `simulation_times` list. When `--config` is used, configuration
values take precedence over CLI options, including `--seed`.

Both CLI commands also accept a seed for ordinary real-time runs:

```bash
dummy-sensors run --seed 42 --rate 10 --count 6 --spec 'device=A: temp*1' --out '*=stdout'
dummy-sensors generate --seed 42 --rate 10 --count 6
```

Standalone stochastic sensors accept a `random.Random` instance through `rng`:

```python
import random
from dummysensors import TemperatureSensor

temp = TemperatureSensor(rng=random.Random(42))
print([temp.read(t) for t in [0, 1, 2]])
```

This applies to temperature, vibration, irradiance, PV power and load sensors.
Battery state-of-charge remains deterministic for a given power balance and times.

---

## `--spec` format

The `--spec` string describes devices and sensors:

```
device=<ID>: <type>*<count>[, <type>*<count> ...] ; device=<ID2>: ...
```

Examples:

* `device=A: temp*3` — device A with three temperature sensors
* `device=eng: temp*1,vibration*2; device=room: temp*2`

> As of `v0.3`, supported sensor types:
> `temp`, `vibration`, `irradiance`, `pv_power`, `load`, `soc`.
> You can define setups either with `--spec` (quick inline config) or using a YAML file (`--config config.sensors.yaml`) for more complex scenarios.

---

## Python API

Below is the up‑to‑date API that matches the code. All times are in seconds; pass monotonic time to `t_s` for stable integration. If `t_s=None`, sensors start from 0.

### `TemperatureSensor`

Daily temperature: sine wave + OU noise.

**Parameters (defaults):**

* `min_val: float = 15.0`
* `max_val: float = 30.0`
* `period_s: float = 24*3600`
* `phase_shift: float = -4*3600` — shift so the maximum is in the evening
* `noise_theta: float = 0.05` — mean‑reversion strength in OU
* `noise_sigma: float = 0.3` — OU noise scale

**Methods:**

* `read(t_s: float | None = None) -> float` — temperature in °C

---

### `VibrationSensor`

Base sine at `base_hz` + OU noise + rare spikes.

**Parameters (defaults):**

* `base_hz: float = 50.0`
* `amp: float = 1.0`
* `noise_theta: float = 2.0`
* `noise_sigma: float = 0.05`
* `spike_prob: float = 0.001` — spike probability per sample
* `spike_scale: float = 4.0` — spike magnitude (× `amp`)

**Methods:**

* `read(t_s: float | None = None) -> float`

---

### `IrradianceSensor`

Solar irradiance (W/m²): half‑sine between sunrise and sunset + slow OU “clouds”.

**Parameters (defaults):**

* `peak: float = 900.0` — peak W/m²
* `day_period_s: float = 24*3600`
* `sunrise: float = 6*3600`
* `sunset: float = 18*3600`
* `cloud_theta: float = 1/600.0` — slow cloud dynamics
* `cloud_sigma: float = 0.05`

**Methods:**

* `read(t_s: float | None = None) -> float` — W/m² (>= 0)

Note: the cloud factor is clamped to 0.2–1.2.

---

### `PVPowerSensor`

Inverter AC power (kW). Model:
`P_dc ≈ (irradiance/1000) * stc_kw`,
`P_ac = min(p_kw_max, max(0, P_dc * inverter_eff)) + N(0, noise_sigma)`

**Parameters (defaults):**

* `stc_kw: float = 5.0` — STC power at 1000 W/m²
* `inverter_eff: float = 0.95`
* `p_kw_max: float = 4.8`
* `noise_sigma: float = 0.05`

**Methods:**

* `read(t_s: float | None = None, irradiance: float | None = None) -> float`

  * Returns `0.0` if `irradiance is None`.

---

### `LoadSensor`

Consumption (kW): base + two daily “bumps” (morning & evening) + OU.

**Parameters (defaults):**

* `base_kw: float = 0.5`
* `morning_kw: float = 0.8`
* `evening_kw: float = 1.2`
* `day_period_s: float = 24*3600`
* `noise_theta: float = 1/120.0`
* `noise_sigma: float = 0.05`

**Methods:**

* `read(t_s: float | None = None) -> float` — kW (>= 0)

---

### `BatterySoCSensor`

State‑of‑charge simulator (%), integrating the power balance. Sign convention: positive `net_power_kw` means an energy deficit → discharge; negative means surplus → charge. Power limits and efficiencies are respected.

**Parameters (defaults):**

* `capacity_kwh: float = 10.0`
* `soc0: float = 50.0` — initial SoC \[%]
* `charge_eff: float = 0.95`
* `discharge_eff: float = 0.95`
* `p_charge_max_kw: float = 3.0`
* `p_discharge_max_kw: float = 3.0`

**Methods:**

* `step(t_s: float, net_power_kw: float) -> float` — returns current SoC \[%]

> Note: this is **not** a `read()`. Call `step(...)` each tick with the power balance.

---

### Sensor dependencies

* `PVPowerSensor` needs `irradiance` (e.g., from `IrradianceSensor`).
* `BatterySoCSensor` needs `net_power_kw = load_kw - pv_kw` (or a general balance).
  Positive → discharge, negative → charge.

---

### Sensor Registry

* `dummysensors.registry.SENSOR_REGISTRY` — maps string `kind` → class
* `dummysensors.registry.make_sensor(kind: str, **params)` — construct by name

---

### Orchestrator

`dummysensors.orchestrator.run_stream(...)`

* Builds instances from a `spec_str` or a `config`.
* Respects sensor **priority** and per‑sensor `rate_hz`.
* Retains each device's latest dependency readings between sampling ticks, so slower irradiance or load sensors can feed faster PV and battery sensors.
* Anchors sampling to the start time rather than each wake-up. Delayed ticks skip missed slots instead of emitting a burst of historical readings. The global tick rate caps how often any sensor can be read.
* Selects output keys according to `partition_by`: sensor type, device ID, or only `"*"` for `none`. `writer_for_type` maps those keys to `callable(sample_dict)`.

---

### Implementation notes

* **OU (Ornstein–Uhlenbeck)** uses `dt` from successive calls; a tiny minimum `dt` is applied when time does not advance.
* Prefer passing monotonic time to `t_s` (e.g., `time.monotonic()`), especially when chaining sensors in a pipeline.

## Output Format

JSON Lines (one record per line):

```json
{
  "ts_ms": 171234,
  "device_id": "engine-A",
  "sensor_id": "vibration-1",
  "type": "vibration",
  "value": -0.124
}
```

Also supported: **CSV**. Planned: Kafka, Redis Stream, WebSocket.

---

## Roadmap

* `v0.2` ✅ — CSV writer, partitioning, YAML config
* `v0.3` ✅ — Smart photovoltaic sensors (`irradiance`, `pv_power`, `load`, `soc`), per-sensor `rate_hz`, priority-based orchestration
* `v0.4` 🚧 — Partially implemented: AnomalyInjector (spike, dropout, drift) and seeded replay are available in the unreleased checkout on `main`; new sensors (`humidity`, `rpm`, `battery_voltage`, `gps`, `accel-3axis`) remain planned.
* `v0.5` 🚧 — Outputs: Kafka, Redis Stream, WebSocket live preview

---

## Development

```bash
git clone https://github.com/dalkedev/dummysensors
cd dummysensors
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[config,dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m build
python -m twine check --strict dist/*
```

On Windows use `py -m venv .venv`, then `.venv\Scripts\Activate.ps1` in PowerShell.
`requirements.txt` installs the same contributor extras; NumPy is not required.
The Makefile also supports `make install`, `make check`, and `make demo` from a shell with Make.

The CI matrix covers Python 3.9–3.15. Compatible tool versions are resolved for each
interpreter; Python 3.9 uses pytest 8, while newer interpreters can use pytest 9.
The package version has one source: `dummysensors.__version__`.

Dependency updates are grouped by Dependabot. Ruff autofix is manual and reuses one
branch; GitHub's **Actions → General → Allow GitHub Actions to create and approve pull
requests** setting must allow PR creation before that optional workflow can open a PR.
Normal CI only checks files and never creates branches.

---

## License

MIT © Mateusz Dalke
