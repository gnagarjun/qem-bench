# Contributing to QEM-Bench

Thank you for your interest. QEM-Bench puts **scientific correctness first, then reproducibility, then everything else**.

## Ground rules
- Never commit fabricated, hand-edited or cherry-picked results. Figures must be generated from saved data by `scripts/`.
- Every bug fix needs a regression test. Every new mitigation method needs (i) synthetic-correctness tests and
  (ii) explicit resource accounting in `execution/resource_tracker.py`, checked by `experiments/validation.py`.
- Never discard failed runs. Record them with `status="failed"` and a `failure_reason`.
- Keep simulated and hardware results strictly separate. Label any hardware data with backend, date and calibration snapshot.

## Adding a mitigation method (PEC, CDR, symmetry verification, ...)
1. Add a `MethodSpec` to `mitigation/base.py` and the estimator to a new module in `mitigation/`.
2. Extend `plan_shots` for comparisons A and B.
3. Add tests under `tests/scientific_validation/`.
4. Document the method and its accounting rule in `docs/methodology.md`.

## Workflow
```bash
uv sync --extra dev && pre-commit install
make lint test
```
Use meaningful commit messages, e.g. `zne: weight partial folds by gate error (fixes λ_eff mis-scaling)`.
