"""Configuration B: readout (measurement) error mitigation by assignment-matrix inversion."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qem_bench.logging import get_logger
from qem_bench.mitigation.base import Estimate, IllConditionedCalibrationError
from qem_bench.mitigation.baseline import linear_estimate
from qem_bench.noise.calibration import AssignmentEstimate

log = get_logger(__name__)


def apply_kron(mats: list[np.ndarray], v: np.ndarray) -> np.ndarray:
    """(M_{n-1} (x) ... (x) M_0) v without forming the 2^n x 2^n matrix."""
    n = len(mats)
    t = v.reshape([2] * n)
    for q, m in enumerate(mats):
        axis = n - 1 - q
        t = np.moveaxis(np.tensordot(m, t, axes=([1], [axis])), 0, axis)
    return t.reshape(-1)


def project_simplex(v: np.ndarray) -> np.ndarray:
    """Euclidean projection onto the probability simplex (Duchi et al., 2008)."""
    u = np.sort(v)[::-1]
    css = np.cumsum(u)
    rho = np.nonzero(u * np.arange(1, v.size + 1) > (css - 1))[0][-1]
    theta = (css[rho] - 1) / (rho + 1.0)
    return np.maximum(v - theta, 0)


@dataclass
class ReadoutCorrector:
    """Inverse of an estimated assignment model; full (dense) or tensored (scalable)."""

    assignment: AssignmentEstimate
    physicality: str = "none"
    condition_warning: float = 1e3
    condition_failure: float = 1e12

    def __post_init__(self) -> None:
        self.cond = self.assignment.condition_number()
        if not np.isfinite(self.cond) or self.cond > self.condition_failure:
            raise IllConditionedCalibrationError(f"assignment matrix ill-conditioned (cond={self.cond:.3g})")
        self.ill_conditioned = self.cond > self.condition_warning
        if self.ill_conditioned:
            log.warning("assignment matrix condition number %.3g exceeds warning threshold", self.cond)
        if self.assignment.full is not None:
            self._inv = [np.linalg.inv(self.assignment.full)]
        else:
            assert self.assignment.per_qubit is not None
            self._inv = [np.linalg.inv(a) for a in self.assignment.per_qubit]

    def _apply(self, v: np.ndarray, transpose: bool = False) -> np.ndarray:
        mats = [m.T for m in self._inv] if transpose else self._inv
        return mats[0] @ v if self.assignment.full is not None else apply_kron(mats, v)

    def correct(self, p: np.ndarray) -> np.ndarray:
        q = self._apply(p)
        return project_simplex(q) if self.physicality == "simplex" else q

    def estimate(self, f: np.ndarray, counts: np.ndarray) -> Estimate:
        n = int(counts.sum())
        p = counts / n
        q = self._apply(p)
        neg_mass = float(-q[q < 0].sum())
        diag = {"readout_cond": self.cond, "readout_ill_conditioned": self.ill_conditioned,
                "readout_negative_mass": neg_mass}
        if self.physicality == "simplex":
            qp = project_simplex(q)
            # simplex projection is nonlinear (biased); stderr below uses the linear approximation
            est = linear_estimate(self._apply(f, transpose=True), p, n)
            return Estimate(float(qp @ f), est.stderr, diag)
        # unconstrained inverse: value = (A^-T f) . p, stderr from multinomial variance of g = A^-T f
        est = linear_estimate(self._apply(f, transpose=True), p, n)
        est.diagnostics = diag
        return est
