PY ?= python
PILOT = $(shell ls -d results/pilot/pilot_* 2>/dev/null | tail -n 1)
STD = $(shell ls -d results/experiments/standard_* 2>/dev/null | tail -n 1)

.PHONY: install test test-fast lint typecheck smoke pilot standard analyze figures validate reproduce docs

install:
	uv sync --extra dev
test:
	$(PY) -m pytest
test-fast:
	$(PY) -m pytest tests/unit
lint:
	$(PY) -m ruff check src tests scripts
typecheck:
	$(PY) -m mypy
smoke:
	$(PY) scripts/run_experiment.py --profile smoke
pilot:
	$(PY) scripts/run_pilot.py
standard:
	$(PY) scripts/run_experiment.py --profile standard
analyze:
	$(PY) scripts/analyze_results.py --run $(PILOT) --out results/aggregated/pilot
	$(PY) scripts/analyze_results.py --run $(STD) --out results/aggregated/standard
figures:
	$(PY) scripts/generate_figures.py --agg results/aggregated/standard --out results/figures --copy-to paper/figures
validate:
	$(PY) scripts/validate_results.py --agg results/aggregated/standard
reproduce:
	PYTHON=$(PY) bash scripts/reproduce_all.sh
docs:
	mkdocs build
