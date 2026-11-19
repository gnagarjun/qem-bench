# Supplementary Material

All quantities are generated from `results/aggregated/standard/` and `results/aggregated/pilot/` (simulated data).

## S1. Experiment configurations
The exact resolved configurations are in `results/experiments/<run_id>/config_resolved.json` (config hash in the
directory name). Source YAML: `configs/default.yaml`, `noise_models.yaml`, `shot_budgets.yaml`, `circuits.yaml` and
`experiments.yaml` (profiles `smoke`, `pilot`, `standard`, `full`).

| Block | Instances | Noise | Shots per circuit | Purpose |
|---|---|---|---|---|
| core | 12 (Bell×3, GHZ 3–8, QAOA n4/n6 × p1/p2) | low, moderate, high | 256 … 16384 (7) | RQ1–RQ6 |
| readout_sweep | bell_cx, ghz_4, ghz_6, qaoa_n4_p1 | moderate gates, readout ×{0 … 6} | 4096 | H1 |
| gate_sweep | same | moderate readout, gates ×{0 … 6} | 4096 | H2 |
| noise_variants | ghz_4, qaoa_n4_p1 | symmetric readout; T1/T2 | 1024, 4096, 16384 | model sensitivity |
| zne_local_135 / zne_global_123 / zne_global_1357 | ghz_4, ghz_6, qaoa_n4_p1 | moderate, high | 1024, 4096, 16384 | ZNE design |
| pilot_aer / pilot_exact | bell_cx, ghz_4, qaoa_n4_p1 | moderate, high | 1024, 4096 | sampling-mode equivalence, timing |

Repetitions: 30 per condition. Root seed: 20260601.

## S2. Full metric definitions
See `docs/methodology.md` §6–8 and `src/qem_bench/metrics/`. Summary:
Bias = mean(θ̂) − θ; MSE = mean((θ̂ − θ)²); RMSE = √MSE; MAE = mean|θ̂ − θ|; Var with ddof = 1;
O = N_tot,mit / N_tot,base; η = [(E_b − E_m)/E_b]/[(C_m − C_b)/C_b] with edge-case labels;
μ = (E_b/E_m)/√(C_m/C_b); WNMSE = MSE_m C_m /(MSE_b C_b). Note: μ > 1 ⇔ WNMSE < 1.

## S3. Statistical tables
- `results/aggregated/standard/comparisons.csv`: 12,798 paired tests (p, BH q, Holm p, rank-biserial r, ΔMSE CI, η, μ).
- `results/aggregated/standard/aggregated.csv`: 8,532 conditions × all summary statistics with bootstrap CIs.
- `paper/tables/*.tex`: core summary, family summary, hypothesis verdicts, timing.
- `results/aggregated/pilot/mode_equivalence.csv`: exact vs per-shot sampling tests (288 conditions).

## S4. Noise-model variants (median relative RMSE change vs baseline)
| Noise | Comparison | REM | ZNE-lin | ZNE-Rich | REM+ZNE-lin | REM+ZNE-Rich |
|---|---|---|---|---|---|---|
| moderate_symmetric | A | −0.64 | −0.30 | −0.23 | −0.85 | −0.83 |
| moderate_symmetric | B | −0.62 | −0.26 | −0.30 | −0.81 | −0.70 |
| moderate_thermal | A | −0.59 | −0.31 | −0.36 | −0.84 | −0.85 |
| moderate_thermal | B | −0.57 | −0.30 | −0.32 | −0.79 | −0.72 |

## S5. Additional figures
All 12 figures are in `results/figures/` (PNG at 300 dpi and PDF), indexed with captions in `figures.json`.

## S6. Reproduction
```bash
uv sync --extra dev && uv run pytest && uv run bash scripts/reproduce_all.sh
```
Expected runtime is about 10 minutes on 4 cores. Outputs are verified by `scripts/validate_results.py`.

## S7. Known deviations and fixes during development
- Partial global folding originally selected gates by raw gate count, giving λ_eff ∈ {1.18, 2.93} for nominal λ = 2 on
  GHZ-4. It was fixed by error-weighted selection plus extrapolation on the measured λ_eff, and guarded by a regression test. The affected run was
  discarded *before* any analysis was reported and fully re-executed.
- REM with zero readout error still changed estimates (median −7 %), because noisy calibration x-gates are attributed to readout.
  This is reported as an observed artefact, not corrected.
