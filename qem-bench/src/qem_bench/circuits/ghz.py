"""GHZ-state benchmark circuits."""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

from qem_bench.circuits.observables import BenchmarkCircuit, Observable


def ghz_circuit(n_qubits: int) -> BenchmarkCircuit:
    """Linear-chain GHZ preparation (H + n-1 CX). Ideal <X^n> = 1 and <Z_0 Z_{n-1}> = 1."""
    if n_qubits < 2:
        raise ValueError("GHZ requires at least 2 qubits")
    qc = QuantumCircuit(n_qubits, name=f"ghz_{n_qubits}")
    qc.h(0)
    for q in range(n_qubits - 1):
        qc.cx(q, q + 1)
    qc.barrier()
    zz = ["I"] * n_qubits
    zz[0] = zz[-1] = "Z"
    obs = [
        Observable("X_all", SparsePauliOp("X" * n_qubits), primary=True),
        Observable("Z0Zn", SparsePauliOp("".join(zz))),
    ]
    return BenchmarkCircuit(
        name=qc.name, family="ghz", params={"n_qubits": n_qubits}, circuit=qc, observables=obs
    )
