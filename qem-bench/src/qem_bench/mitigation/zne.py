"""Zero-noise extrapolation: unitary folding and linear-weight extrapolators."""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import CircuitInstruction

from qem_bench.mitigation.base import Estimate

SUPPORTED_GATES = {"rz", "sx", "x", "cx", "barrier"}


def _inverse_ops(ci: CircuitInstruction) -> list[tuple[str, tuple[float, ...]]]:
    """Inverse of a basis gate expressed in the same basis (sx^-1 = rz(pi) sx rz(pi) up to phase)."""
    name = ci.operation.name
    if name == "rz":
        return [("rz", (-float(ci.operation.params[0]),))]
    if name in ("x", "cx"):
        return [(name, ())]
    if name == "sx":
        return [("rz", (math.pi,)), ("sx", ()), ("rz", (math.pi,))]
    raise ValueError(f"cannot fold non-basis gate '{name}'; transpile to {SUPPORTED_GATES} first")


def _append(qc: QuantumCircuit, name: str, params: tuple[float, ...], qubits: tuple) -> None:
    getattr(qc, name)(*params, *qubits)


def _gates(circ: QuantumCircuit) -> list[CircuitInstruction]:
    for ci in circ.data:
        if ci.operation.name not in SUPPORTED_GATES:
            raise ValueError(f"unsupported instruction '{ci.operation.name}' for folding")
    return [ci for ci in circ.data if ci.operation.name != "barrier"]


def _append_inverse_of(qc: QuantumCircuit, ops: list[CircuitInstruction]) -> None:
    for ci in reversed(ops):
        for name, params in _inverse_ops(ci):
            _append(qc, name, params, ci.qubits)


def _append_forward(qc: QuantumCircuit, ops: list[CircuitInstruction]) -> None:
    for ci in ops:
        qc.append(ci.operation, ci.qubits)


Weights = dict[str, float] | None


def _split(scale: float, ops: list[CircuitInstruction], weights: Weights, from_end: bool) -> tuple[int, int]:
    """k full folds plus m partially folded gates chosen so the *error-weighted* gate budget
    matches the requested scale (fidelity-weighted folding). With weights=None every
    non-virtual gate counts equally (rz is virtual/noiseless and has weight 0)."""
    if scale < 1:
        raise ValueError("scale factor must be >= 1")
    k = int(math.floor((scale - 1) / 2 + 1e-12))
    frac = (scale - 1) / 2 - k
    if frac < 1e-12:
        return k, 0
    table = weights if weights is not None else {"rz": 0.0}
    w = np.array([table.get(ci.operation.name, 1.0) for ci in ops])
    if w.sum() <= 0:
        return k, int(round(frac * len(ops)))
    seq = w[::-1] if from_end else w
    cum = np.concatenate([[0.0], np.cumsum(seq)])
    m = int(np.argmin(np.abs(cum - frac * w.sum())))
    return k, m


def fold_global(circ: QuantumCircuit, scale: float, weights: Weights = None) -> QuantumCircuit:
    """U -> U (U^dag U)^k (L^dag L), L = last m gates; exact scale for odd integers."""
    ops = _gates(circ)
    k, m = _split(scale, ops, weights, from_end=True)
    out = circ.copy_empty_like()
    _append_forward(out, ops)
    for _ in range(k):
        out.barrier()
        _append_inverse_of(out, ops)
        out.barrier()
        _append_forward(out, ops)
    if m:
        tail = ops[len(ops) - m:]
        out.barrier()
        _append_inverse_of(out, tail)
        out.barrier()
        _append_forward(out, tail)
    out.barrier()
    return out


def fold_local(circ: QuantumCircuit, scale: float, weights: Weights = None) -> QuantumCircuit:
    """Each gate g -> g (g^dag g)^k; the first m gates receive one extra fold (deterministic)."""
    ops = _gates(circ)
    k, m = _split(scale, ops, weights, from_end=False)
    out = circ.copy_empty_like()
    for idx, ci in enumerate(ops):
        out.append(ci.operation, ci.qubits)
        for _ in range(k + (1 if idx < m else 0)):
            out.barrier(ci.qubits)
            _append_inverse_of(out, [ci])
            out.barrier(ci.qubits)
            out.append(ci.operation, ci.qubits)
    out.barrier()
    return out


FOLDERS: dict[str, Callable[..., QuantumCircuit]] = {
    "global": fold_global, "local": fold_local,
}


def extrapolation_weights(scales: np.ndarray, method: str, degree: int | None = None) -> np.ndarray:
    """Weights gamma with E(0) = sum_i gamma_i E(lambda_i).

    linear: least-squares straight line; richardson: Lagrange interpolation of degree k-1;
    poly: least-squares polynomial of given degree.
    """
    s = np.asarray(scales, dtype=float)
    if method == "richardson":
        return np.array([np.prod([s[j] / (s[j] - s[i]) for j in range(len(s)) if j != i]) for i in range(len(s))])
    deg = 1 if method == "linear" else degree
    if deg is None or deg >= len(s):
        raise ValueError("polynomial degree must be < number of scale factors")
    vander = np.vander(s, deg + 1, increasing=True)
    return np.linalg.pinv(vander)[0]


def vandermonde_condition(scales: np.ndarray, method: str) -> float:
    deg = len(scales) - 1 if method == "richardson" else 1
    return float(np.linalg.cond(np.vander(np.asarray(scales, float), deg + 1, increasing=True)))


def extrapolate(scales: np.ndarray, values: np.ndarray, stderrs: np.ndarray, method: str) -> Estimate:
    g = extrapolation_weights(scales, method)
    value = float(g @ values)
    se = float(np.sqrt(np.sum(g**2 * np.asarray(stderrs) ** 2)))
    return Estimate(value, se, {
        "zne_gamma": g.tolist(), "zne_gamma_l1": float(np.abs(g).sum()),
        "zne_vandermonde_cond": vandermonde_condition(scales, method),
        "zne_points": np.asarray(values).tolist(),
    })
