import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
from scipy import stats

from qem_bench.circuits import ghz_circuit, qaoa_circuit
from qem_bench.config import NoiseSpec
from qem_bench.execution.runner import compile_instance, folding_weights
from qem_bench.execution.simulator import NoisySimulator
from qem_bench.mitigation.zne import fold_global, fold_local
from qem_bench.noise.calibration import calibration_circuits, estimate_assignment, validate_assignment
from qem_bench.noise.models import apply_readout_channel, readout_matrix
from qem_bench.noise.validation import error_mass, noise_scaling_report


def test_zero_noise_reproduces_ideal(ideal_spec):
    ci = compile_instance(ghz_circuit(4), (1.0, 3.0), "global", 1, 0)
    sim = NoisySimulator(ideal_spec, "exact")
    for st in ci.settings:
        p = sim.distribution(("s", st.basis), st.folded[3.0])
        for o in st.observables:
            assert p @ st.weights[o.name] == pytest.approx(ci.ideal[o.name], abs=1e-9)
    aer = NoisySimulator(ideal_spec, "aer")
    st = ci.settings[0]
    c = aer.sample("k", st.physical, 4000, np.random.default_rng(0))
    est = c @ st.weights[st.observables[0].name] / 4000
    assert est == pytest.approx(1.0, abs=1e-12)  # X_all is deterministic for the ideal GHZ state


def test_noise_monotonically_reduces_correlation(moderate):
    ci = compile_instance(ghz_circuit(4), (1.0,), "global", 1, 0)
    st = [s for s in ci.settings if s.basis == "XXXX"][0]
    vals = [NoisySimulator(moderate.scaled(g, 1), "exact").distribution("k", st.physical) @ st.weights["X_all"]
            for g in (0.0, 1.0, 2.0, 4.0)]
    assert all(a > b for a, b in zip(vals, vals[1:], strict=False))


def test_readout_matrix_valid(moderate):
    m = readout_matrix(moderate)
    assert validate_assignment(m)["valid"]


def test_readout_channel_matches_aer(moderate):
    spec = NoiseSpec(name="ro", p1=0, p2=0, readout_p01=0.1, readout_p10=0.2)
    qc = QuantumCircuit(2)
    qc.x(1)
    p_exact = NoisySimulator(spec, "exact").distribution("k", qc)
    expected = apply_readout_channel(np.array([0, 0, 1.0, 0]), spec)
    np.testing.assert_allclose(p_exact, expected, atol=1e-12)
    counts = NoisySimulator(spec, "aer").sample("k", qc, 20000, np.random.default_rng(3))
    chi = stats.chisquare(counts, expected * 20000)
    assert chi.pvalue > 1e-3


@pytest.mark.parametrize("folder", [fold_global, fold_local])
@pytest.mark.parametrize("scale", [1.0, 3.0, 5.0])
def test_folding_preserves_unitary_and_scales_noise(folder, scale, moderate):
    ci = compile_instance(qaoa_circuit(4, 1), (1.0,), "global", 1, 0)
    phys = ci.settings[0].physical
    folded = folder(phys, scale)
    assert Operator(folded).equiv(Operator(phys))
    assert error_mass(folded, moderate) / error_mass(phys, moderate) == pytest.approx(scale)


def test_partial_folding_effective_scale_reported(moderate):
    # regression: unweighted gate-count partial folding gave lambda_eff = 1.18 / 2.93 for nominal 2
    ci = compile_instance(ghz_circuit(4), (1.0, 2.0), "global", 1, 0, folding_weights(moderate))
    rep = noise_scaling_report(ci, moderate)
    eff = [r["scale_effective"] for r in rep if r["scale_nominal"] == 2.0]
    assert all(abs(e - 2.0) < 0.35 for e in eff), eff  # residual: whole-gate granularity
    eff_used = [st.effective[2.0] for st in ci.settings]
    np.testing.assert_allclose(sorted(eff_used), sorted(eff))  # extrapolation uses the measured scale
    assert all(r["unitary_preserved"] for r in rep)


def test_folding_increases_noisy_deviation(moderate):
    ci = compile_instance(ghz_circuit(4), (1.0, 3.0, 5.0), "global", 1, 0)
    rep = [r for r in noise_scaling_report(ci, moderate) if r["setting"] == "XXXX"]
    vals = [r["exact_noisy_X_all"] for r in sorted(rep, key=lambda r: r["scale_nominal"])]
    assert vals[0] > vals[1] > vals[2]


def test_calibration_estimation_recovers_model():
    spec = NoiseSpec(name="ro", p1=0, p2=0, readout_p01=0.05, readout_p10=0.1)
    sim = NoisySimulator(spec, "exact")
    for mode in ("full", "tensored"):
        cc = {j: sim.distribution(("c", j), c) * 1e6 for j, c in calibration_circuits(3, mode)}
        est = estimate_assignment(cc, 3, mode)
        true = np.kron(np.kron(readout_matrix(spec), readout_matrix(spec)), readout_matrix(spec))
        np.testing.assert_allclose(est.matrix(), true, atol=1e-9)
        assert validate_assignment(est.matrix())["valid"]


def test_exact_and_aer_sampling_equivalent(moderate):
    ci = compile_instance(qaoa_circuit(4, 1), (1.0, 3.0), "global", 1, 0)
    c = ci.settings[0].folded[3.0]
    p = NoisySimulator(moderate, "exact").distribution("k", c)
    counts = NoisySimulator(moderate, "aer").sample("k", c, 50000, np.random.default_rng(5))
    keep = p * 50000 > 5
    exp = p[keep] * 50000
    obs = counts[keep]
    chi = stats.chisquare(obs, exp * obs.sum() / exp.sum())
    assert chi.pvalue > 1e-3
