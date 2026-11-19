import numpy as np
import pytest

from qem_bench.circuits import ghz_circuit
from qem_bench.execution.runner import compile_instance
from qem_bench.execution.simulator import NoisySimulator
from qem_bench.mitigation.base import IllConditionedCalibrationError
from qem_bench.mitigation.baseline import baseline_estimate
from qem_bench.mitigation.combined import combined_estimate
from qem_bench.mitigation.readout import ReadoutCorrector, apply_kron, project_simplex
from qem_bench.mitigation.zne import extrapolate, extrapolation_weights
from qem_bench.noise.calibration import AssignmentEstimate


def _tensored(eps0, eps1, n):
    m = np.array([[1 - eps0, eps1], [eps0, 1 - eps1]])
    return AssignmentEstimate("tensored", n, None, [m] * n), m


@pytest.mark.parametrize("scales", [(1.0, 3.0, 5.0), (1.0, 2.0, 3.0), (1.0, 3.0, 5.0, 7.0)])
def test_extrapolation_weights_exact_on_polynomials(scales):
    s = np.array(scales)
    for deg in range(len(s)):
        f = 0.3 + np.zeros_like(s) + sum((0.1 * (k + 1) * s**k for k in range(1, deg + 1)), np.zeros_like(s))
        assert extrapolation_weights(s, "richardson") @ f == pytest.approx(0.3, abs=1e-10)
    assert extrapolation_weights(s, "linear") @ (0.3 - 0.05 * s) == pytest.approx(0.3)
    assert extrapolation_weights(s, "richardson").sum() == pytest.approx(1.0)
    assert extrapolation_weights(s, "linear").sum() == pytest.approx(1.0)


def test_richardson_known_coefficients():
    np.testing.assert_allclose(extrapolation_weights(np.array([1.0, 3.0, 5.0]), "richardson"), [15 / 8, -5 / 4, 3 / 8])


def test_extrapolation_variance_propagation():
    e = extrapolate(np.array([1.0, 3.0, 5.0]), np.array([0.9, 0.7, 0.5]), np.array([0.01, 0.01, 0.01]), "richardson")
    g = np.array([15 / 8, -5 / 4, 3 / 8])
    assert e.stderr == pytest.approx(0.01 * np.sqrt((g**2).sum()))
    assert e.value == pytest.approx(1.0)


def test_zne_reduces_bias_on_exact_noisy_data(moderate):
    spec = moderate.scaled(1.0, 0.0, "gate_only")
    ci = compile_instance(ghz_circuit(4), (1.0, 3.0, 5.0), "global", 1, 0)
    st = [s for s in ci.settings if s.basis == "XXXX"][0]
    sim = NoisySimulator(spec, "exact")
    vals = np.array([sim.distribution(s, st.folded[s]) @ st.weights["X_all"] for s in (1.0, 3.0, 5.0)])
    for m in ("linear", "richardson"):
        z = extrapolate(np.array([1.0, 3.0, 5.0]), vals, np.zeros(3), m).value
        assert abs(z - 1.0) < abs(vals[0] - 1.0) / 3
    z = extrapolate(np.array([1.0, 3.0, 5.0]), vals, np.zeros(3), "richardson").value
    assert z == pytest.approx(1.0, abs=2e-3)  # depolarizing decay is near-exponential: small residual bias


def test_readout_correction_on_synthetic_distribution():
    rng = np.random.default_rng(0)
    p_true = rng.dirichlet(np.ones(8))
    est, m = _tensored(0.05, 0.1, 3)
    p_noisy = apply_kron([m] * 3, p_true)
    corr = ReadoutCorrector(est)
    np.testing.assert_allclose(corr.correct(p_noisy), p_true, atol=1e-12)
    dense = ReadoutCorrector(AssignmentEstimate("full", 3, est.matrix(), None))
    np.testing.assert_allclose(dense.correct(p_noisy), p_true, atol=1e-12)
    f = rng.normal(size=8)
    counts = p_noisy * 1e9
    assert corr.estimate(f, counts).value == pytest.approx(p_true @ f, abs=1e-6)


def test_singular_calibration_detected():
    est, _ = _tensored(0.5, 0.5, 2)
    with pytest.raises(IllConditionedCalibrationError):
        ReadoutCorrector(est)


def test_ill_conditioned_flagged(caplog):
    est, _ = _tensored(0.45, 0.45, 4)
    corr = ReadoutCorrector(est, condition_warning=100)
    assert corr.ill_conditioned and corr.cond > 100


def test_simplex_projection_physical():
    q = project_simplex(np.array([0.7, 0.5, -0.1, -0.1]))
    assert q.min() >= 0 and q.sum() == pytest.approx(1.0)
    p = np.array([0.2, 0.3, 0.5])
    np.testing.assert_allclose(project_simplex(p), p)


def test_combined_applies_both_steps():
    est, m = _tensored(0.05, 0.1, 2)
    corr = ReadoutCorrector(est)
    f = np.array([1, -1, -1, 1.0])
    p = {s: apply_kron([m, m], np.array([0.5, 0, 0, 0.5]) * (1 - 0.05 * s) + 0.0125 * s) * 1e9 for s in (1.0, 3.0, 5.0)}
    c = combined_estimate(f, p, corr, "linear")
    vals = [corr.estimate(f, p[s]).value for s in (1.0, 3.0, 5.0)]
    raw = [baseline_estimate(f, p[s]).value for s in (1.0, 3.0, 5.0)]
    assert c.value == pytest.approx(extrapolate(np.array([1.0, 3.0, 5.0]), np.array(vals), np.zeros(3), "linear").value)
    assert abs(c.value - 1.0) < abs(raw[0] - 1.0)
    assert c.value == pytest.approx(1.0, abs=1e-6)
