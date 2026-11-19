# QEM-Bench — PRD / status (updated 2026-06)

## Original problem statement
Build QEM-Bench: a research-grade, reproducible framework for resource-aware evaluation of quantum error mitigation
(baseline, readout REM, ZNE linear/Richardson, REM+ZNE) on Bell/GHZ/QAOA circuits with Qiskit Aer noise, multiple shot
budgets, equal-primary-shot (A) and equal-total-budget (B) comparisons, rigorous statistics, Pareto/efficiency analysis,
12 publication figures, literature review, LaTeX manuscript, GitHub-quality repo. (Full prompt: user's MASTER BUILD PROMPT.)

## User choices
Repository + web results viewer; pilot + reduced standard run executed; simulator only (no IBM); MIT; author Nagarjun Gopalaswamy, Independent researcher.

## Architecture
- /app/qem-bench: Python package (src/qem_bench: config, seeds, circuits, noise, mitigation, execution, metrics, experiments, analysis, visualization), configs/*.yaml, scripts/, tests/ (76 tests), docs/, paper/, notebooks/, results/, data/reference/demo. Own venv .venv (qiskit 2.2.3, aer 0.17.2), uv.lock.
- /app/backend/server.py: read-only FastAPI viewer API (/api/qem/*) over /app/backend/viewer_data (exported by scripts/export_viewer_data.py). Env QEM_VIEWER_DATA_DIR.
- /app/frontend: React dashboard (6 tabs) in src/components/qem/.

## Implemented (2026-06)
- All four configurations, both folding modes, error-weighted partial folding + effective-scale extrapolation (regression-tested bug fix).
- Pilot (aer vs exact equivalence: 0/288 differ after FDR; timing study) and standard run (8,532 conditions, 255,960 estimates, 30 reps), validated.
- Analysis: bootstrap CIs, Wilcoxon+rank-biserial, BH/Holm, eta/mu/WNMSE, Pareto, H1–H5 verdicts (H4 NOT SUPPORTED, H2 noise component not observed).
- 12 figures (PNG+PDF), LaTeX tables, main.tex, references.bib (verification flags), supplement, literature review, research gap, hypotheses, methodology.
- CI workflows, Makefile, pre-commit, CITATION.cff, LICENSE, CONTRIBUTING, CoC, issue templates.
- Viewer tested (iteration_1): backend 100%, frontend fixes applied (block 'All', mobile repro overflow, header nav).

- 2026-06: Run Simulations tab: owner-password login (JWT, lockout), design picker (circuits, noise incl. scaled, shots, methods, A/B, reps, ZNE scales/folding, seed), background runs via scripts/run_custom.py, separate saved runs (results/custom_runs, Mongo custom_runs), live progress, cancel/soft-delete, per-run conditions + statistical tests. Tested (iteration_2).
- 2026-06: AWS Lightsail-ready: root Dockerfile (React build + FastAPI serving SPA + Qiskit), backend/requirements.prod.txt, deploy/lightsail/{deploy.sh,deployment.template.json,lightsail.env.example}, DEPLOY_AWS_LIGHTSAIL.md (Atlas, IAM, deploy, ops, custom domain). Custom-run outputs now persisted in MongoDB GridFS (bucket run_files); QEM_RUNS_DIR env = scratch dir; /api/health. Verified prod layout locally in clean venv (no docker in pod).
## Backlog
- DONE 2026-06: manual GitHub Actions deploy (.github/workflows/deploy-lightsail.yml): pytest gate → docker build → smoke test (deploy/ci/smoke_test.sh) → OIDC role (deploy/lightsail/setup-github-oidc.sh) → deploy.sh release → live check
- P1 Compare two custom runs side by side; optional figure generation per run
- P0 before submission: manually verify [K] references; systematic literature search; external review of hypothesis rules.
- P1: run `full` profile (100 reps); exponential extrapolation; correlated readout + M3; coupling-map routing.
- P2: PEC/CDR modules; hardware backend; Zenodo deposit of raw data.

# QEM-Bench PRD
Reproducible research framework (Python/Qiskit) for resource-aware evaluation of quantum error mitigation, plus a React/FastAPI results viewer. Author: Nagarjun Gopalaswamy, MIT license.
## Done
- Framework, pilot + standard Aer runs, 12 figures, LaTeX paper, React viewer, README with execution record.
- 2026-06: Removed Emergent branding from the viewer (badge script, analytics, title/description) and the README; added a QEM-Bench favicon.
- 2026-06: Run Simulations tab: owner-password login (JWT, lockout), design picker (circuits, noise incl. scaled, shots, methods, A/B, reps, ZNE scales/folding, seed), background runs via scripts/run_custom.py, separate saved runs (results/custom_runs, Mongo custom_runs), live progress, cancel/soft-delete, per-run conditions + statistical tests. Tested (iteration_2).
## Backlog
- P1 Compare two custom runs side by side; optional figure generation per run
- P1 IBM hardware validation; P2 PEC/CDR/symmetry verification; P2 larger scale runs (>8 qubits, 100 reps).
