"""Figure 9: Pareto frontiers of RMSE vs total shots."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from qem_bench.visualization.style import METHOD_COLORS, METHOD_LABELS, METHOD_MARKERS, METHODS, save


def pareto_figure(par: pd.DataFrame, out: Path,
                  panels: tuple[tuple[str, str], ...] = (("bell_cx", "moderate"), ("ghz_4", "moderate"),
                                                         ("ghz_8", "high"), ("qaoa_n4_p1", "moderate"),
                                                         ("qaoa_n6_p2", "high"), ("ghz_6", "low"))) -> list[Path]:
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.6))
    for ax, (inst, noise) in zip(axes.flat, panels, strict=True):
        p = par[(par.block == "core") & (par.instance == inst) & (par.noise == noise) & par.primary_observable
                & (par.comparison == "A")]
        for m in METHODS:
            s = p[p.method == m]
            ax.scatter(s.total_shots, s.rmse, s=10, marker=METHOD_MARKERS[m], color=METHOD_COLORS[m],
                       label=METHOD_LABELS[m], alpha=0.85)
        f = p[p.pareto_optimal].sort_values("total_shots")
        ax.step(f.total_shots, f.rmse, where="post", color="black", lw=0.8, label="Pareto frontier")
        ax.set(xscale="log", yscale="log", title=f"{inst}, {noise}", xlabel="total shots", ylabel="RMSE")
    axes[0, 0].legend(fontsize=5)
    fig.suptitle("Pareto frontiers over methods x shot budgets (comparison A accounting)", fontsize=8)
    return save(fig, out, "fig09_pareto_frontier")
