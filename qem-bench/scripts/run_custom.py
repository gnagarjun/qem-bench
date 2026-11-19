#!/usr/bin/env python
"""Run a user-defined design (from the web viewer) and analyse it.

python scripts/run_custom.py --spec spec.json --out results/custom_runs/<id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyze_results  # noqa: E402

from qem_bench.config import ExperimentConfig, load_config  # noqa: E402
from qem_bench.experiments.design import design_summary  # noqa: E402
from qem_bench.experiments.runner import run_experiment  # noqa: E402
from qem_bench.experiments.validation import validate_run  # noqa: E402


def build_config(spec: dict, config_dir: str) -> ExperimentConfig:
    base = load_config("smoke", config_dir).model_dump(mode="json")
    block = {"name": "custom", "purpose": spec.get("name") or "custom run from the web viewer",
             "instances": spec["instances"], "noise": spec["noise"], "shots": spec["shots"],
             "methods": spec["methods"], "comparisons": spec["comparisons"], "zne": spec["zne"]}
    base.update(profile="custom", seed=int(spec["seed"]), repetitions=int(spec["repetitions"]), blocks=[block])
    return ExperimentConfig.model_validate(base)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config-dir", default="configs")
    a = ap.parse_args()
    out = Path(a.out)
    cfg = build_config(json.loads(Path(a.spec).read_text()), a.config_dir)
    print("design:", json.dumps(design_summary(cfg)), flush=True)
    run_dir = run_experiment(cfg, out / "raw_runs")
    report = validate_run(run_dir, cfg)
    print("validation passed:", report["passed"], flush=True)
    if not report["passed"]:
        raise SystemExit(f"dataset validation failed: {json.dumps(report)}")
    print("analysing", flush=True)
    analyze_results.main(["--run", str(run_dir), "--out", str(out / "analysis")])
    print("done", flush=True)


if __name__ == "__main__":
    main()
