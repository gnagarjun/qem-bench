"""Paired method comparisons with effect sizes, FDR control and efficiency metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qem_bench.analysis.aggregation import COND_KEYS
from qem_bench.config import AnalysisSpec
from qem_bench.metrics.efficiency import improvement_factor, resource_efficiency, work_normalized_mse_ratio
from qem_bench.metrics.statistics import benjamini_hochberg, holm, paired_bootstrap_diff, wilcoxon_signed_rank

DEFAULT_PAIRS = [
    ("readout", "baseline"), ("zne_linear", "baseline"), ("zne_richardson", "baseline"),
    ("combined_linear", "baseline"), ("combined_richardson", "baseline"),
    ("combined_linear", "readout"), ("combined_linear", "zne_linear"),
    ("combined_richardson", "readout"), ("combined_richardson", "zne_richardson"),
]


def paired_comparisons(df: pd.DataFrame, spec: AnalysisSpec, pairs=DEFAULT_PAIRS, seed: int = 1) -> pd.DataFrame:
    """Per condition and comparison mode: method vs reference, paired by repetition.

    In comparison A all methods share the same samples (common random numbers);
    in comparison B samples are independent across methods but paired by repetition index.
    Test: two-sided Wilcoxon signed-rank on absolute errors; effect size: matched-pairs
    rank-biserial r (negative = method has smaller errors); CI: paired bootstrap of the
    MSE difference. q-values: Benjamini-Hochberg over every test in the returned table.
    """
    rng = np.random.default_rng(seed)
    ok = df[df.status == "ok"]
    out = []
    for key, g in ok.groupby([*COND_KEYS, "comparison"], sort=True, dropna=False):
        sq = g.pivot_table(index="repetition", columns="method", values="sq_error")
        ab = g.pivot_table(index="repetition", columns="method", values="abs_error")
        cost = g.groupby("method").total_shots.mean()
        for m, r in pairs:
            if m not in sq or r not in sq:
                continue
            both = sq[[m, r]].dropna().index
            d, lo, hi = paired_bootstrap_diff(sq.loc[both, m], sq.loc[both, r], spec.bootstrap_samples,
                                              spec.confidence_level, rng)
            p, rb = wilcoxon_signed_rank(ab.loc[both, m].to_numpy(), ab.loc[both, r].to_numpy())
            e_m, e_r = float(np.sqrt(sq.loc[both, m].mean())), float(np.sqrt(sq.loc[both, r].mean()))
            eta, cat = resource_efficiency(e_r, e_m, float(cost[r]), float(cost[m]))
            out.append({**dict(zip([*COND_KEYS, "comparison"], key, strict=True)), "method": m, "reference": r,
                        "n_pairs": len(both), "rmse_method": e_m, "rmse_reference": e_r,
                        "rel_rmse_change": (e_m - e_r) / e_r if e_r > 0 else np.nan,
                        "mse_diff": d, "mse_diff_ci_lo": lo, "mse_diff_ci_hi": hi,
                        "p_wilcoxon": p, "rank_biserial": rb,
                        "cost_method": float(cost[m]), "cost_reference": float(cost[r]),
                        "eta": eta, "eta_category": cat,
                        "improvement_factor_mu": improvement_factor(e_r, e_m, float(cost[r]), float(cost[m])),
                        "wnmse_ratio": work_normalized_mse_ratio(e_r**2, e_m**2, float(cost[r]), float(cost[m]))})
    res = pd.DataFrame(out)
    if res.empty:
        return res
    res["q_bh"] = benjamini_hochberg(res.p_wilcoxon.to_numpy())
    res["p_holm"] = holm(res.p_wilcoxon.to_numpy())
    sig = res.q_bh < spec.alpha
    practical = res.rel_rmse_change.abs() >= spec.practical_threshold
    res["outcome"] = np.select(
        [sig & (res.rel_rmse_change < 0) & practical, sig & (res.rel_rmse_change < 0),
         sig & (res.rel_rmse_change > 0) & practical, sig & (res.rel_rmse_change > 0)],
        ["better_practical", "better_marginal", "worse_practical", "worse_marginal"], default="no_significant_difference")
    return res
