# Methodology

## 1. Circuits and observables
| Family | Instances | Observables (ideal) | Primary |
|---|---|---|---|
| Bell | `cx`, `cz` variants; `cx` with 2 identity-equivalent CX–CX pairs (`pad2`, a depth knob) | ⟨XX⟩=1, ⟨ZZ⟩=1, ⟨YY⟩=−1 | XX |
| GHZ | n = 3, 4, 5, 6, 8 (linear CX chain) | ⟨X^⊗n⟩=1, ⟨Z₀Z_{n−1}⟩=1 | X_all |
| QAOA Max-Cut | n=4 (seed 7), n=6 (seed 11), G(n, 0.5) conditioned on connectivity; p = 1, 2 | normalised cut ⟨C⟩/\|E\| | cost_norm |

QAOA angles are optimised **noiselessly** (12-start Nelder–Mead, seeded). They are then fixed, so that noise and mitigation are
evaluated at the same parameters. Max-Cut is solved exactly by brute force, and approximation ratios are stored. Ideal references come from
exact statevector expectation values. Observables are grouped by measurement basis, giving one execution per *setting*.

## 2. Compilation
Circuits are transpiled to {rz, sx, x, cx} (optimization level 1, fixed seed, all-to-all connectivity: no routing,
which is a limitation). Barriers stop the transpiler from cancelling Bell padding and folds.

## 3. Noise models (phenomenological, not hardware-derived)
- Depolarizing channel with Qiskit parameter λ₁ on sx/x and λ₂ on cx. rz is virtual and noiseless.
- Independent asymmetric readout error with p(1|0) = 0.8 r and p(0|1) = 1.2 r.
- Variants: symmetric readout; depolarizing composed with thermal relaxation (T1 = 100 µs, T2 = 80 µs, 35/300 ns gates).
- Levels (λ₁, λ₂, r): low (5e−4, 5e−3, 5e−3), moderate (2e−3, 1.5e−2, 2e−2), high (5e−3, 3e−2, 5e−2).
- Sensitivity sweeps around "moderate": gate multiplier ∈ {0, 0.5, 1, 2, 3, 4, 6} at fixed readout, and readout multiplier ∈
  {0, 0.25, 0.5, 1, 1.5, 2.5, 4, 6} at fixed gate noise.

## 4. Sampling modes
- `aer`: AerSimulator with the full noise model, seeded per call.
- `exact` (default for the large runs): the noisy distribution is computed once per circuit, by Aer density-matrix simulation
  plus the exact readout channel, and shots are drawn from it multinomially. For terminal measurements this is the same
  statistical model. This is tested (χ² test), and the pilot compares the two modes over 288 conditions × 30 repetitions.

## 5. Mitigation methods
- **Baseline:** ⟨O⟩ = Σₓ p̂(x) f(x).
- **REM:** calibration by basis-state preparation, using full 2ⁿ circuits for n ≤ 3 and the tensored model (|0…0⟩, |1…1⟩) above that. The calibration circuits use the same noisy x gates. Correction is the unconstrained inverse (unbiased for the linear functional). The condition number is recorded; above 10³ a warning is raised and the result flagged; above 10¹² or when singular the result is **failed** and the row is kept with a reason. Simplex projection is optional.
  The reported standard error is the multinomial error of g = A^{−T} f (it excludes calibration uncertainty). The resulting under-coverage is
  measured as the empirical/predicted variance ratio.
- **ZNE:** global or local unitary folding (G → G(G†G)^k). Partial folds are chosen by **error-weighted** gate selection,
  and the extrapolation uses the **measured** scale λ_eff (the ratio of first-order gate-error mass). Extrapolation: least-squares linear fit or
  Richardson (Lagrange) interpolation. Both are linear in the data, E₀ = Σγᵢ Eᵢ, so Var = Σγᵢ² Var(Eᵢ). The weights γ, ‖γ‖₁ and the
  Vandermonde condition number are recorded.
- **REM+ZNE:** one calibration is shared by all scale points. Readout correction is applied at every scale point *before*
  extrapolation, because measurements are not folded and readout error therefore does not scale with λ.

## 6. Resource accounting
Let N be the shots per circuit, S the number of measurement settings, K the number of scale factors, and M the number of calibration circuits.
- **Comparison A (equal primary shots):** each primary execution gets N shots. Baseline total = N·S. REM = N·S + M·N.
  ZNE = N·S·K. REM+ZNE = N·S·K + M·N. The overhead is reported separately.
- **Comparison B (equal total budget):** T = N·S for every method. REM gives 20 % of T to calibration (split evenly over M). ZNE
  allocates per setting in proportion to |γᵢ| (Krebsbach et al. 2022). Rounding down means usage is ≤ T (minimum utilisation ≈ 98 %).
- Sampling overhead O = N_total,mit / N_total,base. Timing records sampling, calibration and post-processing separately.
  The wall-clock timing study uses the per-shot Aer pilot only.
- The validator (`experiments/validation.py`) enforces these rules on every dataset.

## 7. Metrics
Bias, MSE, RMSE, MAE, variance (ddof = 1), median, 95 % percentile-bootstrap CIs (2000 resamples) for the mean, RMSE and MAE.
Efficiency: η = [(E_b − E_m)/E_b] / [(C_m − C_b)/C_b] with E = RMSE and C = total shots (dimensionless). Edge cases are
labelled (`free_improvement`, `costly_degradation`, …). Established comparators: μ = (E_b/E_m)/√(C_m/C_b) (Russo et al. 2023)
and the work-normalised MSE ratio.

## 8. Statistics
At least 30 independent repetitions per condition, with streams from `SeedSequence(root, spawn_key=hash(labels))`. Comparison A uses common random
numbers (all methods share the draws), so tests are paired. In comparison B the draws are independent but paired by repetition index.
Tests: Wilcoxon signed-rank on |error| with matched-pairs rank-biserial effect size. Paired-bootstrap CI for ΔMSE. Sign-flip
permutation tests are available. BH-FDR is applied over all tests, and Holm is also reported.

## 9. Design strategy (a reduced factorial)
The full factorial (13 instances × 5 noise models × 7 budgets × 6 methods × 2 comparisons × 100 repetitions) is
documented as the `full` profile and **was not executed**. The executed `standard` profile combines:
the core grid (12 instances × 3 levels × 7 budgets), two one-factor-at-a-time noise sweeps, noise-model variants and three ZNE-design blocks
(local 1,3,5; global 1,2,3; global 1,3,5,7).
