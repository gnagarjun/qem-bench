#!/usr/bin/env python
"""Generate all publication figures from saved aggregated data (never from hand-entered values).

python scripts/generate_figures.py --agg results/aggregated/standard --out results/figures --copy-to paper/figures
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from qem_bench.visualization.accuracy_plots import (
    combined_vs_individual,
    confidence_intervals,
    family_comparison,
    method_comparison,
)
from qem_bench.visualization.architecture import architecture_figure
from qem_bench.visualization.heatmaps import efficiency_heatmap
from qem_bench.visualization.overhead_plots import overhead_vs_improvement
from qem_bench.visualization.pareto_plots import pareto_figure
from qem_bench.visualization.scaling_plots import depth_vs_error, noise_vs_error, shots_vs_rmse, zne_scale_factor
from qem_bench.visualization.style import apply_style

CAPTIONS = {
    "fig01_architecture": "QEM-Bench pipeline: configuration, circuits, noise, execution, mitigation, accounting, analysis.",
    "fig02_depth_vs_error": "Two-qubit gate count vs RMSE of the primary observable (core grid, comparison A, N=16384).",
    "fig03_noise_vs_error": "Sensitivity sweeps: gate-noise (top) and readout-noise (bottom) multipliers vs RMSE.",
    "fig04_method_comparison": "RMSE of all methods per instance at moderate noise, N=4096, comparisons A and B.",
    "fig05_overhead_vs_improvement": "Sampling overhead vs RMSE reduction relative to baseline (comparison A).",
    "fig06_shots_vs_rmse": "Shots per circuit vs RMSE under equal primary shots (A) and equal total budget (B).",
    "fig07_family_comparison": "Relative RMSE change vs baseline by circuit family (N=4096).",
    "fig08_efficiency_heatmap": "Resource efficiency eta (A) and RMSE reduction at equal total budget (B).",
    "fig09_pareto_frontier": "Pareto frontiers of RMSE vs total shots across methods and shot budgets.",
    "fig10_confidence_intervals": "Paired bootstrap 95% CIs of MSE differences vs baseline (moderate noise, N=4096).",
    "fig11_zne_scale_factor": "Expectation values vs noise-scale factor with linear/Richardson extrapolation; ZNE designs.",
    "fig12_combined_vs_individual": "Combined mitigation vs the better of its two components, all core conditions.",
}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agg", required=True)
    ap.add_argument("--out", default="results/figures")
    ap.add_argument("--copy-to", default=None)
    args = ap.parse_args(argv)
    apply_style()
    agg_dir, out = Path(args.agg), Path(args.out)
    agg = pd.read_parquet(agg_dir / "aggregated.parquet")
    cmp = pd.read_parquet(agg_dir / "comparisons.parquet")
    par = pd.read_csv(agg_dir / "pareto.csv")
    circ = pd.read_csv(agg_dir / "circuits.csv")
    zpts = pd.read_parquet(agg_dir / "zne_points.parquet")
    made = []
    made += architecture_figure(out)
    made += depth_vs_error(agg, circ, out)
    made += noise_vs_error(agg, out)
    made += method_comparison(agg, out)
    made += overhead_vs_improvement(agg, out)
    made += shots_vs_rmse(agg, out)
    made += family_comparison(cmp, out)
    made += efficiency_heatmap(cmp, out)
    made += pareto_figure(par, out)
    made += confidence_intervals(cmp, out)
    made += zne_scale_factor(zpts, agg, out)
    made += combined_vs_individual(agg, out)
    index = [{"id": p.stem, "png": f"{p.stem}.png", "pdf": f"{p.stem}.pdf", "caption": CAPTIONS[p.stem],
              "source": str(agg_dir)} for p in made if p.suffix == ".png"]
    (out / "figures.json").write_text(json.dumps(index, indent=2))
    if args.copy_to:
        dst = Path(args.copy_to)
        dst.mkdir(parents=True, exist_ok=True)
        for p in made:
            shutil.copy(p, dst / p.name)
    print(f"generated {len(index)} figures in {out}")


if __name__ == "__main__":
    main()
