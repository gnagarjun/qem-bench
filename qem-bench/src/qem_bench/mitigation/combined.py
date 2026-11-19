"""Configuration D: readout correction at each noise-scale point, then ZNE."""

from __future__ import annotations

import numpy as np

from qem_bench.mitigation.base import Estimate
from qem_bench.mitigation.readout import ReadoutCorrector
from qem_bench.mitigation.zne import extrapolate


def combined_estimate(
    f: np.ndarray, counts_by_scale: dict[float, np.ndarray], corrector: ReadoutCorrector, method: str
) -> Estimate:
    """Readout mitigation is applied to the measured distribution *before* extrapolation,
    because readout error is not amplified by gate folding (measurements are not folded)."""
    scales = np.array(sorted(counts_by_scale))
    pts = [corrector.estimate(f, counts_by_scale[s]) for s in scales]
    est = extrapolate(scales, np.array([p.value for p in pts]), np.array([p.stderr for p in pts]), method)
    est.diagnostics.update(pts[0].diagnostics)
    return est
