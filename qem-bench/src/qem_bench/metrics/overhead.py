"""Sampling-overhead definitions.

O_sampling = N_mitigated / N_baseline, where both N are *total* shots per experimental
condition (all measurement settings, all noise-scale points and all calibration circuits).
The baseline denominator is N x n_settings at the same nominal shots-per-circuit N.
"""

from __future__ import annotations


def sampling_overhead(n_mitigated: float, n_baseline: float) -> float:
    if n_baseline <= 0:
        raise ValueError("baseline shot count must be positive")
    return n_mitigated / n_baseline


def relative_extra_cost(c_mitigated: float, c_baseline: float) -> float:
    """(C_mit - C_base) / C_base: dimensionless additional resource expenditure."""
    return sampling_overhead(c_mitigated, c_baseline) - 1.0


def shots_for_target_variance(variance_per_shot: float, target_variance: float) -> float:
    """N needed for an unbiased estimator to reach a target variance (Var = v/N)."""
    return variance_per_shot / target_variance
