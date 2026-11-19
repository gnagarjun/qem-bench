import itertools

import numpy as np
import pytest
from qiskit.quantum_info import Operator, Statevector

from qem_bench.circuits import bell_circuit, ghz_circuit, qaoa_circuit
from qem_bench.circuits.qaoa import cost_operator, cut_value, max_cut
from qem_bench.execution.runner import compile_instance


@pytest.mark.parametrize("variant,pad", [("cx", 0), ("cz", 0), ("cx", 2)])
def test_bell_ideal(variant, pad):
    bc = bell_circuit(variant, pad)
    v = bc.ideal_values()
    assert v["XX"] == pytest.approx(1) and v["ZZ"] == pytest.approx(1) and v["YY"] == pytest.approx(-1)
    p = Statevector(bc.circuit).probabilities()
    np.testing.assert_allclose(p, [0.5, 0, 0, 0.5], atol=1e-12)


@pytest.mark.parametrize("n", [3, 4, 5, 6, 8])
def test_ghz_ideal(n):
    bc = ghz_circuit(n)
    v = bc.ideal_values()
    assert v["X_all"] == pytest.approx(1) and v["Z0Zn"] == pytest.approx(1)
    p = Statevector(bc.circuit).probabilities()
    assert p[0] == pytest.approx(0.5) and p[-1] == pytest.approx(0.5)


def test_maxcut_known_graphs():
    assert max_cut(3, [(0, 1), (1, 2), (0, 2)]) == 2
    assert max_cut(4, [(0, 1), (1, 2), (2, 3), (3, 0)]) == 4


@pytest.mark.parametrize("n,p", [(4, 1), (4, 2), (6, 1)])
def test_qaoa_objective_matches_classical(n, p):
    bc = qaoa_circuit(n, p)
    edges = bc.reference["edges"]
    probs = Statevector(bc.circuit).probabilities()
    classical = sum(probs[b] * cut_value(edges, b) for b in range(2**n)) / len(edges)
    assert bc.ideal_values()["cost_norm"] == pytest.approx(classical, abs=1e-10)
    assert 0.5 < bc.reference["ideal_approx_ratio"] <= 1.0
    # cost operator diagonal equals cut values
    diag = np.real(np.diag(cost_operator(n, edges, normalize=False).to_matrix()))
    for b in range(2**n):
        assert diag[b] == pytest.approx(cut_value(edges, b))


def test_transpiled_settings_preserve_unitary():
    bc = qaoa_circuit(4, 1)
    ci = compile_instance(bc, (1.0, 3.0), "global", 1, 0)
    st = ci.settings[0]
    assert Operator(st.physical).equiv(Operator(bc.circuit))
    assert set(st.physical.count_ops()) <= {"rz", "sx", "x", "cx", "barrier"}


def test_settings_cover_observables():
    bc = bell_circuit()
    groups = bc.settings()
    assert set(groups) == {"XX", "ZZ", "YY"}
    assert list(itertools.chain(*groups.values()))
