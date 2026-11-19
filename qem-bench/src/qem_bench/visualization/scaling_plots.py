"""Scaling figures: depth (2), noise intensity (3), shot budget (6), ZNE scale factor (11)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from qem_bench.mitigation.zne import extrapolation_weights
from qem_bench.visualization.style import DOUBLE, METHOD_COLORS, METHOD_LABELS, METHOD_MARKERS, METHODS, save


def depth_vs_error(agg: pd.DataFrame, circuits: pd.DataFrame, out: Path) -> list[Path]:
    c1 = circuits[(circuits.scale_nominal == 1.0)].groupby("instance").agg(n2q=("folded_n_2q", "max")).reset_index()
    a = agg[(agg.block == "core") & agg.primary_observable & (agg.comparison == "A")
            & (agg.shots_per_circuit == agg.shots_per_circuit.max())].merge(c1, on="instance")
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=True)
    for ax, noise in zip(axes, ("low", "moderate", "high"), strict=True):
        for m in METHODS:
            s = a[(a.noise == noise) & (a.method == m)].sort_values("n2q")
            ax.errorbar(s.n2q, s.rmse, yerr=[s.rmse - s.rmse_ci_lo, s.rmse_ci_hi - s.rmse], fmt=METHOD_MARKERS[m],
                        ms=3, lw=0.6, color=METHOD_COLORS[m], label=METHOD_LABELS[m], alpha=0.85)
        ax.set(xscale="log", yscale="log", title=f"{noise} noise", xlabel="two-qubit gates per setting")
    axes[0].set_ylabel("RMSE (primary observable)")
    axes[2].legend(fontsize=5.5)
    fig.suptitle("Circuit size/depth vs estimation error (core grid, comparison A, N = 16384)", fontsize=8)
    return save(fig, out, "fig02_depth_vs_error")


def noise_vs_error(agg: pd.DataFrame, out: Path) -> list[Path]:
    blocks = (("gate_sweep", "gate_multiplier", "gate-noise multiplier (x moderate)"),
              ("readout_sweep", "readout_multiplier", "readout-noise multiplier (x moderate)"))
    insts = sorted(agg[agg.block == "gate_sweep"].instance.unique())
    fig, axes = plt.subplots(2, len(insts), figsize=(7.2, 4.4), sharex="row")
    for r, (blk, col, lab) in enumerate(blocks):
        for j, inst in enumerate(insts):
            ax = axes[r, j]
            a = agg[(agg.block == blk) & (agg.instance == inst) & agg.primary_observable & (agg.comparison == "A")]
            for m in METHODS:
                s = a[a.method == m].sort_values(col)
                ax.plot(s[col], s.rmse, marker=METHOD_MARKERS[m], ms=2.5, lw=0.8, color=METHOD_COLORS[m],
                        label=METHOD_LABELS[m])
                ax.fill_between(s[col], s.rmse_ci_lo, s.rmse_ci_hi, color=METHOD_COLORS[m], alpha=0.12, lw=0)
            ax.set_yscale("log")
            ax.set_title(inst, fontsize=7)
            ax.set_xlabel(lab if j == 0 else "multiplier", fontsize=6.5)
            ax.yaxis.set_minor_formatter(plt.NullFormatter())
        axes[r, 0].set_ylabel("RMSE (log)")
    axes[0, -1].legend(fontsize=5)
    fig.suptitle("Sensitivity sweeps (N = 4096, comparison A; bands: 95% bootstrap CI)", fontsize=8)
    return save(fig, out, "fig03_noise_vs_error")


def shots_vs_rmse(agg: pd.DataFrame, out: Path, noise: str = "moderate",
                  insts: tuple[str, ...] = ("bell_cx", "ghz_4", "ghz_8", "qaoa_n4_p1")) -> list[Path]:
    fig, axes = plt.subplots(2, len(insts), figsize=(7.2, 4.2), sharex=True)
    for r, comp in enumerate(("A", "B")):
        for j, inst in enumerate(insts):
            ax = axes[r, j]
            a = agg[(agg.block == "core") & (agg.instance == inst) & agg.primary_observable & (agg.noise == noise)
                    & (agg.comparison == comp)]
            for m in METHODS:
                s = a[a.method == m].sort_values("shots_per_circuit")
                ax.plot(s.shots_per_circuit, s.rmse, marker=METHOD_MARKERS[m], ms=2.5, lw=0.8,
                        color=METHOD_COLORS[m], label=METHOD_LABELS[m])
                ax.fill_between(s.shots_per_circuit, s.rmse_ci_lo, s.rmse_ci_hi, color=METHOD_COLORS[m], alpha=0.12, lw=0)
            n = np.array(sorted(a.shots_per_circuit.unique()), float)
            if len(n):
                ax.plot(n, 1 / np.sqrt(n), "k:", lw=0.6, label=r"$1/\sqrt{N}$")
            ax.set(xscale="log", yscale="log", title=f"{inst} [{comp}]")
            if r == 1:
                ax.set_xlabel("shots per circuit N")
        axes[r, 0].set_ylabel(f"RMSE, comparison {comp}")
    axes[0, -1].legend(fontsize=5)
    fig.suptitle(f"Shot budget vs RMSE ({noise} noise; B = equal total budget incl. calibration and scale points)",
                 fontsize=8)
    return save(fig, out, "fig06_shots_vs_rmse")


def zne_scale_factor(zpts: pd.DataFrame, agg: pd.DataFrame, out: Path) -> list[Path]:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
    z = zpts[(zpts.block == "core") & (zpts.shots_per_circuit == 16384)]
    for ax, (inst, obs) in zip(axes[:2], (("ghz_4", "X_all"), ("qaoa_n4_p1", "cost_norm")), strict=True):
        for noise, ls in (("moderate", "-"), ("high", "--")):
            s = z[(z.instance == inst) & (z.observable == obs) & (z.noise == noise)]
            g = s.groupby("scale").agg(raw=("raw", "mean"), ro=("readout_corrected", "mean"), ideal=("ideal", "first"))
            sc = g.index.to_numpy()
            for col, colr, lab in (("raw", METHOD_COLORS["baseline"], "raw"), ("ro", METHOD_COLORS["readout"], "REM")):
                ax.plot(sc, g[col], "o" + ls, ms=3, lw=0.8, color=colr, label=f"{lab} ({noise})")
                xs = np.linspace(0, sc.max(), 50)
                fit = np.polyfit(sc, g[col], 1)
                ax.plot(xs, np.polyval(fit, xs), ls, lw=0.4, color=colr, alpha=0.6)
                ax.plot(0, extrapolation_weights(sc, "richardson") @ g[col].to_numpy(), "*", ms=5, color=colr)
            ax.axhline(g.ideal.iloc[0], color="black", lw=0.6)
        ax.set(xlabel="noise scale factor $\\lambda$ (global folding)", ylabel=f"<{obs}>", title=f"{inst}, N = 16384")
        ax.set_xlim(-0.3, None)
    axes[1].legend(fontsize=5)
    ax = axes[2]
    zb = agg[agg.block.str.startswith("zne_") | (agg.block == "core")]
    zb = zb[zb.instance.isin(["ghz_4", "ghz_6", "qaoa_n4_p1"]) & zb.noise.isin(["moderate", "high"])
            & zb.primary_observable & (zb.comparison == "A") & (zb.shots_per_circuit == 4096)
            & zb.method.isin(["zne_linear", "zne_richardson"])]
    zb = zb.assign(design=zb.folding + " " + zb.scale_factors.map(lambda s: ",".join(f"{x:g}" for x in json.loads(s))))
    piv = zb.groupby(["design", "method"]).rel_rmse_change.median().unstack()
    piv.mul(100).plot.bar(ax=ax, color=[METHOD_COLORS[c] for c in piv.columns], width=0.7, legend=False)
    ax.axhline(0, color="black", lw=0.6)
    ax.set(ylabel="median RMSE change vs baseline (%)", xlabel="", title="ZNE design (N = 4096, A)")
    ax.tick_params(axis="x", rotation=30)
    fig.suptitle("Expectation value vs scale factor (lines: linear fit, stars: Richardson) and ZNE design choices",
                 fontsize=8)
    return save(fig, out, "fig11_zne_scale_factor")


__all__ = ["DOUBLE", "depth_vs_error", "noise_vs_error", "shots_vs_rmse", "zne_scale_factor"]
