# Installation

```bash
# recommended (exact lock)
uv sync --extra dev
# alternative
python3.11 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
```
Pinned core stack: qiskit 2.2.3 and qiskit-aer 0.17.2. This pair was chosen for API stability (Qiskit 2.x, with no deprecated `execute`/`Aer` provider
calls). Also numpy ≥ 2.0 (we use `np.bitwise_count`), scipy, pandas, pyarrow, matplotlib, seaborn, pydantic 2 and PyYAML.
Verify the install with `pytest tests/unit -q`.
