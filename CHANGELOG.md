# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 0.3.3

### Fixed

- Anchor sensor deadlines to the start of the run so wake-up jitter does not skip
  default-rate samples or accumulate scheduling drift; skip missed slots after delays.
- Retain the latest dependency reading per device between sampling ticks, so
  faster PV and battery sensors can use slower irradiance and load sensors.
- Advance the single-stream CLI's temperature model with elapsed simulation time.
- Import CLI output helpers on Python 3.9 without evaluating unsupported union annotations.
- Correct API examples to use `noise_sigma` and show the output partition needed
  for per-type files.
- Keep runtime and distribution versions consistent through one version source.

### Changed

- Update supported development tooling and the optional PyYAML dependency; remove
  the unused NumPy dependency from contributor installation.
- Use a portable Makefile and include tests and development instructions in the sdist.
- Add explicit local Ruff configuration and apply a consistent format/import order.
- Test Python 3.9–3.15 in CI, with additional macOS and Windows jobs and validated
  package builds. Pin GitHub Actions to verified release commits.
- Replace weekly per-run Ruff branches with an optional manual workflow using one
  stable branch and validation before it creates changes.
- Group future Python and Actions dependency updates with Dependabot.

## [0.1.0] - 04-09-2025

### Added

- Initial release of `dummysensors`
- `TemperatureSensor` with configurable range and noise
- `VibrationSensor` with sinusoidal signal and noise
- CLI with two commands:
  - `generate` for a single temperature stream
  - `run` for multi-device, multi-sensor streams
- Output to JSONL (stdout or files, partitioned by sensor type)
- Simple `--spec` string format to describe devices and sensors
- Basic test suite (pytest)
- CI/CD GitHub Actions (tests + lint + build + publish via Trusted Publishing)

## [0.2.0] - 2025-09-04

### Added

- CSV writer (header, line-buffering).
- `--partition-by device|type|none`.
- YAML config: `dummy-sensors run --config config.yaml`.
- Autodiscovery: `config.sensors.yaml` (preferred), also `dummysensors.yaml|yml`, `config.yaml|yml`.
- Tests: config discovery, CSV writer.

### Changed

- `publish.yml` stabilizowany pod Trusted Publishing.

## [0.3.0] - 2025-09-06



### Added

- PV/energy sensors: `irradiance`, `pv_power`, `load`, `soc`.
- Context-aware orchestration: per-tick device context (e.g. irradiance → pv_power → load → soc).
- Per-sensor `rate_hz` (optional) and `priority` (optional) in YAML.
- `params` block for sensors in YAML (tunable models: peaks, capacities, etc.).
- Tests: PV pipeline (day/night), SoC integration, per-sensor rate.

### Changed

- Orchestrator supports dependency order and per-sensor scheduling while remaining backward compatible with existing `--spec` and YAML without `params`.
- PV power noise can be configured; recommends `noise_sigma: 0.0` for strict night zeros.

### Fixed

- Minor pacing stability when sleeping to the next tick.

[0.3.0]: https://github.com/SculptTechProject/dummysensors/releases/tag/v0.3.0

[0.2.0]: https://github.com/SculptTechProject/dummysensors/releases/tag/v0.2.0

[0.1.0]: https://github.com/SculptTechProject/dummysensors/releases/tag/v0.1.0

