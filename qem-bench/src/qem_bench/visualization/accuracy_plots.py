"""Accuracy figures: method comparison (4), family comparison (7), CIs (10), combined vs individual (12)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from qem_bench.visualization.style import DOUBLE, METHOD_COLORS, METHOD_LABELS, METHODS, save


def method_comparison(agg: pd.DataFrame, out: Path, shots: int = 4096, noise: str = "moderate") -> list[Path]:
    a = agg[(agg.block == "core") & agg.primary_observable & (agg.shots_per_circuit == shots) & (agg.noise == noise)]
    insts = list(dict.fromkeys(a.sort_values(["family", "n_qubits"]).instance))
    fig, axes = plt.subplots(1, 2, figsize=DOUBLE, sharey=True)
    w = 0.8 / len(METHODS)
    for ax, comp in zip(axes, ("A", "B"), strict=True):
        for k, m in enumerate(METHODS):
            s = a[(a.comparison == comp) & (a.method == m)].set_index("instance").reindex(insts)
            x = np.arange(len(insts)) + (k - len(METHODS) / 2 + 0.5) * w
            ax.bar(x, s.rmse, w, color=METHOD_COLORS[m], label=METHOD_LABELS[m],
                   yerr=[s.rmse - s.rmse_ci_lo, s.rmse_ci_hi - s.rmse], error_kw={"lw": 0.5, "capsize": 0})
        ax.set_xticks(range(len(insts)), insts, rotation=60, ha="right")
        ax.set_title(f"Comparison {comp}: " + ("equal primary shots" if comp == "A" else "equal total budget"))
        ax.set_yscale("log")
    axes[0].set_ylabel("RMSE of primary observable (log scale)")
    axes[1].legend(ncol=2, loc="upper right")
    fig.suptitle(f"Core grid, {noise} noise, N = {shots} shots/circuit; bars: 95% bootstrap CI", fontsize=8)
    return save(fig, out, "fig04_method_comparison")


def family_comparison(cmp: pd.DataFrame, out: Path, shots: int = 4096) -> list[Path]:
    c = cmp[(cmp.block == "core") & (cmp.reference == "baseline") & (cmp.shots_per_circuit == shots)]
    fams = ["bell", "ghz", "qaoa"]
    ms = METHODS[1:]
    fig, axes = plt.subplots(1, 2, figsize=DOUBLE, sharey=True)
    for ax, comp in zip(axes, ("A", "B"), strict=True):
        for fi, fam in enumerate(fams):
            for k, m in enumerate(ms):
                v = c[(c.comparison == comp) & (c.family == fam) & (c.method == m)].rel_rmse_change * 100
                x = fi + (k - len(ms) / 2 + 0.5) * 0.16
                bp = ax.boxplot(v.dropna(), positions=[x], widths=0.13, patch_artist=True, showfliers=False)
                for patch in bp["boxes"]:
                    patch.set(facecolor=METHOD_COLORS[m], alpha=0.8, lw=0.5)
                for el in ("whiskers", "caps", "medians"):
                    for line in bp[el]:
                        line.set(lw=0.6, color="black")
        ax.axhline(0, color="black", lw=0.7)
        ax.set_xticks(range(3), ["Bell", "GHZ", "QAOA"])
        ax.set_title(f"Comparison {comp}")
    axes[0].set_ylabel("RMSE change vs baseline (%)  [<0 = better]")
    handles = [plt.Rectangle((0, 0), 1, 1, fc=METHOD_COLORS[m]) for m in ms]
    axes[1].legend(handles, [METHOD_LABELS[m] for m in ms], fontsize=6)
    fig.suptitle(f"Distribution over instances, observables and noise levels (N = {shots})", fontsize=8)
    return save(fig, out, "fig07_family_comparison")


def confidence_intervals(cmp: pd.DataFrame, out: Path, shots: int = 4096, noise: str = "moderate") -> list[Path]:
    c = cmp[(cmp.block == "core") & (cmp.reference == "baseline") & (cmp.shots_per_circuit == shots)
            & (cmp.noise == noise) & cmp.primary_observable]
    insts = list(dict.fromkeys(c.sort_values(["family", "n_qubits"]).instance))
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.0), sharey=True)
    for ax, comp in zip(axes, ("A", "B"), strict=True):
        for k, m in enumerate(METHODS[1:]):
            s = c[(c.comparison == comp) & (c.method == m)].set_index("instance").reindex(insts)
            y = np.arange(len(insts)) + (k - 2) * 0.14
            sig = s.q_bh < 0.05
            ax.errorbar(s.mse_diff, y, xerr=[s.mse_diff - s.mse_diff_ci_lo, s.mse_diff_ci_hi - s.mse_diff], fmt="none",
                        ecolor=METHOD_COLORS[m], lw=0.8)
            ax.scatter(s.mse_diff, y, s=10, color=METHOD_COLORS[m], edgecolor="black",
                       linewidths=np.where(sig, 0.6, 0), label=METHOD_LABELS[m], zorder=3)
        ax.axvline(0, color="black", lw=0.7)
        ax.set_xscale("symlog", linthresh=1e-4)
        ax.set_yticks(range(len(insts)), insts)
        ax.set_xlabel("MSE(method) - MSE(baseline)  (symlog)")
        ax.set_title(f"Comparison {comp}")
    axes[1].legend(fontsize=6, loc="lower right")
    fig.suptitle(f"Paired bootstrap 95% CIs, {noise} noise, N = {shots}; outlined = BH q<0.05", fontsize=8)
    return save(fig, out, "fig10_confidence_intervals")


def combined_vs_individual(agg: pd.DataFrame, out: Path) -> list[Path]:
    a = agg[agg.block == "core"]
    keys = ["instance", "noise", "observable", "shots_per_circuit", "comparison"]
    p = a.pivot_table(index=keys, columns="method", values="rmse").reset_index()
    fig, axes = plt.subplots(1, 2, figsize=DOUBLE)
    for ax, (comb, zne) in zip(axes, (("combined_linear", "zne_linear"), ("combined_richardson", "zne_richardson")),
                               strict=True):
        best = np.minimum(p["readout"], p[zne])
        for comp, mk in (("A", "o"), ("B", "x")):
            s = p.comparison == comp
            ax.scatter(best[s], p.loc[s, comb], s=6, marker=mk, alpha=0.6, color=METHOD_COLORS[comb],
                       label=f"Comparison {comp}")
        lim = [min(best.min(), p[comb].min()) * 0.8, max(best.max(), p[comb].max()) * 1.2]
        ax.plot(lim, lim, "k--", lw=0.7)
        ax.set(xscale="log", yscale="log", xlabel=f"min(RMSE REM, RMSE {METHOD_LABELS[zne]})",
               ylabel=f"RMSE {METHOD_LABELS[comb]}", title=f"{METHOD_LABELS[comb]} vs best single method")
        ax.legend()
    fig.suptitle("Below the diagonal: combination beats the better individual method (all core conditions)", fontsize=8)
    return save(fig, out, "fig12_combined_vs_individual")
