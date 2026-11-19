"""Small QAOA Max-Cut benchmark with exact classical references."""

from __future__ import annotations

import itertools

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector
from scipy.optimize import minimize

from qem_bench.circuits.observables import BenchmarkCircuit, Observable

Edge = tuple[int, int]


def random_graph(n: int, edge_prob: float, seed: int) -> list[Edge]:
    """Connected Erdos-Renyi G(n, p) graph, resampled deterministically until connected."""
    rng = np.random.default_rng(seed)
    for _ in range(10_000):
        edges = [(i, j) for i, j in itertools.combinations(range(n), 2) if rng.random() < edge_prob]
        if _connected(n, edges):
            return edges
    raise RuntimeError("could not sample a connected graph")


def _connected(n: int, edges: list[Edge]) -> bool:
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i, j in edges:
        adj[i].add(j)
        adj[j].add(i)
    seen, stack = {0}, [0]
    while stack:
        for k in adj[stack.pop()] - seen:
            seen.add(k)
            stack.append(k)
    return len(seen) == n


def cut_value(edges: list[Edge], bits: int) -> int:
    return sum(((bits >> i) & 1) != ((bits >> j) & 1) for i, j in edges)


def max_cut(n: int, edges: list[Edge]) -> int:
    """Exact Max-Cut by brute force (only for small n)."""
    if n > 20:
        raise ValueError("brute force restricted to n <= 20")
    return max(cut_value(edges, b) for b in range(2**n))


def cost_operator(n: int, edges: list[Edge], normalize: bool = True) -> SparsePauliOp:
    """C = sum_(i,j) (I - Z_i Z_j)/2, optionally divided by |E|."""
    terms = []
    scale = 1.0 / len(edges) if normalize else 1.0
    for i, j in edges:
        label = ["I"] * n
        label[n - 1 - i] = label[n - 1 - j] = "Z"
        terms += [("I" * n, 0.5 * scale), ("".join(label), -0.5 * scale)]
    return SparsePauliOp.from_list(terms).simplify()


def qaoa_ansatz(n: int, edges: list[Edge], gammas: np.ndarray, betas: np.ndarray) -> QuantumCircuit:
    qc = QuantumCircuit(n, name=f"qaoa_n{n}_p{len(gammas)}")
    qc.h(range(n))
    for g, b in zip(gammas, betas, strict=True):
        for i, j in edges:
            qc.rzz(-float(g), i, j)  # exp(-i g C) up to global phase
        qc.rx(2 * float(b), range(n))
    qc.barrier()
    return qc


def optimize_parameters(n: int, edges: list[Edge], p: int, seed: int, starts: int = 12) -> np.ndarray:
    """Noiseless parameter optimisation (multi-start Nelder-Mead); fixed before noisy evaluation."""
    op = cost_operator(n, edges, normalize=False)
    rng = np.random.default_rng(seed)

    def neg(x: np.ndarray) -> float:
        sv = Statevector(qaoa_ansatz(n, edges, x[:p], x[p:]))
        return -float(np.real(sv.expectation_value(op)))

    best = None
    for _ in range(starts):
        x0 = np.concatenate([rng.uniform(0, np.pi, p), rng.uniform(0, np.pi / 2, p)])
        res = minimize(neg, x0, method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 3000})
        if best is None or res.fun < best.fun:
            best = res
    assert best is not None
    return np.asarray(best.x)


def qaoa_circuit(n_qubits: int, p: int = 1, edge_prob: float = 0.5, graph_seed: int = 7) -> BenchmarkCircuit:
    n = n_qubits
    edges = random_graph(n, edge_prob, graph_seed)
    x = optimize_parameters(n, edges, p, seed=graph_seed)
    qc = qaoa_ansatz(n, edges, x[:p], x[p:])
    op = cost_operator(n, edges, normalize=True)
    mc = max_cut(n, edges)
    obs = [Observable("cost_norm", op, primary=True)]
    ideal = float(np.real(Statevector(qc).expectation_value(op)))
    ref = {
        "edges": edges, "n_edges": len(edges), "max_cut": mc,
        "gammas": x[:p].tolist(), "betas": x[p:].tolist(),
        "ideal_cost": ideal * len(edges), "ideal_approx_ratio": ideal * len(edges) / mc,
    }
    return BenchmarkCircuit(
        name=f"qaoa_n{n}_p{p}", family="qaoa",
        params={"n_qubits": n, "p": p, "edge_prob": edge_prob, "graph_seed": graph_seed},
        circuit=qc, observables=obs, reference=ref,
    )
