#!/usr/bin/env python
"""Aggregate raw runs, run statistical comparisons, Pareto + hypothesis analysis, export tables.

python scripts/analyze_results.py --run results/experiments/<run_id> --out results/aggregated/standard
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from qem_bench.analysis.aggregation import COND_KEYS, aggregate
from qem_bench.analysis.comparisons import paired_comparisons
from qem_bench.analysis.hypotheses import evaluate_all
from qem_bench.analysis.pareto import PARETO_GROUP, pareto_table
from qem_bench.config import AnalysisSpec
from qem_bench.experiments.runner import load_run
from qem_bench.metrics.statistics import benjamini_hochberg


def tex_table(df: pd.DataFrame, path: Path, caption: str, label: str, fmt: str = "{:.3g}") -> None:
    cols = list(df.columns)
    lines = ["\\begin{table}[t]", "\\centering", "\\small", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
             "\\resizebox{\\linewidth}{!}{%", "\\begin{tabular}{" + "l" * len(cols) + "}", "\\toprule",
             " & ".join(str(c).replace("_", "\\_") for c in cols) + " \\\\", "\\midrule"]
    for _, r in df.iterrows():
        cells = [fmt.format(v) if isinstance(v, float | np.floating) else str(v).replace("_", "\\_") for v in r]
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n")


def mode_equivalence(df: pd.DataFrame) -> dict:
    """Pilot: exact-distribution sampling vs per-shot Aer sampling (Welch t-test on estimates)."""
    keys = ["instance", "noise", "shots_per_circuit", "comparison", "method", "observable"]
    a = df[df.block == "pilot_aer"]
    e = df[df.block == "pilot_exact"]
    rows = []
    for k, g in a.groupby(keys):
        h = e.set_index(keys).loc[k] if k in e.set_index(keys).index else None
        if h is None:
            continue
        x, y = g.estimate.dropna(), h.estimate.dropna()
        t = stats.ttest_ind(x, y, equal_var=False)
        lev = stats.levene(x, y)
        rows.append({**dict(zip(keys, k, strict=True)), "p_mean": t.pvalue, "p_var": lev.pvalue,
                     "mean_aer": x.mean(), "mean_exact": y.mean(), "sd_aer": x.std(), "sd_exact": y.std()})
    r = pd.DataFrame(rows)
    r["q_mean"] = benjamini_hochberg(r.p_mean.fillna(1).to_numpy())
    r["q_var"] = benjamini_hochberg(r.p_var.fillna(1).to_numpy())
    return {"n_conditions": len(r), "fraction_mean_differs_q<0.05": float((r.q_mean < 0.05).mean()),
            "fraction_variance_differs_q<0.05": float((r.q_var < 0.05).mean()),
            "fraction_raw_p<0.05_mean": float((r.p_mean < 0.05).mean()),
            "max_abs_mean_difference": float((r.mean_aer - r.mean_exact).abs().max())}, r


def timing_study(df: pd.DataFrame) -> pd.DataFrame:
    a = df[(df.block == "pilot_aer") & (df.comparison == "A")]
    a = a.assign(t_total=a.t_sampling_s + a.t_calibration_s + a.t_postprocess_s)
    # one wall-clock value per (condition, rep, method): sampling/calibration are shared across observables
    u = a.groupby(["instance", "noise", "shots_per_circuit", "repetition", "method"]).agg(
        t_sampling_s=("t_sampling_s", "first"), t_calibration_s=("t_calibration_s", "first"),
        t_postprocess_s=("t_postprocess_s", "sum")).reset_index()
    u["t_total_s"] = u.t_sampling_s + u.t_calibration_s + u.t_postprocess_s
    return u.groupby(["instance", "shots_per_circuit", "method"]).agg(
        t_total_mean=("t_total_s", "mean"), t_total_sd=("t_total_s", "std"),
        t_sampling_mean=("t_sampling_s", "mean"), t_calibration_mean=("t_calibration_s", "mean"),
        t_postprocess_mean=("t_postprocess_s", "mean"), n=("t_total_s", "size")).reset_index()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    runs = [Path(r) for r in args.run]
    cfgs = [json.loads((r / "config_resolved.json").read_text()) for r in runs]
    spec = AnalysisSpec(**cfgs[0]["config"]["analysis"])
    df = pd.concat([load_run(r) for r in runs], ignore_index=True)
    circuits = pd.concat([load_run(r, "circuits") for r in runs], ignore_index=True)
    zpts = pd.concat([load_run(r, "zne_points") for r in runs], ignore_index=True)
    agg = aggregate(df, spec, seed=cfgs[0]["config"]["seed"])
    cmp = paired_comparisons(df, spec, seed=cfgs[0]["config"]["seed"] + 1)
    par = pareto_table(agg[agg.comparison == "A"], [g for g in PARETO_GROUP if g != "comparison"] + ["comparison"])
    agg.to_parquet(out / "aggregated.parquet", index=False)
    agg.to_csv(out / "aggregated.csv", index=False)
    cmp.to_parquet(out / "comparisons.parquet", index=False)
    cmp.to_csv(out / "comparisons.csv", index=False)
    par.to_csv(out / "pareto.csv", index=False)
    circuits.to_csv(out / "circuits.csv", index=False)
    zpts.to_parquet(out / "zne_points.parquet", index=False)
    summary: dict = {"runs": [r.name for r in runs], "config_hashes": [c["config_hash"] for c in cfgs],
                     "schema_version": cfgs[0]["schema_version"], "n_raw_rows": len(df),
                     "n_failed_rows": int((df.status != "ok").sum()),
                     "n_conditions": int(len(agg)), "n_tests": int(len(cmp)),
                     "repetitions": sorted(int(x) for x in agg.n_reps.unique()),
                     "blocks": sorted(df.block.unique().tolist()),
                     "environment": json.loads((runs[0] / "environment.json").read_text()),
                     "analysis": spec.model_dump()}
    if "pilot_aer" in summary["blocks"]:
        eq, eqt = mode_equivalence(df)
        eqt.to_csv(out / "mode_equivalence.csv", index=False)
        tim = timing_study(df)
        tim.to_csv(out / "timing_study.csv", index=False)
        summary["mode_equivalence"] = eq
        piv = tim.groupby("method").t_total_mean.median()
        summary["timing_median_total_s_by_method"] = piv.to_dict()
        tex_table(tim[tim.shots_per_circuit == 4096][["instance", "method", "t_total_mean", "t_total_sd",
                                                      "t_sampling_mean", "t_calibration_mean", "t_postprocess_mean"]],
                  out / "tables" / "timing.tex", "Wall-clock time per condition-repetition (s), per-shot Aer "
                  "sampling, N=4096, comparison A (machine-specific).", "tab:timing", "{:.4f}")
    if "core" in summary["blocks"]:
        hyp = evaluate_all(agg, cmp, circuits)
        summary["hypotheses"] = hyp
        c = cmp[(cmp.block == "core") & (cmp.reference == "baseline")]
        tab = c.groupby(["comparison", "method"]).agg(
            median_rel_rmse_change=("rel_rmse_change", "median"),
            frac_better=("outcome", lambda s: s.str.startswith("better").mean()),
            frac_worse=("outcome", lambda s: s.str.startswith("worse").mean()),
            median_overhead=("cost_method", lambda s: np.nan)).reset_index()
        ov = agg[(agg.block == "core")].groupby(["comparison", "method"]).sampling_overhead.median().reset_index()
        tab = tab.drop(columns="median_overhead").merge(ov, on=["comparison", "method"])
        summary["core_method_summary"] = tab.to_dict(orient="records")
        tex_table(tab, out / "tables" / "core_summary.tex", "Core grid: median relative RMSE change versus baseline, "
                  "fraction of conditions significantly better/worse (BH $q<0.05$) and median sampling overhead.",
                  "tab:core")
        fam = c[c.shots_per_circuit == 4096].groupby(["family", "comparison", "method"]).rel_rmse_change.median()
        tex_table(fam.unstack("method").reset_index(), out / "tables" / "family_summary.tex",
                  "Median relative RMSE change vs baseline by circuit family (N=4096).", "tab:family")
        hrows = [{"hypothesis": k, "verdict": v["verdict"]} for k, v in hyp.items() if k.startswith("H")]
        tex_table(pd.DataFrame(hrows), out / "tables" / "hypotheses.tex", "Pre-specified hypothesis verdicts.",
                  "tab:hyp")
        cats = c[c.comparison == "A"].groupby(["method", "eta_category"]).size().unstack(fill_value=0)
        summary["eta_categories_A"] = cats.to_dict(orient="index")
        cond = agg[(agg.method == "readout")][["instance", "readout_cond"]].groupby("instance").readout_cond.max()
        summary["max_readout_condition_number"] = float(cond.max())
        summary["ill_conditioned_rows"] = int(df.readout_ill_conditioned.sum())
        sc = circuits.groupby(["instance", "scale_nominal", "block"]).agg(
            eff=("scale_effective", "mean"), unitary=("unitary_preserved", "all")).reset_index()
        summary["noise_scaling_max_abs_deviation"] = float(
            (sc[sc.block != "zne_global_123"].eff - sc[sc.block != "zne_global_123"].scale_nominal).abs().max())
        summary["noise_scaling_partial_folding"] = sc[sc.block == "zne_global_123"].groupby(
            "scale_nominal").eff.agg(["min", "max"]).to_dict(orient="index")
        summary["all_folds_unitary_preserving"] = bool(sc.unitary.dropna().all())
    manifest = {"aggregated_from": [{"run": r.name, "raw_files": {p.name: sha(p) for p in sorted((r / "raw").glob("*.parquet"))}}
                                    for r in runs],
                "outputs": {p.name: sha(p) for p in sorted(out.glob("*.*")) if p.suffix in (".csv", ".parquet")}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(json.dumps({k: summary[k] for k in summary if k in ("hypotheses", "mode_equivalence")}, indent=1, default=str))
    return out


if __name__ == "__main__":
    main()

__all__ = ["COND_KEYS", "main"]
