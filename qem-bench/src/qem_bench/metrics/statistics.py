"""Bootstrap CIs, paired tests, effect sizes and multiple-comparison corrections."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy import stats

Stat = Callable[[np.ndarray], np.ndarray]


def bootstrap_ci(x: np.ndarray, stat: str = "mean", n_boot: int = 2000, level: float = 0.95,
                 rng: np.random.Generator | None = None, ideal: float = 0.0) -> tuple[float, float]:
    """Percentile bootstrap CI for mean / rmse (about `ideal`) / median of 1-D data."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return float("nan"), float("nan")
    rng = rng or np.random.default_rng(0)
    res = x[rng.integers(0, x.size, size=(n_boot, x.size))]
    if stat == "mean":
        v = res.mean(axis=1)
    elif stat == "rmse":
        v = np.sqrt(((res - ideal) ** 2).mean(axis=1))
    elif stat == "median":
        v = np.median(res, axis=1)
    else:
        raise ValueError(stat)
    a = (1 - level) / 2
    return float(np.quantile(v, a)), float(np.quantile(v, 1 - a))


def summarize(x: np.ndarray, level: float = 0.95, n_boot: int = 2000,
              rng: np.random.Generator | None = None) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    lo, hi = bootstrap_ci(x, "mean", n_boot, level, rng)
    return {"n": int(np.isfinite(x).sum()), "mean": float(np.nanmean(x)), "sd": float(np.nanstd(x, ddof=1)),
            "median": float(np.nanmedian(x)), "ci_lo": lo, "ci_hi": hi}


def paired_bootstrap_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, level: float = 0.95,
                          rng: np.random.Generator | None = None) -> tuple[float, float, float]:
    """Mean of paired differences a-b with percentile bootstrap CI (resampling pairs)."""
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[np.isfinite(d)]
    lo, hi = bootstrap_ci(d, "mean", n_boot, level, rng)
    return float(d.mean()) if d.size else float("nan"), lo, hi


def paired_permutation_test(a: np.ndarray, b: np.ndarray, n_perm: int = 5000,
                            rng: np.random.Generator | None = None) -> float:
    """Two-sided sign-flip permutation test of mean paired difference."""
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[np.isfinite(d)]
    if d.size == 0 or np.allclose(d, 0):
        return 1.0
    rng = rng or np.random.default_rng(0)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, d.size))
    null = np.abs((signs * d).mean(axis=1))
    return float((1 + np.sum(null >= abs(d.mean()) - 1e-15)) / (n_perm + 1))


def wilcoxon_signed_rank(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Two-sided Wilcoxon signed-rank p-value and matched-pairs rank-biserial correlation r.

    r in [-1, 1]; r < 0 means a tends to be smaller than b."""
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[np.isfinite(d)]
    d = d[np.abs(d) > 1e-15]
    if d.size == 0:
        return 1.0, 0.0
    ranks = stats.rankdata(np.abs(d))
    w_pos, w_neg = ranks[d > 0].sum(), ranks[d < 0].sum()
    r = float((w_pos - w_neg) / (w_pos + w_neg))
    p = float(stats.wilcoxon(d).pvalue) if d.size >= 1 else 1.0
    return p, r


def holm(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    order = np.argsort(p)
    m = p.size
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[idx]))
        adj[idx] = running
    return adj


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    m = p.size
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


def spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    r = stats.spearmanr(x, y)
    return float(r.statistic), float(r.pvalue)
