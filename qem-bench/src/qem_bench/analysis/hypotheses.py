"""Pre-specified decision rules for hypotheses H1-H5 and the RQ6 ranking.

The rules are fixed in docs/research/hypotheses.md *before* inspecting results and are
applied mechanically; verdicts are SUPPORTED / PARTIALLY SUPPORTED / NOT SUPPORTED.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from qem_bench.metrics.statistics import spearman

ZNE = ["zne_linear", "zne_richardson"]
COMB = ["combined_linear", "combined_richardson"]
MITIG = ["readout", *ZNE, *COMB]


def _frac(mask: pd.Series) -> float:
    return float(mask.mean()) if len(mask) else float("nan")


def _verdict(frac: float, hi: float = 0.75, lo: float = 0.25) -> str:
    if not np.isfinite(frac):
        return "NOT TESTABLE"
    return "SUPPORTED" if frac >= hi else "PARTIALLY SUPPORTED" if frac >= lo else "NOT SUPPORTED"


def h1(cmp: pd.DataFrame, agg: pd.DataFrame) -> dict[str, Any]:
    c = cmp[(cmp.block == "readout_sweep") & (cmp.comparison == "A") & (cmp.method == "readout")
            & (cmp.reference == "baseline")]
    dom = c[c.readout_multiplier >= 1.0]
    a = agg[(agg.block == "readout_sweep") & (agg.comparison == "A")]
    piv = a.pivot_table(index=["instance", "observable", "noise", "readout_multiplier"], columns="method",
                        values="abs_bias").reset_index()
    pd_ = piv[piv.readout_multiplier >= 1.0]
    frac_sig = _frac(dom.outcome.str.startswith("better"))
    frac_bias = _frac(pd_["readout"] < pd_["baseline"])
    return {"rule": "readout sweep, comparison A, readout multiplier >= 1: fraction of conditions where readout "
                    "mitigation has significantly lower error (BH q<alpha) AND fraction with lower |bias|",
            "n_conditions": len(dom), "fraction_significantly_better": frac_sig,
            "fraction_lower_abs_bias": frac_bias, "verdict": _verdict(min(frac_sig, frac_bias))}


def h2(cmp: pd.DataFrame) -> dict[str, Any]:
    res = _h2_core(cmp)
    gs = cmp[(cmp.block == "gate_sweep") & (cmp.comparison == "A") & cmp.method.isin(ZNE) & (cmp.reference == "baseline")]
    res["exploratory_gate_sweep_median_rel_rmse_change"] = gs.groupby(["method", "gate_multiplier"]).rel_rmse_change.median().unstack(0).to_dict()
    res["noise_component_supported"] = bool(res["fraction_better_by_noise"].get("high", 1) <
                                            res["fraction_better_moderate_N>=4096"] - 0.2)
    return res


def _h2_core(cmp: pd.DataFrame) -> dict[str, Any]:
    c = cmp[(cmp.block == "core") & (cmp.comparison == "A") & cmp.method.isin(ZNE) & (cmp.reference == "baseline")]
    better = c.outcome.str.startswith("better")
    by_noise = {k: _frac(better[c.noise == k]) for k in ("low", "moderate", "high")}
    by_shots = {int(k): _frac(better[c.shots_per_circuit == k]) for k in sorted(c.shots_per_circuit.unique())}
    mod_hi = _frac(better[(c.noise == "moderate") & (c.shots_per_circuit >= 4096)])
    s_min = min(by_shots) if by_shots else None
    deterioration = (by_noise.get("high", np.nan) < mod_hi - 0.2) or (s_min is not None and by_shots[s_min] < mod_hi - 0.2)
    verdict = ("SUPPORTED" if mod_hi >= 0.5 and deterioration else
               "PARTIALLY SUPPORTED" if mod_hi >= 0.5 or deterioration else "NOT SUPPORTED")
    return {"rule": "core, comparison A: ZNE significantly better than baseline in >=50% of moderate-noise "
                    "conditions with N>=4096, AND the fraction drops by >=0.2 at high noise or at the lowest N",
            "fraction_better_moderate_N>=4096": mod_hi, "fraction_better_by_noise": by_noise,
            "fraction_better_by_shots": by_shots, "deterioration_observed": bool(deterioration), "verdict": verdict}


def h3(cmp: pd.DataFrame) -> dict[str, Any]:
    res = {}
    for comp in ("A", "B"):
        c = cmp[(cmp.block == "core") & (cmp.comparison == comp) & cmp.method.isin(COMB)]
        vs_ro = c[c.reference == "readout"].set_index([*_ck(), "method"])
        vs_z = c[c.reference.isin(ZNE)].set_index([*_ck(), "method"])
        j = vs_ro[["outcome", "cost_method", "cost_reference"]].join(
            vs_z[["outcome", "cost_reference"]], rsuffix="_zne", how="inner")
        both = j.outcome.str.startswith("better") & j.outcome_zne.str.startswith("better")
        costlier = (j.cost_method > j.cost_reference) & (j.cost_method > j.cost_reference_zne)
        res[comp] = {"n": len(j), "fraction_better_than_both": _frac(both), "fraction_costlier_than_both": _frac(costlier)}
    fa = res["A"]["fraction_better_than_both"]
    verdict = ("SUPPORTED" if 0.1 <= fa and res["A"]["fraction_costlier_than_both"] == 1.0 else
               "PARTIALLY SUPPORTED" if fa > 0 else "NOT SUPPORTED")
    return {"rule": "core: combined significantly better than BOTH readout-only and matching ZNE-only in >=10% of "
                    "comparison-A conditions, while always consuming more shots than both", **res, "verdict": verdict}


def _ck() -> list[str]:
    return ["instance", "noise", "observable", "shots_per_circuit"]


def h4(agg: pd.DataFrame, circuits: pd.DataFrame) -> dict[str, Any]:
    c1 = circuits[circuits.scale_nominal == 1.0].groupby("instance").agg(
        depth=("folded_depth", "max"), n2q=("folded_n_2q", "max")).reset_index()
    a = agg[(agg.block == "core") & (agg.comparison == "A") & (agg.method == "baseline") & agg.primary_observable
            & (agg.shots_per_circuit == agg.shots_per_circuit.max())].merge(c1, on="instance")
    out, ok = {}, []
    for k, g in a.groupby("noise"):
        rho, p = spearman(g.n2q, g.abs_bias)
        out[k] = {"spearman_rho_n2q_vs_abs_bias": rho, "p": p, "n_instances": len(g)}
        ok.append(rho > 0 and p < 0.05)
    # exploratory (post hoc, not part of the verdict): within-family trends
    within = {}
    for fam, g in a.groupby("family"):
        if g.n2q.nunique() > 2:
            within[fam] = {k: dict(zip(("rho", "p"), spearman(h.n2q, h.abs_bias), strict=True))
                           for k, h in g.groupby("noise")}
    return {"rule": "core, baseline, primary observable, largest N: Spearman rho(two-qubit gate count, |bias|) > 0 "
                    "with p<0.05 at every noise level (QAOA cost observable is bounded differently; reported anyway)",
            "by_noise": out, "exploratory_within_family": within,
            "verdict": "SUPPORTED" if all(ok) else "PARTIALLY SUPPORTED" if any(ok) else "NOT SUPPORTED"}


def h5(cmp: pd.DataFrame) -> dict[str, Any]:
    c = cmp[(cmp.comparison == "B") & (cmp.reference == "baseline") & (cmp.block == "core")]
    g = c.groupby(_ck())
    none_better = g.outcome.apply(lambda s: not s.str.startswith("better").any())
    all_worse = g.outcome.apply(lambda s: s.str.startswith("worse").all())
    frac = _frac(none_better)
    return {"rule": "core, comparison B (equal total budget): fraction of conditions in which NO mitigation method is "
                    "significantly better than baseline; supported if at least one such condition exists",
            "n_conditions": int(len(none_better)), "fraction_no_method_better": frac,
            "fraction_all_methods_significantly_worse": _frac(all_worse),
            "verdict": "SUPPORTED" if frac > 0 else "NOT SUPPORTED"}


def rq6_ranking(agg: pd.DataFrame) -> dict[str, Any]:
    out = {}
    for comp in ("A", "B"):
        a = agg[(agg.block == "core") & (agg.comparison == comp)]
        ranks = a.groupby(_ck()).rmse.rank(method="average")
        out[f"mean_rmse_rank_{comp}"] = a.assign(rank=ranks).groupby("method")["rank"].mean().sort_values().to_dict()
    return out


def evaluate_all(agg: pd.DataFrame, cmp: pd.DataFrame, circuits: pd.DataFrame) -> dict[str, Any]:
    return {"H1": h1(cmp, agg), "H2": h2(cmp), "H3": h3(cmp), "H4": h4(agg, circuits), "H5": h5(cmp),
            "RQ6": rq6_ranking(agg)}
