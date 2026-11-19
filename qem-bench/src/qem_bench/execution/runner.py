"""Compilation of benchmark instances and execution of one condition-repetition."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from qiskit import QuantumCircuit, transpile

from qem_bench.circuits.observables import BenchmarkCircuit, Observable, basis_rotation, diagonal_vector
from qem_bench.config import BlockSpec, ExperimentConfig, NoiseSpec
from qem_bench.execution.resource_tracker import ShotPlan, plan_shots
from qem_bench.execution.simulator import NoisySimulator
from qem_bench.mitigation.base import METHODS, Estimate, MethodSpec, MitigationError
from qem_bench.mitigation.baseline import baseline_estimate
from qem_bench.mitigation.combined import combined_estimate
from qem_bench.mitigation.readout import ReadoutCorrector
from qem_bench.mitigation.zne import FOLDERS, extrapolate
from qem_bench.noise.calibration import calibration_circuits, calibration_mode, estimate_assignment
from qem_bench.noise.models import BASIS_GATES, NOISY_1Q, NOISY_2Q, gate_error_weight
from qem_bench.seeds import rng_for


@dataclass
class CompiledSetting:
    basis: str
    observables: list[Observable]
    weights: dict[str, np.ndarray]
    physical: QuantumCircuit
    folded: dict[float, QuantumCircuit]
    effective: dict[float, float] = field(default_factory=dict)  # nominal -> error-mass scale


@dataclass
class CompiledInstance:
    bench: BenchmarkCircuit
    ideal: dict[str, float]
    settings: list[CompiledSetting]
    scales: tuple[float, ...]
    folding: str
    transpile_time_s: float
    complexity: list[dict[str, Any]] = field(default_factory=list)


def gate_counts(circ: QuantumCircuit) -> dict[str, int]:
    ops = circ.count_ops()
    return {
        "n_gates": int(sum(v for k, v in ops.items() if k not in ("barrier", "measure"))),
        "n_1q_noisy": int(sum(ops.get(g, 0) for g in NOISY_1Q)),
        "n_2q": int(sum(ops.get(g, 0) for g in NOISY_2Q)),
        "depth": int(circ.depth(lambda ci: ci.operation.name != "barrier")),
    }


def _mass(circ: QuantumCircuit, weights: dict[str, float]) -> float:
    return float(sum(weights.get(ci.operation.name, 0.0) for ci in circ.data))


def compile_instance(bench: BenchmarkCircuit, scales: tuple[float, ...], folding: str,
                     optimization_level: int, seed: int, fold_weights: dict[str, float] | None = None) -> CompiledInstance:
    t0 = time.perf_counter()
    settings, complexity = [], []
    logical = bench.circuit
    lops = logical.count_ops()
    for basis, obs in bench.settings().items():
        circ = logical.compose(basis_rotation(basis))
        phys = transpile(circ, basis_gates=BASIS_GATES, optimization_level=optimization_level,
                         seed_transpiler=seed)
        if phys.num_qubits != bench.n_qubits:
            raise RuntimeError("transpilation changed the qubit count")
        folded = {s: FOLDERS[folding](phys, s, fold_weights) for s in scales}
        eff = {s: s for s in scales}
        if fold_weights:
            base = _mass(phys, fold_weights)
            eff = {s: _mass(fc, fold_weights) / base for s, fc in folded.items()}
        settings.append(CompiledSetting(basis, obs, {o.name: diagonal_vector(o.op) for o in obs}, phys, folded, eff))
        for s, fc in folded.items():
            complexity.append({
                "setting": basis, "scale_nominal": s, "n_qubits": bench.n_qubits,
                "logical_gates": int(sum(v for k, v in lops.items() if k != "barrier")),
                "logical_2q": int(sum(lops.get(g, 0) for g in ("cx", "cz", "rzz"))),
                "logical_depth": int(logical.depth(lambda ci: ci.operation.name != "barrier")),
                "transpiled_depth_unfolded": gate_counts(phys)["depth"],
                "n_measurements": bench.n_qubits, **{f"folded_{k}": v for k, v in gate_counts(fc).items()},
            })
    return CompiledInstance(bench, bench.ideal_values(), settings, scales, folding,
                            time.perf_counter() - t0, complexity)


def folding_weights(spec: NoiseSpec) -> dict[str, float] | None:
    """Gate error weights used to choose partially folded gates (None if the spec is gate-noiseless)."""
    w = {g: gate_error_weight(spec, g) for g in (*NOISY_1Q, *NOISY_2Q)}
    return {**w, "rz": 0.0} if sum(w.values()) > 0 else None


class ConditionRunner:
    """Runs all methods for one (instance, noise) condition at a given shot budget and repetition."""

    def __init__(self, ci: CompiledInstance, spec: NoiseSpec, cfg: ExperimentConfig, block: BlockSpec,
                 sim: NoisySimulator) -> None:
        self.ci, self.spec, self.cfg, self.block, self.sim = ci, spec, cfg, block, sim
        self.methods = [METHODS[m] for m in block.methods]
        self.cal_mode = calibration_mode(ci.bench.n_qubits, cfg.readout.full_max_qubits)
        self.cal_circuits = calibration_circuits(ci.bench.n_qubits, self.cal_mode)

    # ---------------------------------------------------------------- sampling
    def _sample(self, plan: ShotPlan, rng: np.random.Generator, need: set[float]) -> tuple[dict, dict, float]:
        counts: dict[tuple[int, float], np.ndarray] = {}
        tsamp: dict[tuple[int, float], float] = {}
        for si, st in enumerate(self.ci.settings):
            for s in sorted(need):
                t0 = time.perf_counter()
                counts[(si, s)] = self.sim.sample((st.basis, s), st.folded[s], plan.shots_by_scale[s], rng)
                tsamp[(si, s)] = time.perf_counter() - t0
        return counts, tsamp, 0.0

    def _calibrate(self, shots: int, rng: np.random.Generator) -> tuple[ReadoutCorrector | None, str, float]:
        t0 = time.perf_counter()
        cc = {j: self.sim.sample(("cal", j), c, shots, rng) for j, c in self.cal_circuits}
        try:
            corr = ReadoutCorrector(
                estimate_assignment(cc, self.ci.bench.n_qubits, self.cal_mode),
                self.cfg.readout.physicality, self.cfg.readout.condition_warning,
                self.cfg.readout.condition_failure)
            return corr, "", time.perf_counter() - t0
        except MitigationError as exc:
            return None, f"calibration: {exc}", time.perf_counter() - t0

    def _estimate(self, m: MethodSpec, f: np.ndarray, si: int, counts: dict, corr: ReadoutCorrector | None,
                  scales: list[float]) -> Estimate:
        if m.readout and corr is None:
            raise MitigationError("no valid calibration")
        if not m.zne:
            c = counts[(si, 1.0)]
            return corr.estimate(f, c) if m.readout and corr else baseline_estimate(f, c)
        eff = self.ci.settings[si].effective if self.block.zne.use_effective_scales else {s: s for s in scales}
        if m.readout and corr:
            return combined_estimate(f, {eff[s]: counts[(si, s)] for s in scales}, corr, m.extrapolation or "linear")
        pts = [baseline_estimate(f, counts[(si, s)]) for s in scales]
        return extrapolate(np.array([eff[s] for s in scales]), np.array([p.value for p in pts]),
                           np.array([p.stderr for p in pts]), m.extrapolation or "linear")

    def _rows(self, comparison: str, m: MethodSpec, plan: ShotPlan, counts: dict, tsamp: dict,
              corr: ReadoutCorrector | None, cal_err: str, t_cal: float) -> list[dict[str, Any]]:
        rows = []
        scales = sorted(plan.shots_by_scale)
        for si, st in enumerate(self.ci.settings):
            for o in st.observables:
                t0 = time.perf_counter()
                status, reason = "ok", ""
                try:
                    est = self._estimate(m, st.weights[o.name], si, counts, corr, scales)
                except (MitigationError, np.linalg.LinAlgError) as exc:
                    est, status, reason = Estimate(float("nan"), float("nan")), "failed", cal_err or str(exc)
                t_post = time.perf_counter() - t0
                ideal = self.ci.ideal[o.name]
                err = est.value - ideal
                rows.append({
                    "comparison": comparison, "method": m.name, "setting": st.basis, "observable": o.name,
                    "primary_observable": o.primary, "estimate": est.value, "stderr_est": est.stderr,
                    "ideal": ideal, "error": err, "abs_error": abs(err), "sq_error": err**2,
                    "primary_shots": plan.primary_shots, "calibration_shots": plan.calibration_shots,
                    "total_shots": plan.total_shots, "n_executions": plan.n_executions,
                    "n_scales": len(scales), "shots_by_scale": str({k: v for k, v in plan.shots_by_scale.items()}),
                    "t_sampling_s": sum(tsamp[(i, s)] for i in range(len(self.ci.settings)) for s in scales),
                    "t_calibration_s": t_cal if m.readout else 0.0, "t_postprocess_s": t_post,
                    "readout_cond": est.diagnostics.get("readout_cond", np.nan),
                    "readout_negative_mass": est.diagnostics.get("readout_negative_mass", np.nan),
                    "readout_ill_conditioned": bool(est.diagnostics.get("readout_ill_conditioned", False)),
                    "zne_gamma_l1": est.diagnostics.get("zne_gamma_l1", np.nan),
                    "zne_vandermonde_cond": est.diagnostics.get("zne_vandermonde_cond", np.nan),
                    "status": status, "failure_reason": reason,
                })
        return rows

    def _plan(self, m: MethodSpec, comparison: str, shots: int) -> ShotPlan:
        z = self.block.zne
        return plan_shots(m, comparison, shots, len(self.ci.settings), z.scale_factors, len(self.cal_circuits),
                          self.cfg.readout.calibration_shots_equal_primary,
                          self.cfg.readout.calibration_fraction_equal_budget, z.allocation_equal_budget)

    # ---------------------------------------------------------------- public
    def run_rep(self, shots: int, rep: int, labels: tuple) -> tuple[list[dict], list[dict]]:
        seed = self.cfg.seed
        rows: list[dict] = []
        zpts: list[dict] = []
        any_ro = any(m.readout for m in self.methods)
        scales = self.ci.scales
        # Comparison A: one shared draw (common random numbers -> paired comparisons)
        rng = rng_for(seed, *labels, shots, rep, "A")
        full = ShotPlan({s: shots for s in scales}, 0, len(self.ci.settings), 0)
        counts, tsamp, _ = self._sample(full, rng, set(scales))
        corr, cal_err, t_cal = (None, "", 0.0)
        if any_ro:
            cal_n = self._plan(METHODS["readout"], "A", shots).calibration_shots_per_circuit
            corr, cal_err, t_cal = self._calibrate(cal_n, rng)
        if "A" in self.block.comparisons:
            for m in self.methods:
                rows += self._rows("A", m, self._plan(m, "A", shots), counts, tsamp, corr, cal_err, t_cal)
            for si, st in enumerate(self.ci.settings):
                for o in st.observables:
                    for s in scales:
                        raw = baseline_estimate(st.weights[o.name], counts[(si, s)]).value
                        ro = corr.estimate(st.weights[o.name], counts[(si, s)]).value if corr else np.nan
                        zpts.append({"observable": o.name, "scale": s, "raw": raw, "readout_corrected": ro,
                                     "ideal": self.ci.ideal[o.name]})
        if "B" in self.block.comparisons:
            for m in self.methods:
                plan = self._plan(m, "B", shots)
                if m.name == "baseline":  # identical plan to A: reuse the same draw
                    rows += self._rows("B", m, plan, counts, tsamp, None, "", 0.0)
                    continue
                rb = rng_for(seed, *labels, shots, rep, "B", m.name)
                cb, tb, _ = self._sample(plan, rb, set(plan.shots_by_scale))
                cr, ce, tc = (None, "", 0.0)
                if m.readout:
                    cr, ce, tc = self._calibrate(plan.calibration_shots_per_circuit, rb)
                rows += self._rows("B", m, plan, cb, tb, cr, ce, tc)
        return rows, zpts
