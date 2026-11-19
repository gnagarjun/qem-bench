"""Pauli observables, measurement-basis grouping and diagonal estimators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector


@dataclass(frozen=True)
class Observable:
    name: str
    op: SparsePauliOp
    primary: bool = False

    @property
    def n_qubits(self) -> int:
        return self.op.num_qubits

    @property
    def basis(self) -> str:
        return measurement_basis(self.op)


def measurement_basis(op: SparsePauliOp) -> str:
    """Per-qubit basis label (Qiskit order, rightmost = qubit 0); identity positions -> 'Z'."""
    labels = op.paulis.to_labels()
    chars = []
    for pos in range(op.num_qubits):
        used = {lab[pos] for lab in labels} - {"I"}
        if len(used) > 1:
            raise ValueError(f"observable terms not jointly measurable in one basis: {op}")
        chars.append(used.pop() if used else "Z")
    return "".join(chars)


def basis_rotation(basis: str) -> QuantumCircuit:
    n = len(basis)
    qc = QuantumCircuit(n, name=f"meas_{basis}")
    for q in range(n):
        ch = basis[n - 1 - q]
        if ch == "X":
            qc.h(q)
        elif ch == "Y":
            qc.sdg(q)
            qc.h(q)
    return qc


def diagonal_vector(op: SparsePauliOp) -> np.ndarray:
    """f(x) such that <op> = sum_x p(x) f(x) for outcomes measured in op's basis.

    Index x encodes qubit q in bit q (matches Qiskit count-string ordering).
    """
    n = op.num_qubits
    idx = np.arange(2**n, dtype=np.uint64)
    f = np.zeros(2**n)
    for label, coeff in op.to_list():
        if abs(complex(coeff).imag) > 1e-12:
            raise ValueError("observable must be Hermitian with real coefficients")
        mask = sum(1 << q for q, ch in enumerate(reversed(label)) if ch != "I")
        parity = np.bitwise_count(idx & np.uint64(mask)) & 1
        f += complex(coeff).real * (1.0 - 2.0 * parity)
    return f


def ideal_expectation(circuit: QuantumCircuit, op: SparsePauliOp) -> float:
    return float(np.real(Statevector(circuit).expectation_value(op)))


@dataclass
class BenchmarkCircuit:
    """A logical benchmark circuit (no measurements) plus its observables."""

    name: str
    family: str
    params: dict[str, Any]
    circuit: QuantumCircuit
    observables: list[Observable]
    reference: dict[str, Any] = field(default_factory=dict)

    @property
    def n_qubits(self) -> int:
        return self.circuit.num_qubits

    def ideal_values(self) -> dict[str, float]:
        sv = Statevector(self.circuit)
        return {o.name: float(np.real(sv.expectation_value(o.op))) for o in self.observables}

    def settings(self) -> dict[str, list[Observable]]:
        """Group observables by measurement basis (one circuit execution per setting)."""
        groups: dict[str, list[Observable]] = {}
        for o in self.observables:
            groups.setdefault(o.basis, []).append(o)
        return groups
