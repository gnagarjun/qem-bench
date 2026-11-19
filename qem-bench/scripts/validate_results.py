#!/usr/bin/env python
"""Validate raw runs and aggregated outputs (completeness, accounting, figure provenance).

python scripts/validate_results.py --agg results/aggregated/standard
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from qem_bench.config import ExperimentConfig
from qem_bench.experiments.validation import validate_run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agg", required=True)
    ap.add_argument("--figures", default="results/figures")
    args = ap.parse_args(argv)
    agg = Path(args.agg)
    man = json.loads((agg / "manifest.json").read_text())
    ok = True
    for entry in man["aggregated_from"]:
        run = next(Path("results").rglob(entry["run"]))
        for name, digest in entry["raw_files"].items():
            if hashlib.sha256((run / "raw" / name).read_bytes()).hexdigest() != digest:
                print("raw file changed since aggregation:", name)
                ok = False
        cfg = ExperimentConfig(**json.loads((run / "config_resolved.json").read_text())["config"])
        rep = validate_run(run, cfg)
        print(entry["run"], "dataset validation:", rep["passed"])
        ok &= rep["passed"]
    for name, digest in man["outputs"].items():
        if hashlib.sha256((agg / name).read_bytes()).hexdigest() != digest:
            print("aggregated output modified:", name)
            ok = False
    figs = Path(args.figures) / "figures.json"
    if figs.exists():
        idx = json.loads(figs.read_text())
        missing = [f["png"] for f in idx if not (Path(args.figures) / f["png"]).exists()]
        print(f"figures indexed: {len(idx)}, missing: {missing}")
        ok &= not missing and len(idx) == 12
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
