# QEM-Bench

**A resource-aware benchmarking framework for quantum error mitigation (QEM) under noisy circuit execution.**

QEM-Bench answers one practical question: *when you mitigate errors on a quantum computer, is the accuracy you gain
worth the extra shots, circuits and time you pay for it?* The framework runs four mitigation configurations on a suite of
benchmark circuits and records **every shot** each method consumes. It then compares the methods under explicit and
enforceable accounting rules, with full statistical testing.

> **Read this first.** Every result in this repository comes from a **simulator** (Qiskit Aer with simplified,
> phenomenological noise). None of it is a real-hardware measurement. The manuscript in `paper/` is an unreviewed draft and
> has not been submitted anywhere. Section 7 below explains what is needed to run on real hardware.

---

## Contents
1. [The project in five minutes](#1-the-project-in-five-minutes)
   - [Execution record: how the reported results were produced](#execution-record-how-the-reported-results-were-produced)
2. [How to read the results](#2-how-to-read-the-results)
3. [Why this matters to a quantum computing company today](#3-why-this-matters-to-a-quantum-computing-company-today)
4. [Running it on your Mac](#4-running-it-on-your-mac-local-simulator)
5. [Getting more results: extend, compare, improve](#5-getting-more-results-extend-compare-improve)
6. [Repository map](#6-repository-map)
7. [Running the experiments on real quantum hardware](#7-running-the-experiments-on-real-quantum-hardware)
8. [Limitations](#8-limitations) · [Citation](#citation) · [License](#license)

> Hosting the web viewer on AWS? See [`../DEPLOY_AWS_LIGHTSAIL.md`](../DEPLOY_AWS_LIGHTSAIL.md).


---

## 1. The project in five minutes

### The problem
Today's quantum processors are noisy. Gates are imperfect and measurements misread qubits. As a result, the expectation values you estimate
(energies, correlations, cost functions) are **biased**. *Error mitigation* reduces that bias without full error correction,
but it is never free:

| Method | What it does | What it costs |
|---|---|---|
| **Baseline** | Runs the circuit and averages the measurement outcomes | — (the reference) |
| **Readout error mitigation (REM)** | Runs calibration circuits to learn how often each qubit is misread, then mathematically undoes those errors | Calibration circuits and shots; higher variance |
| **Zero-noise extrapolation (ZNE)** | Deliberately amplifies the noise (by "folding" gates, G → G G† G) at scale factors λ = 1, 3, 5, then extrapolates back to λ = 0 | Runs every circuit 3 or more times, and the extrapolation amplifies statistical noise (variance ×4.2 for Richardson) |
| **REM + ZNE** | Corrects readout at every noise level, then extrapolates | Both costs together |

A method that halves the error but needs four times the shots may be *worse* than simply spending those four times the shots on the
unmitigated circuit. QEM-Bench measures this trade-off.

### The two accounting rules (the core idea)
- **Comparison A, "equal primary shots":** every circuit execution gets N shots. Mitigation overhead (calibration, extra noise
  levels) is **added on top** and reported separately. This is how most papers present mitigation.
- **Comparison B, "equal total budget":** every method gets the **same total shot budget** T = N × (number of measurement
  settings). Mitigation must pay for its calibration and noise-scaled runs **out of that budget**. This is the fair
  "same money, which method wins?" comparison.

A validator (`src/qem_bench/experiments/validation.py`) enforces these rules on every row of data. For example, it fails the dataset
if any method in comparison B spends more than the baseline's budget.

### What was run
- **Circuits:** Bell states (3 variants), GHZ states (3, 4, 5, 6 and 8 qubits) and QAOA Max-Cut (4 and 6 qubits, depth p = 1 and 2). All have exactly known ideal answers.
- **Noise:** low, moderate and high gate and readout noise, plus sweeps of gate noise (0–6×) and readout noise (0–6×), plus relaxation (T1/T2) and symmetric-readout variants.
- **Shot budgets:** 256 to 16,384 shots per circuit.
- **Scale:** 30 independent repetitions per condition, 8,532 conditions and 255,960 estimates, with 12,798 paired statistical tests corrected for multiple comparisons.
- **Pilot check:** a pilot confirmed that the fast "exact-distribution" sampling mode gives the same results as genuine per-shot Aer sampling (0 of 288 conditions differed after correction).

### Headline findings (simulated, see the caveats in Section 8)
| Method | Median error change vs baseline, **A** | Shots used vs baseline (A) | Median error change, **B** (equal budget) | Beats "just spend the shots on baseline" (μ > 1) |
|---|---|---|---|---|
| REM | −60 % | 2.3× | −54 % | 84 % of conditions |
| ZNE-linear | −22 % | 3.0× | −19 % | 10 % |
| ZNE-Richardson | −22 % | 3.0× | −19 % | 18 % |
| REM+ZNE-linear | **−81 %** | 4.3× | **−68 %** | 89 % |
| REM+ZNE-Richardson | −74 % | 4.3× | −55 % | 77 % |

Interpretation:
1. **Readout mitigation is the best value.** It removes a large, easy share of the bias for a modest cost.
2. **REM + ZNE is the most accurate**, and it stays the most accurate even when it must pay for its overhead from the same budget.
3. **ZNE alone is statistically significant but usually inefficient.** It reduces the error, but in only 10–18 % of conditions did it beat simply
   spending its extra shots on the baseline.
4. **Small budgets punish aggressive extrapolation.** At 256 shots under an equal budget, Richardson ZNE was significantly *worse*
   than doing nothing in 17 % of conditions.
5. **A pitfall we found:** naive partial gate folding (choosing gates by count) scaled the noise by 1.18× or 2.93× when 2× was intended.
   QEM-Bench measures the noise scaling it actually achieves and extrapolates on that measured value.

### Hypothesis verdicts
The decision rules were fixed in advance in [`docs/research/hypotheses.md`](docs/research/hypotheses.md) and applied mechanically.

| Hypothesis | Verdict |
|---|---|
| H1: REM reduces bias when readout errors dominate | **Supported** (all 40 readout-dominated conditions) |
| H2: ZNE helps at moderate noise but deteriorates at high noise or low budgets | **Supported only through the budget part.** The noise part was *not* observed in the tested range |
| H3: combining methods can beat both parts, at higher cost | **Supported** (69 % of conditions under A, 40 % under B) |
| H4: deeper circuits make estimation harder | **Not supported** by the pre-specified pooled test. An exploratory within-GHZ analysis does show the trend |
| H5: sometimes no mitigation is just as good at equal budget | **Supported (weak form):** 3.3 % of equal-budget conditions, all at low noise and small budgets |

Unfavourable and null results are reported deliberately.

---

## Execution record: how the reported results were produced

**Yes. Every number in this README, in `summary.json` and in the paper comes from simulations that were actually run**, with the code in
this repository, inside a cloud development container where the project was built. No value was typed in by hand. The figures
and tables are regenerated from the saved Parquet data, and `scripts/validate_results.py` checks the SHA-256 hashes of that data.

### Machine and software
| Item | Value (from `results/experiments/<run>/environment.json`) |
|---|---|
| Host | Cloud development container (Linux 6.12, **aarch64**), 4 vCPUs, about 15 GB RAM. CPU model not reported by the container |
| Python | 3.11.18 (isolated virtual environment `/app/qem-bench/.venv`, created with `uv`) |
| Quantum stack | qiskit 2.2.3, qiskit-aer 0.17.2 (CPU only, no GPU) |
| Scientific stack | numpy 2.4.6, scipy 1.17.1, pandas 3.1.1, pyarrow 26.0.1, matplotlib 3.11.2, seaborn 0.13.2, pydantic 2.14.3 |
| Code version | git commit `503f25e` (recorded automatically in `environment.json`) |
| Root seed | 20260601 (all repetition streams derive from it with `SeedSequence`) |

The timestamps below come from the container clock, as written into the run IDs and manifests.

### What was executed, and how long it took
| Step | Command | Run ID / output | Wall-clock |
|---|---|---|---|
| 1. Pilot experiment | `scripts/run_experiment.py --profile pilot` | `pilot_20261119T034457Z_4b7d0bd7351ab767`: 24 conditions × 30 reps, 17,280 estimates | **60.7 s** |
| 2. Pilot analysis | `scripts/analyze_results.py` | `results/aggregated/pilot/` (sampling-mode equivalence, timing study) | about 7 s |
| 3. Standard experiment | `scripts/run_experiment.py --profile standard` | `standard_20261119T034606Z_87821ca68ff11fc6`: 8,532 conditions × 30 reps, **255,960 estimates**, 354 Parquet files, 25 MB | **80.9 s** |
| 4. Standard analysis | `scripts/analyze_results.py` | aggregation, 12,798 paired tests (2,000 bootstrap resamples each), Pareto, hypothesis verdicts | about 60 s |
| 5. Figures, tables, validation | `generate_figures.py`, `validate_results.py` | 12 figures (PNG + PDF), LaTeX tables, `ALL CHECKS PASSED` | about 20 s |
| 6. Paper build | `pdflatex` + `bibtex` | `paper/main.pdf` (12 pages) | about 10 s |

**End to end, the whole study takes about 4–5 minutes on this 4-vCPU container** (all steps were chained in `scripts/reproduce_all.sh`).
A modern Mac should be in the same range, but timings are machine-specific.

### Why it is that fast, and what "simulated" means here
The circuits are small (2–8 qubits), so Qiskit Aer can simulate them exactly.

- **Standard run (`sampling_mode: exact`).** For each distinct physical circuit (setting × noise-scale fold × noise model, 685 circuit/noise
  combinations in total), Aer's **density-matrix simulator** computes the full noisy output distribution once. Gate noise comes from the Aer noise model, and
  readout error is applied by the exact classical channel. Each repetition then draws its N shots from that distribution with a seeded multinomial sampler.
  For circuits that end in measurements, this is statistically the same as shot-by-shot simulation. The total Aer density-matrix time was only **about 3 s**.
  Most of the 81 s is the Python bookkeeping for the 6 methods × 2 comparisons × 30 repetitions, plus calibration and extrapolation.
- **Pilot (`sampling_mode: aer` block).** Every execution was a genuine per-shot `AerSimulator.run(..., shots=N, seed_simulator=...)` with the
  full noise model, including readout error. The pilot also repeated the identical design in exact mode. Across 288 matched conditions,
  **no mean differed after FDR correction** (raw p < 0.05 in 4.9 % of conditions, close to the 5 % expected by chance), and 1 of 288 variances differed. This is the
  evidence that the fast mode is valid. The wall-clock timing study in the paper (REM about 2.6×, ZNE about 3.6×, REM+ZNE about 5.2× the baseline time) also comes
  from this per-shot pilot.

### What was **not** executed
- No real quantum hardware was used (see Section 7).
- The `full` profile (100 repetitions, larger grid) is configured but was not run.
- No GPU, no MPS or tensor-network methods, and nothing above 8 qubits.

### Development history that affected the data
1. A first pilot and standard run were executed and then **discarded** before any results were reported. Validation tests showed that partial gate folding
   (scale factor 2) achieved λ_eff = 1.18 and 2.93 instead of 2.0. The fix (error-weighted folding plus extrapolation on the measured λ_eff) was
   added with a regression test, and **both runs were re-executed from scratch**. The run IDs above are the re-executed runs. Only the `zne_global_123`
   design block was materially affected; the odd-integer folds (1, 3, 5) used everywhere else were exact in both versions.
2. After the re-run, the figures were regenerated once with a layout-only style change (no data change).

### How to check this yourself
```bash
cat results/experiments/standard_*/manifest.json   # run ID, completion time, wall-clock seconds, SHA-256 + row count per file
cat results/experiments/standard_*/environment.json
cat results/experiments/standard_*/validation_report.json
uv run python scripts/validate_results.py --agg results/aggregated/standard     # re-verifies hashes and accounting
uv run bash scripts/reproduce_all.sh                                             # re-runs everything; fixed seeds give the same estimates
```
Re-running with the same configuration reproduces **bit-identical estimates**: `tests/reproducibility/` checks this. Only the timings and run IDs change.
Note that raw Parquet files are git-ignored because of their size. After cloning, run `reproduce_all.sh` (about 5 min) to regenerate them, or
use the bundled `data/reference/demo/` subset.

---

## 2. How to read the results

### Where things are
| Path | What it contains | Read it when you want… |
|---|---|---|
| `results/aggregated/standard/summary.json` | Machine-readable summary: run IDs, config hash, hypothesis verdicts, per-method medians, noise-scaling checks, environment | the headline numbers |
| `results/aggregated/standard/aggregated.csv` | One row per **condition** (instance × noise × shots × comparison × method × observable): mean, bias, variance, RMSE with 95 % CI, total shots, overhead, timings | to look up any single condition |
| `results/aggregated/standard/comparisons.csv` | One row per **paired test** (method vs reference): ΔRMSE, ΔMSE CI, Wilcoxon p, BH q, effect size r, η, μ, outcome | to know whether a difference is real |
| `results/aggregated/standard/pareto.csv` | Conditions flagged as Pareto-optimal (no other configuration is both cheaper and more accurate) | the most efficient configurations |
| `results/aggregated/standard/circuits.csv` | Circuit complexity, achieved noise scale λ_eff, unitary-preservation checks, state fidelity | to audit the noise scaling |
| `results/aggregated/pilot/` | Sampling-mode equivalence and the wall-clock timing study | to check the simulator shortcut and the time cost |
| `results/experiments/<run_id>/raw/*.parquet` | **Raw data**: one row per repetition (every individual estimate), with all metadata | to recompute anything |
| `results/figures/` | The 12 figures (PNG at 300 dpi and PDF), indexed in `figures.json` | for visual inspection |
| `paper/main.pdf`, `paper/main.tex` | The draft manuscript built from these outputs | for the narrative |

### Reading a row of `aggregated.csv`
Example: `instance=ghz_4, noise=moderate, shots_per_circuit=4096, comparison=B, method=readout`.
- `ideal` is the exact noiseless answer. `mean` is the average estimate over 30 repetitions. `bias = mean − ideal`.
- `rmse` is the typical total error, combining bias and spread. **Lower is better.** `rmse_ci_lo` and `rmse_ci_hi` give its 95 % bootstrap interval.
- `total_shots` is everything this method spent. `sampling_overhead` is total_shots divided by the baseline's total_shots (about 1.0 in comparison B by design).
- `rel_rmse_change` is (RMSE − baseline RMSE) / baseline RMSE. A value of **−0.60 means 60 % less error than the baseline.**
- `variance_ratio` is the observed variance divided by the predicted shot-noise variance. Values above 1 mean the error bars understate the uncertainty
  (for REM this happens because calibration noise is not included in the analytic error bar).

### Reading a row of `comparisons.csv`
- `q_bh < 0.05` means the difference is **statistically significant** after correcting for about 12,800 tests.
- `outcome` combines significance with practical size: `better_practical` means significant **and** at least 10 % less error.
- `rank_biserial` (r) is the effect size, from −1 to 1. Negative means the method usually has the smaller error.
- `eta` (η) is the relative error reduction per relative extra shot cost (proposed here). For example, 0.25 means each +100 % of shots bought 25 % less error.
  The value `inf` with category `free_improvement` appears in comparison B, where the extra cost is zero.
- `improvement_factor_mu` (μ) is the established metric (Russo et al., 2023). **μ > 1 means mitigation beat spending the same extra shots on the
  unmitigated circuit.**

### Figure guide
| Figure | Question it answers |
|---|---|
| 01 architecture | How the pipeline fits together |
| 02 depth vs error | Do bigger or deeper circuits get worse? |
| 03 noise sweeps | How does each method respond as gate noise or readout noise grows? |
| 04 method comparison | Which method is most accurate per circuit (A and B side by side)? |
| 05 overhead vs improvement | How much accuracy does each extra shot buy? |
| 06 shots vs RMSE | Does the error keep falling as the budget grows? (The baseline flattens at its bias; mitigated methods keep improving) |
| 07 by family | Do Bell, GHZ and QAOA behave differently? |
| 08 efficiency heatmap | Where is mitigation worth it (blue) or not (red)? |
| 09 Pareto frontier | Which method and budget combinations are not dominated? |
| 10 confidence intervals | Which differences are statistically real? |
| 11 ZNE scale factor | What does the extrapolation actually look like, and do ZNE design choices matter? |
| 12 combined vs individual | Does combining methods beat the better single method? |

### The web results viewer
A read-only dashboard (React + FastAPI) presents the same saved data interactively: verdicts, a filterable condition explorer, RMSE-vs-shots
and Pareto charts, the statistical tests, the figure gallery and provenance. It never computes or invents numbers. It reads a bundle
exported by `scripts/export_viewer_data.py`.

---

## 3. Why this matters to a quantum computing company today

Error mitigation is now the default way to get useful numbers from pre-fault-tolerant hardware. Every major software stack
ships it (for example, IBM's Qiskit Runtime resilience options and Unitary Fund's Mitiq). It is also central to "utility-scale" demonstrations.
The commercial question is no longer *whether* to mitigate but **how to spend a finite QPU budget**. QEM-Bench is built around that question.

| Who | How QEM-Bench is useful |
|---|---|
| **Hardware providers** | Shows which errors are worth fixing in hardware rather than in software. In our data, readout error was the cheapest large bias to remove, so readout fidelity improvements translate directly into fewer mitigation shots. The equal-budget comparison is the right way to show customers "value per QPU-second". |
| **Software and middleware teams** | A neutral harness for testing a new mitigation method against baselines under fixed budgets, with a validator that catches accounting mistakes (calibration shots silently left out, extra noise-scaled runs not counted). |
| **Algorithm and application teams** (chemistry, optimisation, finance) | A decision aid: for a given circuit size, noise level and shot budget, which configuration gives the lowest error per dollar? The Pareto and η/μ outputs give exactly that ranking. |
| **Cloud and QPU resellers, budgeting and FinOps** | Converts mitigation into cost. Comparison A shows the true shot multiplier (2.3× to 4.3× here), which is the multiplier on the QPU bill. |
| **Research and benchmarking groups** | Reproducible, statistically defensible methodology: paired tests, FDR control, effect sizes, pre-registered hypotheses, and raw data with SHA-256 manifests. |

What it does **not** yet show: performance on real devices, at large scale (more than 8 qubits) or under correlated and coherent noise. These are exactly
the regimes a company would need to validate next (Section 7).

---

## 4. Running it on your Mac (local simulator)

Tested stack: Python 3.11, Qiskit 2.2.3, Qiskit Aer 0.17.2. Qiskit Aer publishes pre-built wheels for macOS on both Apple Silicon (arm64) and
Intel, so no compiler is needed.

### 4.1 Install
```bash
# 1. Tools (Homebrew)
brew install uv git            # uv manages Python and dependencies (or: curl -LsSf https://astral.sh/uv/install.sh | sh)

# 2. Get the code
git clone <your-repo-url> qem-bench && cd qem-bench

# 3. Create the environment with the exact pinned versions from uv.lock (uv downloads Python 3.11 if needed)
uv python install 3.11
uv sync --extra dev

# 4. Verify (about 15 s): 76 tests covering unit, integration, scientific-validation and reproducibility
uv run pytest
```
If you prefer plain pip: `python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.

### 4.2 First runs
```bash
uv run python scripts/run_experiment.py --profile smoke     # about 2 s, tiny end-to-end run plus dataset validation
uv run python scripts/run_pilot.py                          # a few minutes: real per-shot Aer vs exact mode, timing study
uv run python scripts/analyze_results.py --run data/reference/demo/run --out /tmp/demo_agg   # analysis on bundled demo data
```

### 4.3 Reproduce the full reported study
```bash
uv run bash scripts/reproduce_all.sh
# = pilot + standard run + analysis + 12 figures + validation + paper tables + viewer bundle (about 5 min on the 4-core machine used here)
uv run python scripts/validate_results.py --agg results/aggregated/standard   # prints ALL CHECKS PASSED
```
Optional: build the paper (`brew install --cask mactex-no-gui`, then `make paper`), and open the notebooks with `uv run --with jupyter jupyter lab notebooks/`.

### 4.4 Mac tips
- **Speed:** most large runs use `sampling_mode: exact`, which simulates each circuit once with Aer's density-matrix method and then
  samples. It is fast on a laptop. `sampling_mode: aer` (genuine per-shot simulation) is slower but closer to the physics of a shot. Use it for timing studies.
- **Memory:** density-matrix simulation needs 16·4ⁿ bytes, so 8 qubits is trivial, 12 qubits is about 270 MB and 14 qubits is about 4 GB. For more than 12 qubits, switch the
  distribution step to statevector or trajectory methods (see 5.4).
- **Interrupted runs:** `uv run python scripts/run_experiment.py --profile standard --resume results/experiments/<run_id>` completes only the missing chunks.
- **Timings are machine-specific.** Your Mac's wall-clock numbers will differ from ours. Compare timings only within a single machine.

---

## 5. Getting more results: extend, compare, improve

Everything is driven by YAML in `configs/`. **Changing a configuration changes its hash, so every variant lands in its own run
directory and nothing is overwritten.**

### 5.0 From the browser: the "Run Simulations" tab
The web viewer can also start new simulator runs. Sign in with the owner password (`ADMIN_PASSWORD` in `backend/.env`).
Then pick the circuits, noise levels (including scaled ones such as "high, gate noise ×2"), shot budgets, mitigation
methods, accounting rules (A/B), repetitions, ZNE scale factors, folding mode and an optional seed. The backend runs
`scripts/run_custom.py`, which uses the same runner, validation and `analyze_results.py` as the published study. Each run is
saved on its own in `results/custom_runs/<run_id>/` with its `spec.json`, raw Parquet data, `analysis/` tables and `run.log`.
The viewer then shows its conditions table and the Wilcoxon/BH test outcomes. The published results are never modified.
Anyone can browse runs, only the owner can start, cancel or remove them, and only one run happens at a time. A run is capped
at 20,000 condition-repetitions; small designs finish in a few seconds. Figures and the paper are not rebuilt for custom runs.


### 5.1 Add a noise level (e.g. "what if readout were 3× better?")
`configs/noise_models.yaml`:
```yaml
levels:
  my_better_readout: {p1: 0.002, p2: 0.015, readout_p01: 0.0053, readout_p10: 0.008}
```
Then reference it in a block in `configs/experiments.yaml` as `noise: [{base: my_better_readout}]`. Sweeps are written as
`{base: moderate, gate_multiplier: 2.0, label: g_x2}`.

### 5.2 Add a circuit instance
`configs/circuits.yaml`:
```yaml
  ghz_10:     {family: ghz, params: {n_qubits: 10}}
  qaoa_n8_p1: {family: qaoa, params: {n_qubits: 8, p: 1, edge_prob: 0.5, graph_seed: 3}}
```
A new circuit **family** goes in `src/qem_bench/circuits/` (return a `BenchmarkCircuit` with observables), plus a branch in `circuits/__init__.py`
and an ideal-value test in `tests/scientific_validation/test_circuits.py`.

### 5.3 Define your own experiment profile
```yaml
profiles:
  my_study:
    repetitions: 50
    blocks:
      - name: core
        purpose: My comparison
        instances: [ghz_4, ghz_8, qaoa_n6_p1]
        noise: [{base: moderate}, {base: my_better_readout}]
        shots: all                      # or an explicit list: [1024, 8192]
        zne: {scale_factors: [1.0, 3.0, 5.0], folding: global}
```
```bash
uv run python scripts/run_experiment.py --profile my_study
uv run python scripts/analyze_results.py --run results/experiments/my_study_<UTC>_<hash> --out results/aggregated/my_study
uv run python scripts/generate_figures.py --agg results/aggregated/my_study --out results/figures/my_study
```
Note: the hypothesis verdicts and some figures expect a block named `core`, plus `readout_sweep` and `gate_sweep` for H1/H2. Keep those names if you want them computed.

### 5.4 Compare runs against each other
- **Combine runs in one analysis:** `analyze_results.py --run RUN_A --run RUN_B --out results/aggregated/combined` (use distinct block names per run).
- **Before/after an improvement:** keep the same profile, seeds and instances, change one thing, and compare `aggregated.csv` files on the condition keys (`block, instance, noise, shots_per_circuit, comparison, method, observable`):
```python
import pandas as pd
k = ["block","instance","noise","shots_per_circuit","comparison","method","observable"]
a = pd.read_csv("results/aggregated/standard/aggregated.csv").set_index(k)
b = pd.read_csv("results/aggregated/my_study/aggregated.csv").set_index(k)
print((b.rmse / a.rmse).dropna().describe())      # <1 means the new variant is more accurate
```
- **The full research-scale design** (100 repetitions, 13 instances, 5 noise models) is pre-configured: `uv run python scripts/run_full_benchmark.py --yes`.

### 5.5 High-value improvements to build next
| Improvement | Where | Why |
|---|---|---|
| Exponential / adaptive extrapolation | `mitigation/zne.py` (add weights or a nonlinear fit plus variance by bootstrap) | Depolarizing decay is nearly exponential; linear and Richardson leave about 0.08 residual bias |
| Hardware-derived noise models | `execution/simulator.py`: build the noise model with `NoiseModel.from_backend(FakeBackendV2)` from `qiskit-ibm-runtime` fake backends | A realistic step between our phenomenological noise and real devices |
| Coupling-map-aware compilation | `execution/runner.py` (`transpile(..., coupling_map=...)`) | Adds SWAP overhead, so depth and noise scaling become realistic |
| Correlated readout + M3 | `noise/models.py`, `mitigation/readout.py` | Our uncorrelated readout model flatters the tensored calibration |
| PEC, CDR, symmetry verification, twirling | new modules in `mitigation/`, `MethodSpec` in `mitigation/base.py`, shot plans in `execution/resource_tracker.py` | Wider method coverage under the same accounting rules |
| Larger circuits | swap the density-matrix step for statevector/MPS sampling | Test scaling beyond 8 qubits |

Rules for contributions (see `CONTRIBUTING.md`): every new method needs synthetic-correctness tests **and** explicit shot accounting
for both comparisons. Every bug fix needs a regression test.

---

## 6. Repository map
```
configs/                 YAML: default settings, noise levels, shot budgets, circuit instances, experiment profiles
src/qem_bench/
  config.py seeds.py     validated configuration (pydantic) · reproducible SeedSequence streams
  circuits/              bell, ghz, qaoa (+ exact Max-Cut), observables and measurement settings
  noise/                 Aer noise models, calibration circuits, assignment matrices, noise-scaling validation
  mitigation/            baseline, readout, zne (folding + extrapolation), combined, method registry
  execution/             transpile + fold, simulator backend interface, shot ledger (A/B), condition runner
  metrics/               accuracy, variance, overhead, efficiency (η, μ, WNMSE), statistics (bootstrap, tests, FDR)
  experiments/           design, orchestration (resumable, never-overwrite), dataset validation, environment capture
  analysis/              aggregation, paired comparisons, Pareto, hypothesis rules
  visualization/         the 12 publication figures
scripts/                 run_experiment, run_pilot, run_full_benchmark, analyze_results, generate_figures,
                         validate_results, export_viewer_data, reproduce_all.sh
tests/                   unit · integration · scientific_validation · reproducibility (76 tests)
docs/                    methodology, architecture, reproducibility, research/{literature_review, research_gap, hypotheses}
paper/                   main.tex (+ main.pdf), references.bib, figures/, tables/, supplementary_material.md
data/reference/demo/     small, clearly labelled subset of real simulated data for quick exploration
results/                 pilot/ experiments/ (raw, git-ignored) · aggregated/ · figures/
notebooks/               01–05 exploration, noise, comparison, efficiency, figures
```
Deeper documentation: [methodology](docs/methodology.md) · [architecture](docs/architecture.md) ·
[reproducibility](docs/reproducibility.md) · [literature review](docs/research/literature_review.md).

---

## 7. Running the experiments on real quantum hardware

**Status: not implemented.** The code was designed so that hardware can be added without touching the mitigation, accounting or
analysis layers. Everything downstream only needs a count vector for each (circuit, shots). Below is what has to be done, using IBM Quantum
as the concrete example. Other providers (IonQ, Quantinuum, Rigetti, IQM, AWS Braket) follow the same pattern through their Qiskit providers or SDKs.

### 7.1 Access and budget
1. Create an IBM Quantum account and an API token. Store the token as an environment variable or with `QiskitRuntimeService.save_account`, and
   **never commit it**.
2. `uv add qiskit-ibm-runtime`.
3. **Budget before you run.** Shots translate into QPU time. One condition-repetition of REM+ZNE on GHZ-4 at N = 4096 uses about 4.3× the
   baseline's shots. Run `experiments/design.py:design_matrix` on your hardware profile and sum `total_shots` before you submit. Free and
   open plans have small monthly QPU-time allowances (check the current limits), so a hardware study should be a deliberately small subset:
   for example ghz_4, ghz_8, qaoa_n4_p1 × 2 budgets × 10 or more repetitions.

### 7.2 Code changes (with sketches)
**(a) A hardware backend with the same interface as `NoisySimulator`** (`execution/hardware.py`, new):
```python
# SKETCH — not part of the current codebase
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2, Batch

class HardwareSampler:
    def __init__(self, backend_name: str, batch: Batch):
        self.backend = QiskitRuntimeService().backend(backend_name)
        self.sampler = SamplerV2(mode=batch)
        self.sampler.options.dynamical_decoupling.enable = False   # no hidden mitigation
        self.sampler.options.twirling.enable_gates = False          # (enable only as an explicit, accounted method)
        self.sampler.options.twirling.enable_measure = False
    def sample_many(self, circuits, shots_list):                    # submit many circuits per job: queue time matters
        job = self.sampler.run([(c.measure_all(inplace=False), None, s) for c, s in zip(circuits, shots_list)])
        return job, [r.data.meas.get_counts() for r in job.result()]
```
Hardware needs **batched** submission (one job containing all circuits of a repetition, or of many repetitions) instead of the per-call
`sample()` used by the simulator. `ConditionRunner.run_rep` would first collect all (setting, scale, calibration) circuits, then submit them
together, then dispatch the counts.

**(b) Compile to the device ISA *before* folding.** Replace the basis-gate transpile in `execution/runner.py` with
```python
from qiskit.transpiler import generate_preset_pass_manager
pm = generate_preset_pass_manager(backend=backend, optimization_level=1, seed_transpiler=seed)
phys = pm.run(circ)   # routed onto the coupling map, native gates, fixed physical layout
```
Then fold the ISA circuit. IBM devices use native two-qubit gates such as `ecr` or `cz` instead of `cx`. Add their inverses to
`mitigation/zne.py::_inverse_ops` (both are self-inverse up to a global phase; verify with `Operator.equiv`). Keep the barriers, and make sure
**no further optimisation runs after folding**, because the server must not cancel G G† pairs. Use the same physical layout for calibration circuits.

**(c) Noise-scaling validation without a noise model.** On hardware the error mass is unknown. Compute λ_eff from the backend's
reported gate errors (`backend.target[gate][qubits].error`) and pass those as `fold_weights`. Then validate empirically: the measured
expectation value should decay monotonically with λ, which you can check from the stored `zne_points` table.

**(d) Ideal references.** Keep circuits small enough for exact classical simulation, as all circuits here are. The ideal values are
computed exactly as now. That is the main reason this suite works on hardware at all.

**(e) Provenance (mandatory).** For every job, record the backend name, processor revision, job IDs, submission and completion timestamps, queue
time, the calibration snapshot (T1, T2, gate and readout errors for the qubits used, saved as JSON next to the raw data), the physical layout and the transpiled
circuits (QPY). Add `sampling_mode="hardware"` and `backend` columns. **Store hardware runs in a separate `results/hardware/` tree,
never mixed with simulator data.**

### 7.3 Experimental-design issues that only appear on hardware
- **Drift:** calibration changes over hours. Interleave the methods and repetitions within the same batch, randomise the circuit order, and
  re-run readout calibration in every repetition (as the code already does) rather than once per day.
- **Pairing:** comparison A's common-random-numbers pairing (every method derived from the same raw counts) carries over directly,
  because REM, ZNE and REM+ZNE are post-processing of a shared set of executions. Comparison B needs separate executions per method.
- **Correlated readout and crosstalk:** real readout errors are correlated. Compare full and tensored calibration on 2–3 qubits, and consider M3.
- **Non-depolarizing noise:** coherent errors do not scale linearly under folding. Pauli twirling makes noise more stochastic, but it is
  itself a method with its own cost and must be accounted for as such.
- **Timing:** report QPU time (from job metadata) and queue time separately from local classical processing time.
- **Simulator-vs-hardware comparison:** run the same instances on (i) the phenomenological simulator, (ii) a fake-backend noise model
  of the same device, and (iii) the device. Present the three side by side and do not pool them.

### 7.4 A minimal hardware validation plan
1. Bell (2 qubits) and GHZ-4 on one device. Run baseline, REM, ZNE-linear (λ = 1, 3, 5) and REM+ZNE-linear at N = 4096, with 10 repetitions under comparison A
   (shared executions). That is roughly 10 × (S·K + M) circuits.
2. Validate: the ideal value is known, the λ decay is monotone, the calibration matrices are well conditioned, and the variance ratio is near 1.
3. Compare against a simulator run of the same configuration, using a fake-backend noise model.
4. Only then add comparison B and larger circuits.

---

## 8. Limitations
- **Simulation only.** The noise is phenomenological (depolarizing plus independent readout, optional T1/T2). It is favourable to tensored REM and to
  folding-based ZNE, because folding scales stochastic gate noise exactly.
- The circuits are small (at most 8 qubits) and compiled **without routing**, so depth and two-qubit counts are optimistic.
- 30 repetitions per condition, and a reduced factorial design. The `full` profile is configured but not executed.
- The extrapolation models are only linear and Richardson. The calibration fraction in comparison B is fixed at 20 %.
- The hypothesis rules were written by the author without external review. The H4 rule pooled observables with different bias scales.
- Wall-clock timings are machine-specific. Some references still need manual verification (marked [K] in `paper/references.bib`).

---

## Citation
See [`CITATION.cff`](CITATION.cff).
```bibtex
@software{gopalaswamy2026qembench,
  author  = {Gopalaswamy, Nagarjun},
  title   = {QEM-Bench: A Resource-Aware Benchmarking Framework for Quantum Error Mitigation},
  year    = {2026}, version = {0.1.0}, note = {Independent researcher}
}
```

## License
MIT. See [`LICENSE`](LICENSE).
