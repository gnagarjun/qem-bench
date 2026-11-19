"""Noisy Aer execution: exact-distribution sampling or per-shot Aer sampling."""

from __future__ import annotations

import time
from collections.abc import Hashable

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from qem_bench.config import NoiseSpec
from qem_bench.noise.models import apply_readout_channel, build_noise_model


class SimulationError(RuntimeError):
    pass


class NoisySimulator:
    """Backend abstraction. A hardware backend would implement the same `sample` interface.

    mode="exact": the noisy output distribution (gate noise via Aer density-matrix
    simulation, then the exact independent readout channel) is computed once per circuit
    and shots are drawn multinomially. This is statistically identical to per-shot
    sampling for terminal measurements (validated in tests) and far cheaper.
    mode="aer": every call runs AerSimulator with the full noise model and a seed.
    """

    def __init__(self, spec: NoiseSpec, mode: str = "exact") -> None:
        if mode not in ("exact", "aer"):
            raise ValueError(f"unknown sampling mode {mode}")
        self.spec, self.mode = spec, mode
        self._gate_model = build_noise_model(spec, include_readout=False)
        self._full_model = build_noise_model(spec, include_readout=True)
        self._dm = AerSimulator(method="density_matrix", noise_model=self._gate_model)
        self._shots_sim = AerSimulator(noise_model=self._full_model)
        self._cache: dict[Hashable, np.ndarray] = {}
        self.distribution_time: dict[Hashable, float] = {}

    def gate_only_distribution(self, circ: QuantumCircuit) -> np.ndarray:
        c = circ.copy()
        c.save_probabilities()
        res = self._dm.run(c).result()
        if not res.success:
            raise SimulationError(res.status)
        p = np.clip(np.asarray(res.data(0)["probabilities"], dtype=float), 0, None)
        return p / p.sum()

    def distribution(self, key: Hashable, circ: QuantumCircuit) -> np.ndarray:
        if key not in self._cache:
            t0 = time.perf_counter()
            p = apply_readout_channel(self.gate_only_distribution(circ), self.spec)
            p = np.clip(p, 0, None)
            self._cache[key] = p / p.sum()
            self.distribution_time[key] = time.perf_counter() - t0
        return self._cache[key]

    def sample(self, key: Hashable, circ: QuantumCircuit, shots: int, rng: np.random.Generator) -> np.ndarray:
        if shots < 1:
            raise SimulationError("shots must be >= 1")
        n = circ.num_qubits
        if self.mode == "exact":
            return rng.multinomial(shots, self.distribution(key, circ))
        c = circ.copy()
        c.measure_all()
        res = self._shots_sim.run(c, shots=shots, seed_simulator=int(rng.integers(2**31 - 1))).result()
        if not res.success:
            raise SimulationError(res.status)
        out = np.zeros(2**n, dtype=np.int64)
        for bits, cnt in res.get_counts(0).items():
            out[int(bits.replace(" ", ""), 2)] += cnt
        return out
