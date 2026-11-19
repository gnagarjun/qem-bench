# DEMONSTRATION DATASET (subset of real simulated data)

This directory holds 6 chunks copied **unchanged** from the standard run `standard_20261119T034606Z_87821ca68ff11fc6` (simulated with Qiskit Aer, not hardware).
It exists so that users can try the analysis pipeline in seconds:

    python scripts/analyze_results.py --run data/reference/demo/run --out /tmp/demo_agg

Because the subset is incomplete, hypothesis verdicts computed from it are **not** the study's results.
