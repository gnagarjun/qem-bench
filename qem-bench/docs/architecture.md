# Architecture

| Package | Responsibility | Must not depend on |
|---|---|---|
| `config.py` | Validated configuration (pydantic, `extra="forbid"`), config hash, profile merging | everything else |
| `seeds.py` | `SeedSequence` streams keyed by labels (block, instance, noise, N, rep, comparison, method) | – |
| `circuits/` | Logical circuits, observables, measurement settings, exact references | noise, mitigation |
| `noise/` | Aer noise models, readout channel, calibration circuits, assignment estimation, noise-scaling validation | mitigation |
| `mitigation/` | Pure estimators over count vectors (baseline, readout, zne, combined); method registry | execution |
| `execution/` | Transpilation, folding, the simulator backend interface (`NoisySimulator.sample`), shot plans, condition runner | analysis |
| `experiments/` | Design enumeration, orchestration, resume, manifests, dataset validation, environment capture | visualization |
| `analysis/` | Aggregation, paired comparisons, Pareto, hypothesis rules | execution |
| `visualization/` | Figures from saved tables only | execution |

**Backend extensibility.** A hardware backend would implement `sample(key, circuit, shots, rng) -> counts`, record
backend name, calibration snapshot, date and queue time, and run with `sampling_mode="hardware"`. Hardware data must be stored
in separate run directories. No hardware backend is implemented (it is not required by the core project).

**Method extensibility.** `MethodSpec(name, readout, zne, extrapolation)` plus `plan_shots`. PEC, CDR and symmetry
verification would add fields for quasi-probability sampling and post-selection cost.

**Data schema (v1.0.0).** One raw row per (block, instance, noise, N, repetition, comparison, method, observable), with:
estimate, stderr_est, ideal, error, abs_error, sq_error, primary/calibration/total shots, n_executions, n_scales, shots_by_scale,
the sampling/calibration/post-processing times, readout condition number and negative quasi-probability mass, zne ‖γ‖₁ and Vandermonde condition,
status, failure_reason, plus run metadata (run_id, config_hash, timestamp, root_seed, circuit parameters, noise parameters, sampling
mode, folding, scales, calibration mode). The `circuits/` table holds complexity (gate counts, transpiled and folded depth),
λ_eff, unitary-preservation checks, exact noisy values, state fidelity, and construction/transpile/distribution times.
