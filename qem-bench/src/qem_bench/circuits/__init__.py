"""Benchmark circuit library."""

from __future__ import annotations

from functools import lru_cache

from qem_bench.circuits.bell import bell_circuit
from qem_bench.circuits.ghz import ghz_circuit
from qem_bench.circuits.observables import BenchmarkCircuit, Observable
from qem_bench.circuits.qaoa import qaoa_circuit
from qem_bench.config import InstanceSpec


@lru_cache(maxsize=64)
def _build(family: str, key: tuple) -> BenchmarkCircuit:
    params = dict(key)
    if family == "bell":
        return bell_circuit(**params)
    if family == "ghz":
        return ghz_circuit(**params)
    if family == "qaoa":
        return qaoa_circuit(**params)
    raise ValueError(f"unknown circuit family {family}")


def build_instance(spec: InstanceSpec) -> BenchmarkCircuit:
    bc = _build(spec.family, tuple(sorted(spec.params.items())))
    bc.name = spec.name
    return bc


__all__ = ["BenchmarkCircuit", "Observable", "bell_circuit", "build_instance", "ghz_circuit", "qaoa_circuit"]
