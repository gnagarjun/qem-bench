"""Shot allocation and resource accounting for comparisons A and B.

Comparison A (equal primary shots): every primary circuit execution receives N shots;
calibration and extra noise-scaled executions are *additional* and reported.
Comparison B (equal total budget): every method spends at most T = N x n_settings
shots in total (the baseline's spend), including calibration and all ZNE scale points.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qem_bench.mitigation.base import MethodSpec
from qem_bench.mitigation.zne import extrapolation_weights


@dataclass(frozen=True)
class ShotPlan:
    shots_by_scale: dict[float, int]  # per measurement setting
    calibration_shots_per_circuit: int
    n_settings: int
    n_calibration_circuits: int

    @property
    def primary_shots(self) -> int:
        return self.n_settings * sum(self.shots_by_scale.values())

    @property
    def calibration_shots(self) -> int:
        return self.calibration_shots_per_circuit * self.n_calibration_circuits

    @property
    def total_shots(self) -> int:
        return self.primary_shots + self.calibration_shots

    @property
    def n_executions(self) -> int:
        cal = self.n_calibration_circuits if self.calibration_shots_per_circuit else 0
        return self.n_settings * len(self.shots_by_scale) + cal


def _split(budget: int, weights: np.ndarray, scales: tuple[float, ...]) -> dict[float, int]:
    w = weights / weights.sum()
    return {s: max(1, int(np.floor(budget * wi))) for s, wi in zip(scales, w, strict=True)}


def plan_shots(
    method: MethodSpec, comparison: str, shots: int, n_settings: int, scales: tuple[float, ...],
    n_cal_circuits: int, cal_shots_a: int | str = "match_primary", cal_fraction_b: float = 0.2,
    zne_allocation_b: str = "proportional_gamma",
) -> ShotPlan:
    n_cal = n_cal_circuits if method.readout else 0
    if comparison == "A":
        by_scale = {s: shots for s in scales} if method.zne else {1.0: shots}
        cal = (shots if cal_shots_a == "match_primary" else int(cal_shots_a)) if method.readout else 0
        return ShotPlan(by_scale, cal, n_settings, n_cal)
    if comparison != "B":
        raise ValueError(f"unknown comparison {comparison}")
    total = shots * n_settings
    cal = max(1, int(round(cal_fraction_b * total)) // n_cal) if method.readout else 0
    per_setting = (total - cal * n_cal) // n_settings
    if per_setting < 1:
        raise ValueError("budget too small for calibration")
    if not method.zne:
        return ShotPlan({1.0: per_setting}, cal, n_settings, n_cal)
    if zne_allocation_b == "proportional_gamma":  # variance-minimising (Krebsbach et al. 2022)
        w = np.abs(extrapolation_weights(np.array(scales), method.extrapolation or "linear"))
    else:
        w = np.ones(len(scales))
    return ShotPlan(_split(per_setting, w, scales), cal, n_settings, n_cal)
