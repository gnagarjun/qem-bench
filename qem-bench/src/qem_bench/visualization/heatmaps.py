"""Figure 8: resource-efficiency heatmaps."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from qem_bench.visualization.style import METHOD_LABELS, METHODS, save


def efficiency_heatmap(cmp: pd.DataFrame, out: Path, shots: int = 4096) -> list[Path]:
    c = cmp[(cmp.block == "core") & (cmp.reference == "baseline") & (cmp.shots_per_circuit == shots)]
    order = list(dict.fromkeys(c.sort_values(["family", "n_qubits"]).instance))
    cols = [METHOD_LABELS[m] for m in METHODS[1:]]
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 6.0), sharey=True)
    for j, noise in enumerate(("low", "moderate", "high")):
        a = c[(c.comparison == "A") & (c.noise == noise)]
        eta = a.assign(eta=np.clip(a.eta.replace([np.inf, -np.inf], np.nan), -1, 1)).pivot_table(
            index="instance", columns="method", values="eta", aggfunc="median").reindex(order)[METHODS[1:]]
        sns.heatmap(eta.set_axis(cols, axis=1), ax=axes[0, j], cmap="RdBu", vmin=-0.5, vmax=0.5, center=0,
                    annot=True, fmt=".2f", annot_kws={"size": 5}, cbar=j == 2,
                    cbar_kws={"label": r"$\eta$ (clipped to [-1,1])"})
        axes[0, j].set_title(f"A: efficiency $\\eta$, {noise}")
        b = c[(c.comparison == "B") & (c.noise == noise)]
        rel = b.pivot_table(index="instance", columns="method", values="rel_rmse_change",
                            aggfunc="median").reindex(order)[METHODS[1:]] * -100
        sns.heatmap(rel.set_axis(cols, axis=1), ax=axes[1, j], cmap="RdBu", vmin=-100, vmax=100, center=0,
                    annot=True, fmt=".0f", annot_kws={"size": 5}, cbar=j == 2,
                    cbar_kws={"label": "RMSE reduction at equal budget (%)"})
        axes[1, j].set_title(f"B: RMSE reduction (%), {noise}")
        for r in range(2):
            axes[r, j].tick_params(axis="x", rotation=60, labelsize=6)
            axes[r, j].set_xlabel("")
            axes[r, j].set_ylabel("")
    fig.suptitle(f"Resource efficiency (median over observables, N = {shots}); blue = favourable to mitigation",
                 fontsize=8)
    return save(fig, out, "fig08_efficiency_heatmap")
