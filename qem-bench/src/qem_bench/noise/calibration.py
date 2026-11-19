"""Measurement calibration circuits and assignment-matrix estimation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit


def calibration_mode(n_qubits: int, full_max_qubits: int) -> str:
    return "full" if n_qubits <= full_max_qubits else "tensored"


def calibration_circuits(n_qubits: int, mode: str) -> list[tuple[int, QuantumCircuit]]:
    """Basis-state preparations. full: all 2^n states; tensored: |0..0> and |1..1>."""
    states = range(2**n_qubits) if mode == "full" else [0, 2**n_qubits - 1]
    out = []
    for j in states:
        qc = QuantumCircuit(n_qubits, name=f"cal_{j}")
        for q in range(n_qubits):
            if (j >> q) & 1:
                qc.x(q)
        qc.barrier()
        out.append((j, qc))
    return out


@dataclass
class AssignmentEstimate:
    mode: str
    n_qubits: int
    full: np.ndarray | None
    per_qubit: list[np.ndarray] | None

    def matrix(self) -> np.ndarray:
        if self.full is not None:
            return self.full
        assert self.per_qubit is not None
        m = np.array([[1.0]])
        for a in reversed(self.per_qubit):  # qubit n-1 is the most significant index
            m = np.kron(m, a)
        return m

    def condition_number(self) -> float:
        if self.full is not None:
            return float(np.linalg.cond(self.full))
        assert self.per_qubit is not None
        return float(np.prod([np.linalg.cond(a) for a in self.per_qubit]))


def estimate_assignment(counts: dict[int, np.ndarray], n_qubits: int, mode: str) -> AssignmentEstimate:
    """counts[j] = outcome histogram (length 2^n) of preparation j."""
    if mode == "full":
        cols = [counts[j] / counts[j].sum() for j in range(2**n_qubits)]
        return AssignmentEstimate(mode, n_qubits, np.column_stack(cols), None)
    p0 = counts[0] / counts[0].sum()
    p1 = counts[2**n_qubits - 1] / counts[2**n_qubits - 1].sum()
    idx = np.arange(2**n_qubits)
    mats = []
    for q in range(n_qubits):
        bit = (idx >> q) & 1
        r10 = p0[bit == 1].sum()  # read 1 | prep 0
        r01 = p1[bit == 0].sum()  # read 0 | prep 1
        mats.append(np.array([[1 - r10, r01], [r10, 1 - r01]]))
    return AssignmentEstimate(mode, n_qubits, None, mats)


def validate_assignment(a: np.ndarray, tol: float = 1e-9) -> dict[str, float | bool]:
    col_err = float(np.max(np.abs(a.sum(axis=0) - 1)))
    in_range = bool(np.all(a >= -tol) and np.all(a <= 1 + tol))
    return {"column_sum_error": col_err, "entries_in_unit_interval": in_range,
            "valid": in_range and col_err < 1e-6, "condition_number": float(np.linalg.cond(a))}
