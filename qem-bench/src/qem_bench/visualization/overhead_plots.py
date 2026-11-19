"""Figure 5: sampling overhead vs accuracy improvement."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from qem_bench.visualization.style import DOUBLE, METHOD_COLORS, METHOD_LABELS, METHOD_MARKERS, METHODS, save


def overhead_vs_improvement(agg: pd.DataFrame, out: Path) -> list[Path]:
    a = agg[(agg.block == "core") & (agg.comparison == "A") & (agg.method != "baseline")]
    fig, axes = plt.subplots(1, 2, figsize=DOUBLE)
    for m in METHODS[1:]:
        s = a[a.method == m]
        axes[0].scatter(s.sampling_overhead, -100 * s.rel_rmse_change, s=5, alpha=0.5, color=METHOD_COLORS[m],
                        marker=METHOD_MARKERS[m], label=METHOD_LABELS[m])
    axes[0].axhline(0, color="black", lw=0.6)
    axes[0].set(xscale="log", xlabel="sampling overhead $O = N_{mit}/N_{base}$ (total shots)",
                ylabel="RMSE reduction vs baseline (%)", title="Comparison A (all core conditions)")
    axes[0].legend(fontsize=5.5)
    med = a.groupby(["method", "shots_per_circuit"]).rel_rmse_change.median().unstack(0) * -100
    for m in med.columns:
        axes[1].plot(med.index, med[m], marker=METHOD_MARKERS[m], ms=3, color=METHOD_COLORS[m], label=METHOD_LABELS[m])
    axes[1].axhline(0, color="black", lw=0.6)
    axes[1].set(xscale="log", xlabel="shots per circuit N", ylabel="median RMSE reduction (%)",
                title="Median over instances/observables/noise")
    return save(fig, out, "fig05_overhead_vs_improvement")


__all__ = ["overhead_vs_improvement", "plt"]
