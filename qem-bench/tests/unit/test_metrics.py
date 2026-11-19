import math

import numpy as np
import pytest

from qem_bench.analysis.pareto import pareto_mask
from qem_bench.metrics.accuracy import bias, mae, mse, rmse
from qem_bench.metrics.efficiency import improvement_factor, resource_efficiency, work_normalized_mse_ratio
from qem_bench.metrics.overhead import relative_extra_cost, sampling_overhead
from qem_bench.metrics.statistics import (
    benjamini_hochberg,
    bootstrap_ci,
    holm,
    paired_permutation_test,
    wilcoxon_signed_rank,
)
from qem_bench.metrics.variance import mse_decomposition, variance


def test_accuracy_metrics():
    e = np.array([0.9, 1.1, 1.0, 0.8])
    assert bias(e, 1.0) == pytest.approx(-0.05)
    assert mse(e, 1.0) == pytest.approx((0.01 + 0.01 + 0 + 0.04) / 4)
    assert rmse(e, 1.0) == pytest.approx(math.sqrt(0.015))
    assert mae(e, 1.0) == pytest.approx(0.1)
    d = mse_decomposition(e, 1.0)
    assert d["bias_sq"] + d["variance_ddof0"] == pytest.approx(d["mse"])
    assert variance(e) == pytest.approx(np.var(e, ddof=1))


def test_overhead():
    assert sampling_overhead(3000, 1000) == 3
    assert relative_extra_cost(3000, 1000) == 2
    with pytest.raises(ValueError):
        sampling_overhead(1, 0)


@pytest.mark.parametrize("eb,em,cb,cm,cat", [
    (0.1, 0.05, 100, 300, "costly_improvement"),
    (0.1, 0.2, 100, 300, "costly_degradation"),
    (0.1, 0.05, 100, 100, "free_improvement"),
    (0.1, 0.1, 100, 100, "no_change"),
    (0.1, 0.2, 100, 100, "free_degradation"),
    (0.0, 0.1, 100, 300, "baseline_exact"),
    (float("nan"), 0.1, 100, 300, "undefined"),
])
def test_efficiency_edge_cases(eb, em, cb, cm, cat):
    eta, c = resource_efficiency(eb, em, cb, cm)
    assert c == cat
    if cat == "costly_improvement":
        assert eta == pytest.approx(0.5 / 2)
    if cat == "costly_degradation":
        assert eta < 0
    if cat == "free_improvement":
        assert eta == math.inf


def test_established_metrics():
    assert improvement_factor(0.2, 0.1, 100, 400) == pytest.approx(1.0)
    assert work_normalized_mse_ratio(0.04, 0.01, 100, 400) == pytest.approx(1.0)


def test_bootstrap_coverage_synthetic():
    rng = np.random.default_rng(0)
    hits = 0
    trials = 400
    for _ in range(trials):
        x = rng.normal(0.0, 1.0, 60)
        lo, hi = bootstrap_ci(x, "mean", 1000, 0.95, rng)
        hits += lo <= 0.0 <= hi
    assert 0.90 <= hits / trials <= 0.98  # percentile bootstrap is slightly anti-conservative


def test_ci_shrinks_with_n():
    rng = np.random.default_rng(1)
    w1 = np.diff(bootstrap_ci(rng.normal(size=20), rng=rng))[0]
    w2 = np.diff(bootstrap_ci(rng.normal(size=2000), rng=rng))[0]
    assert w2 < w1 / 5


def test_multiple_comparisons():
    p = np.array([0.01, 0.04, 0.03, 0.5])
    np.testing.assert_allclose(holm(p), [0.04, 0.09, 0.09, 0.5])
    np.testing.assert_allclose(benjamini_hochberg(p), [0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])


def test_paired_tests():
    rng = np.random.default_rng(2)
    a = rng.normal(size=50)
    p_null = paired_permutation_test(a, a + rng.normal(0, 1e-3, 50) * 0)
    assert p_null == 1.0
    b = a + 1.0
    p, r = wilcoxon_signed_rank(a, b)
    assert p < 1e-6 and r == -1.0
    assert paired_permutation_test(a, b, rng=rng) < 0.01


def test_pareto_mask():
    x = np.array([1, 2, 3, 2])
    y = np.array([3, 2, 1, 3])
    np.testing.assert_array_equal(pareto_mask(x, y), [True, True, True, False])
