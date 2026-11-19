"""Aggregation of raw repetition-level rows into per-condition statistics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qem_bench.config import AnalysisSpec
from qem_bench.metrics.statistics import bootstrap_ci
from qem_bench.metrics.variance import variance_calibration_ratio

COND_KEYS = ["block", "instance", "family", "n_qubits", "noise", "noise_base", "p1", "p2", "readout_p01",
             "readout_p10", "gate_multiplier", "readout_multiplier", "thermal", "folding", "scale_factors",
             "calibration_mode", "n_settings", "shots_per_circuit", "observable", "primary_observable"]
KEYS = [*COND_KEYS, "comparison", "method"]


def _agg_group(g: pd.DataFrame, spec: AnalysisSpec, rng: np.random.Generator) -> dict:
    ok = g[g.status == "ok"]
    est = ok.estimate.to_numpy()
    ideal = float(g.ideal.iloc[0])
    n = est.size
    out = {"n_reps": len(g), "n_ok": n, "n_failed": len(g) - n, "ideal": ideal}
    if n == 0:
        return out
    err = est - ideal
    lo, hi = bootstrap_ci(est, "rmse", spec.bootstrap_samples, spec.confidence_level, rng, ideal)
    mlo, mhi = bootstrap_ci(est, "mean", spec.bootstrap_samples, spec.confidence_level, rng)
    alo, ahi = bootstrap_ci(np.abs(err), "mean", spec.bootstrap_samples, spec.confidence_level, rng)
    out.update({
        "mean": est.mean(), "sd": est.std(ddof=1) if n > 1 else np.nan, "median": float(np.median(est)),
        "mean_ci_lo": mlo, "mean_ci_hi": mhi, "bias": err.mean(), "abs_bias": abs(err.mean()),
        "variance": est.var(ddof=1) if n > 1 else np.nan, "mse": float(np.mean(err**2)),
        "rmse": float(np.sqrt(np.mean(err**2))), "rmse_ci_lo": lo, "rmse_ci_hi": hi,
        "mae": float(np.mean(np.abs(err))), "mae_ci_lo": alo, "mae_ci_hi": ahi,
        "stderr_est_mean": float(ok.stderr_est.mean()),
        "variance_ratio": variance_calibration_ratio(est, ok.stderr_est.to_numpy()),
        "total_shots": float(g.total_shots.mean()), "primary_shots": float(g.primary_shots.mean()),
        "calibration_shots": float(g.calibration_shots.mean()), "n_executions": float(g.n_executions.mean()),
        "t_sampling_s": float(g.t_sampling_s.mean()), "t_sampling_sd": float(g.t_sampling_s.std()),
        "t_calibration_s": float(g.t_calibration_s.mean()), "t_postprocess_s": float(g.t_postprocess_s.mean()),
        "t_postprocess_sd": float(g.t_postprocess_s.std()),
        "readout_cond": float(ok.readout_cond.mean()), "readout_negative_mass": float(ok.readout_negative_mass.mean()),
        "zne_gamma_l1": float(ok.zne_gamma_l1.mean()),
    })
    return out


def aggregate(df: pd.DataFrame, spec: AnalysisSpec, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    records = []
    for key, g in df.groupby(KEYS, sort=True, dropna=False):
        records.append({**dict(zip(KEYS, key, strict=True)), **_agg_group(g, spec, rng)})
    agg = pd.DataFrame(records)
    base = agg[agg.method == "baseline"][[*COND_KEYS, "comparison", "total_shots", "rmse", "mse"]]
    base = base.rename(columns={"total_shots": "baseline_total_shots", "rmse": "baseline_rmse", "mse": "baseline_mse"})
    agg = agg.merge(base, on=[*COND_KEYS, "comparison"], how="left")
    agg["sampling_overhead"] = agg.total_shots / agg.baseline_total_shots
    agg["rel_rmse_change"] = (agg.rmse - agg.baseline_rmse) / agg.baseline_rmse
    return agg
