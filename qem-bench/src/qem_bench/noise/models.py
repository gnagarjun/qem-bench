"""Configurable phenomenological Aer noise models (NOT hardware-derived)."""

from __future__ import annotations

import numpy as np
from qiskit_aer.noise import NoiseModel, QuantumError, ReadoutError, depolarizing_error, thermal_relaxation_error

from qem_bench.config import NoiseSpec

BASIS_GATES = ["rz", "sx", "x", "cx"]
NOISY_1Q = ("sx", "x")
NOISY_2Q = ("cx",)


def readout_matrix(spec: NoiseSpec) -> np.ndarray:
    """Single-qubit assignment matrix, columns = prepared state, rows = observed."""
    return np.array([[1 - spec.readout_p01, spec.readout_p10], [spec.readout_p01, 1 - spec.readout_p10]])


def _gate_errors(spec: NoiseSpec) -> tuple[QuantumError | None, QuantumError | None]:
    e1 = depolarizing_error(spec.p1, 1) if spec.p1 > 0 else None
    e2 = depolarizing_error(spec.p2, 2) if spec.p2 > 0 else None
    if spec.thermal:
        t1, t2 = spec.t1_us * 1e3, spec.t2_us * 1e3
        th1 = thermal_relaxation_error(t1, t2, spec.gate_time_1q_ns)
        th2 = thermal_relaxation_error(t1, t2, spec.gate_time_2q_ns)
        th2 = th2.tensor(th2)
        e1 = th1 if e1 is None else e1.compose(th1)
        e2 = th2 if e2 is None else e2.compose(th2)
    return e1, e2


def build_noise_model(spec: NoiseSpec, include_readout: bool = True) -> NoiseModel | None:
    """Gate depolarizing (+ optional T1/T2 relaxation) and independent asymmetric readout error.

    rz is virtual and noiseless. Returns None when the specification is noiseless.
    """
    e1, e2 = _gate_errors(spec)
    ro = include_readout and (spec.readout_p01 > 0 or spec.readout_p10 > 0)
    if e1 is None and e2 is None and not ro:
        return None
    nm = NoiseModel(basis_gates=BASIS_GATES)
    if e1 is not None:
        nm.add_all_qubit_quantum_error(e1, list(NOISY_1Q))
    if e2 is not None:
        nm.add_all_qubit_quantum_error(e2, list(NOISY_2Q))
    if ro:
        nm.add_all_qubit_readout_error(ReadoutError(readout_matrix(spec).T))
    return nm


def apply_readout_channel(p: np.ndarray, spec: NoiseSpec) -> np.ndarray:
    """Exact classical action of independent readout error on a probability vector."""
    n = int(np.log2(p.size))
    m = readout_matrix(spec)
    t = p.reshape([2] * n)
    for axis in range(n):
        t = np.moveaxis(np.tensordot(m, t, axes=([1], [axis])), 0, axis)
    return t.reshape(-1)


def gate_error_weight(spec: NoiseSpec, gate: str) -> float:
    """Total Pauli-error probability of a gate under depolarizing parameter lambda."""
    if gate in NOISY_1Q:
        return 0.75 * spec.p1
    if gate in NOISY_2Q:
        return 15 / 16 * spec.p2
    return 0.0
