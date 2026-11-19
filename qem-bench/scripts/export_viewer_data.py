#!/usr/bin/env python
"""Export a read-only data bundle for the web results viewer (no computation, only selection/copy).

python scripts/export_viewer_data.py --std results/aggregated/standard --pilot results/aggregated/pilot \
    --figures results/figures --out ../backend/viewer_data
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

AGG_COLS = ["block", "instance", "family", "n_qubits", "noise", "gate_multiplier", "readout_multiplier", "folding", "scale_factors",
            "shots_per_circuit", "observable", "primary_observable", "comparison", "method", "n_reps", "n_failed", "ideal", "mean",
            "sd", "bias", "variance", "rmse", "rmse_ci_lo", "rmse_ci_hi", "mae", "total_shots", "calibration_shots",
            "sampling_overhead", "rel_rmse_change", "readout_cond", "zne_gamma_l1", "variance_ratio"]
CMP_COLS = ["block", "instance", "family", "noise", "shots_per_circuit", "observable", "primary_observable", "comparison", "method",
            "reference", "n_pairs", "rmse_method", "rmse_reference", "rel_rmse_change", "mse_diff", "mse_diff_ci_lo", "mse_diff_ci_hi",
            "p_wilcoxon", "q_bh", "p_holm", "rank_biserial", "eta", "eta_category", "improvement_factor_mu", "outcome",
            "cost_method", "cost_reference"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--std", required=True)
    ap.add_argument("--pilot", required=True)
    ap.add_argument("--figures", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    std, pilot = Path(a.std), Path(a.pilot)
    pd.read_csv(std / "aggregated.csv")[AGG_COLS].to_csv(out / "aggregated.csv", index=False)
    pd.read_csv(std / "comparisons.csv")[CMP_COLS].to_csv(out / "comparisons.csv", index=False)
    par = pd.read_csv(std / "pareto.csv")
    par[["block", "instance", "noise", "observable", "primary_observable", "comparison", "method", "shots_per_circuit",
         "total_shots", "rmse", "rmse_ci_lo", "rmse_ci_hi", "pareto_optimal"]].to_csv(out / "pareto.csv", index=False)
    shutil.copy(std / "summary.json", out / "summary_standard.json")
    shutil.copy(pilot / "summary.json", out / "summary_pilot.json")
    shutil.copy(pilot / "timing_study.csv", out / "timing_study.csv")
    shutil.copy(std / "manifest.json", out / "manifest_standard.json")
    figs = Path(a.figures)
    shutil.copy(figs / "figures.json", out / "figures" / "figures.json")
    for f in json.loads((figs / "figures.json").read_text()):
        shutil.copy(figs / f["png"], out / "figures" / f["png"])
    print("viewer bundle written to", out)


if __name__ == "__main__":
    main()
