#!/usr/bin/env bash
# Complete reproduction of the reported study: pilot + reduced standard run, analysis, figures.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
$PY scripts/run_experiment.py --profile pilot
$PY scripts/analyze_results.py --run "$(ls -d results/pilot/pilot_* | tail -n 1)" --out results/aggregated/pilot
$PY scripts/run_experiment.py --profile standard
$PY scripts/analyze_results.py --run "$(ls -d results/experiments/standard_* | tail -n 1)" --out results/aggregated/standard
$PY scripts/generate_figures.py --agg results/aggregated/standard --out results/figures --copy-to paper/figures
$PY scripts/validate_results.py --agg results/aggregated/standard
mkdir -p paper/tables && cp results/aggregated/standard/tables/*.tex results/aggregated/pilot/tables/timing.tex paper/tables/
