"""Bell-state benchmark circuits."""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

from qem_bench.circuits.observables import BenchmarkCircuit, Observable


def bell_circuit(variant: str = "cx", padding: int = 0) -> BenchmarkCircuit:
    """|Phi+> preparation.

    variant: 'cx' (H, CX) or 'cz' (H, H, CZ, H).
    padding: number of identity-equivalent CX-CX pairs (separated by barriers so the
    transpiler cannot cancel them); a controlled depth knob, *not* a noise-scaling method.
    """
    qc = QuantumCircuit(2, name=f"bell_{variant}_pad{padding}")
    qc.h(0)
    if variant == "cx":
        qc.cx(0, 1)
    elif variant == "cz":
        qc.h(1)
        qc.cz(0, 1)
        qc.h(1)
    else:
        raise ValueError(f"unknown Bell variant {variant}")
    for _ in range(padding):
        qc.barrier()
        qc.cx(0, 1)
        qc.barrier()
        qc.cx(0, 1)
    qc.barrier()
    obs = [
        Observable("XX", SparsePauliOp("XX"), primary=True),
        Observable("ZZ", SparsePauliOp("ZZ")),
        Observable("YY", SparsePauliOp("YY")),
    ]
    return BenchmarkCircuit(
        name=qc.name, family="bell", params={"variant": variant, "padding": padding},
        circuit=qc, observables=obs,
    )
