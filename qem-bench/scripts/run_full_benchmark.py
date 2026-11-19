#!/usr/bin/env python
"""Run the research-scale 'full' profile (100 repetitions, extended grid).

NOT executed for the reported study. The estimated cost is printed first; pass --yes to start.
The run can be resumed with --resume <run_dir>.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "scripts")
import run_experiment  # noqa: E402
from qem_bench.config import load_config  # noqa: E402
from qem_bench.experiments.design import design_summary  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--resume", default=None)
    a = ap.parse_args()
    print("full design:", design_summary(load_config("full")))
    if not a.yes:
        raise SystemExit("re-run with --yes to execute the full benchmark")
    run_experiment.main(["--profile", "full"] + (["--resume", a.resume] if a.resume else []))
