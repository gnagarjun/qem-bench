"""Configuration A: unmitigated estimator."""

from __future__ import annotations

import numpy as np

from qem_bench.mitigation.base import Estimate


def linear_estimate(weights: np.ndarray, p_hat: np.ndarray, shots: int) -> Estimate:
    """<O> = sum_x p(x) w(x) with multinomial standard error sqrt(Var_p[w]/N)."""
    mean = float(p_hat @ weights)
    var = max(float(p_hat @ weights**2) - mean**2, 0.0)
    return Estimate(mean, float(np.sqrt(var / shots)) if shots > 0 else float("nan"))


def baseline_estimate(f: np.ndarray, counts: np.ndarray) -> Estimate:
    n = int(counts.sum())
    return linear_estimate(f, counts / n, n)
