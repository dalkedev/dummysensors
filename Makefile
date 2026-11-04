PYTHON ?= python3
VENV ?= .venv
ifeq ($(OS),Windows_NT)
PY := $(VENV)/Scripts/python.exe
else
PY := $(VENV)/bin/python
endif

.PHONY: venv install test lint format build check clean demo demo-clean

venv:
	@$(PYTHON) -c "import os, venv; venv.create('$(VENV)', with_pip=True) if not os.path.isdir('$(VENV)') else None"

install: venv
	@$(PY) -c "import importlib.util, subprocess, sys; subprocess.check_call([sys.executable, '-m', 'ensurepip', '--upgrade']) if importlib.util.find_spec('pip') is None else None"
	@$(PY) -m pip install --upgrade pip
	@$(PY) -m pip install -e ".[config,dev]"

test:
	@$(PY) -m pytest -q

lint:
	@$(PY) -m ruff check .
	@$(PY) -m ruff format --check .

format:
	@$(PY) -m ruff check --fix .
	@$(PY) -m ruff format .

build:
	@$(PY) -m build
	@$(PY) -m twine check --strict dist/*

check: lint test build

clean:
	@$(PY) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('build', 'dist', '.pytest_cache', '.ruff_cache')]"

demo-clean:
	@$(PY) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('out', 'demo_out')]"

# Two sensor types, two devices, two output files and a stdout fallback.
demo:
	@$(PY) -c "from dummysensors.cli import main; main(['run', '--rate', '5', '--count', '30', '--partition-by', 'type', '--spec', 'device=engine-A: temp*1,vibration*2; device=room-101: temp*2', '--out', 'temp=demo_out/temp.jsonl', '--out', 'vibration=demo_out/vibration.jsonl', '--out', '*=stdout'])"
