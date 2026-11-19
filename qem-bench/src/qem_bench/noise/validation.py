"""Validation of noise configuration and of ZNE noise scaling."""

from __future__ import annotations

from typing import Any

import numpy as np
from qiskit import transpile
from qiskit.quantum_info import DensityMatrix, Operator, Statevector, state_fidelity
from qiskit_aer import AerSimulator

from qem_bench.config import NoiseSpec
from qem_bench.execution.runner import CompiledInstance
from qem_bench.execution.simulator import NoisySimulator
from qem_bench.noise.models import BASIS_GATES, build_noise_model, gate_error_weight


def error_mass(circ, spec: NoiseSpec) -> float:
    """Sum of per-gate Pauli-error probabilities (first-order total gate-error budget)."""
    return float(sum(gate_error_weight(spec, ci.operation.name) for ci in circ.data))


def noise_scaling_report(ci: CompiledInstance, spec: NoiseSpec, check_unitary: bool = True) -> list[dict[str, Any]]:
    """Verify that folding (i) preserves the ideal unitary and (ii) scales the gate-error budget
    as intended, and record the exact noisy expectation value at each scale (readout excluded)."""
    sim = NoisySimulator(spec, "exact")
    out = []
    for st in ci.settings:
        base_mass = error_mass(st.physical, spec)
        u0 = Operator(st.physical) if check_unitary and ci.bench.n_qubits <= 8 else None
        for s, fc in st.folded.items():
            p = sim.gate_only_distribution(fc)
            row = {"setting": st.basis, "scale_nominal": s,
                   "scale_effective": error_mass(fc, spec) / base_mass if base_mass > 0 else np.nan,
                   "unitary_preserved": bool(Operator(fc).equiv(u0)) if u0 is not None else None}
            for o in st.observables:
                row[f"exact_noisy_{o.name}"] = float(p @ st.weights[o.name])
                row[f"ideal_{o.name}"] = ci.ideal[o.name]
            out.append(row)
    return out


def state_fidelity_under_noise(ci: CompiledInstance, spec: NoiseSpec, optimization_level: int = 1) -> float:
    """Fidelity of the noisy pre-measurement state with the ideal state (density-matrix simulation)."""
    qc = transpile(ci.bench.circuit, basis_gates=BASIS_GATES, optimization_level=optimization_level, seed_transpiler=0)
    qc.save_density_matrix()
    res = AerSimulator(method="density_matrix", noise_model=build_noise_model(spec, False)).run(qc).result()
    rho = DensityMatrix(res.data(0)["density_matrix"])
    return float(state_fidelity(rho, Statevector(ci.bench.circuit)))
