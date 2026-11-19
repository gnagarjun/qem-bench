#!/usr/bin/env python
"""Run the pilot profile (per-shot Aer vs exact sampling; timing study) and analyse it."""

from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import analyze_results  # noqa: E402
import run_experiment  # noqa: E402

if __name__ == "__main__":
    run = run_experiment.main(["--profile", "pilot"])
    analyze_results.main(["--run", str(run), "--out", "results/aggregated/pilot"])
