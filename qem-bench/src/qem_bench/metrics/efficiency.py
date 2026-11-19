"""Resource-aware efficiency metrics.

eta (QEM-Bench, proposed): relative error reduction per unit relative extra cost,
    eta = [(E_b - E_m)/E_b] / [(C_m - C_b)/C_b],  E = RMSE, C = total shots.
Both numerator and denominator are dimensionless, so no incompatible units are mixed.
Edge cases (Delta C <= 0) are mapped to +/-inf or 0 and always labelled by `category`.

mu (established, Russo et al. 2023, IEEE TQE): improvement factor normalised by
    the shot-cost factor sqrt(N_m/N_b):  mu = (E_b/E_m) / sqrt(C_m/C_b).
mu > 1 means mitigation beats simply spending the extra shots on the unmitigated estimator
*if* that estimator were variance-dominated.

wnmse: work-normalised MSE ratio (MSE_m C_m)/(MSE_b C_b), the classical Monte-Carlo
efficiency criterion (lower is better); only meaningful when variance dominates MSE.
"""

from __future__ import annotations

import math


def resource_efficiency(e_base: float, e_mit: float, c_base: float, c_mit: float, tol: float = 1e-12) -> tuple[float, str]:
    if not all(math.isfinite(x) for x in (e_base, e_mit, c_base, c_mit)) or c_base <= 0:
        return float("nan"), "undefined"
    if e_base <= tol:
        return float("nan"), "baseline_exact"
    de = (e_base - e_mit) / e_base
    dc = (c_mit - c_base) / c_base
    if abs(dc) <= tol:
        if de > tol:
            return float("inf"), "free_improvement"
        return (0.0, "no_change") if abs(de) <= tol else (float("-inf"), "free_degradation")
    if dc < 0:
        return (float("inf"), "cheaper_and_better") if de > tol else (de / dc, "cheaper_and_worse")
    if de <= 0:
        return de / dc, "costly_degradation" if de < -tol else "costly_no_change"
    return de / dc, "costly_improvement"


def improvement_factor(e_base: float, e_mit: float, c_base: float, c_mit: float) -> float:
    if e_mit <= 0 or c_base <= 0:
        return float("nan")
    return (e_base / e_mit) / math.sqrt(c_mit / c_base)


def work_normalized_mse_ratio(mse_base: float, mse_mit: float, c_base: float, c_mit: float) -> float:
    if mse_base <= 0:
        return float("nan")
    return (mse_mit * c_mit) / (mse_base * c_base)
