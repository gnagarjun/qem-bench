"""Estimator variance metrics."""

from __future__ import annotations

import numpy as np


def variance(est: np.ndarray) -> float:
    """Unbiased sample variance (ddof=1) of the estimator over repetitions."""
    e = np.asarray(est, dtype=float)
    return float(np.var(e, ddof=1)) if e.size > 1 else float("nan")


def mse_decomposition(est: np.ndarray, ideal: float) -> dict[str, float]:
    """MSE = bias^2 + population variance (ddof=0); returned for diagnostics."""
    e = np.asarray(est, dtype=float)
    b = float(e.mean() - ideal)
    return {"bias_sq": b**2, "variance_ddof0": float(np.var(e)), "mse": float(np.mean((e - ideal) ** 2))}


def variance_calibration_ratio(est: np.ndarray, predicted_stderr: np.ndarray) -> float:
    """Empirical variance / mean predicted variance (1 = shot-noise model is calibrated)."""
    pv = float(np.nanmean(np.asarray(predicted_stderr) ** 2))
    return variance(est) / pv if pv > 0 else float("nan")
