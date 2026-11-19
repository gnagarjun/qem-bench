#!/usr/bin/env python
"""Run an experiment profile: python scripts/run_experiment.py --profile standard [--resume RUN_DIR]."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qem_bench.config import load_config
from qem_bench.experiments.design import design_summary
from qem_bench.experiments.runner import run_experiment
from qem_bench.experiments.validation import validate_run


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--config-dir", default="configs")
    ap.add_argument("--out", default=None, help="output root (default results/<pilot|experiments>)")
    ap.add_argument("--resume", default=None, help="existing run directory to resume")
    args = ap.parse_args(argv)
    cfg = load_config(args.profile, args.config_dir)
    print("design:", json.dumps(design_summary(cfg)))
    out = args.out or ("results/pilot" if args.profile in ("pilot", "smoke") else "results/experiments")
    run_dir = run_experiment(cfg, out, resume=args.resume)
    report = validate_run(run_dir, cfg)
    print("run:", run_dir)
    print("validation passed:", report["passed"])
    if not report["passed"]:
        raise SystemExit(f"dataset validation failed: {json.dumps(report, indent=2)}")
    return run_dir


if __name__ == "__main__":
    main()
