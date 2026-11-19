"""Post-run dataset validation: completeness, accounting consistency and value sanity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qem_bench.config import ExperimentConfig
from qem_bench.experiments.runner import load_run


def validate_run(run_dir: str | Path, cfg: ExperimentConfig) -> dict[str, Any]:
    run_dir = Path(run_dir)
    df = load_run(run_dir)
    checks: dict[str, Any] = {}
    # completeness
    expected = 0
    for b in cfg.blocks:
        reps = b.repetitions or cfg.repetitions
        for inst in b.instances:
            n_obs = len(df.loc[(df.block == b.name) & (df.instance == inst), "observable"].unique())
            expected += len(b.noise) * len(b.shots) * reps * len(b.methods) * len(b.comparisons) * n_obs
    checks["rows_expected"], checks["rows_found"] = expected, len(df)
    checks["complete"] = expected == len(df)
    # failures are retained, never dropped
    checks["n_failed"] = int((df.status != "ok").sum())
    checks["failed_have_reason"] = bool((df.loc[df.status != "ok", "failure_reason"] != "").all())
    ok = df[df.status == "ok"]
    checks["no_nan_in_ok_estimates"] = bool(np.isfinite(ok.estimate).all())
    # accounting
    checks["total_equals_primary_plus_calibration"] = bool(
        (df.total_shots == df.primary_shots + df.calibration_shots).all())
    ro = df[df.method.str.contains("readout|combined")]
    checks["readout_methods_charge_calibration"] = bool((ro.calibration_shots > 0).all())
    nonro = df[~df.method.str.contains("readout|combined")]
    checks["non_readout_methods_no_calibration"] = bool((nonro.calibration_shots == 0).all())
    a = df[df.comparison == "A"]
    zA = a[a.method.str.startswith(("zne", "combined"))]
    checks["A_zne_primary_scales_with_n_scales"] = bool(
        (zA.primary_shots == zA.shots_per_circuit * zA.n_settings * zA.n_scales).all())
    b = df[df.comparison == "B"]
    budget = b.shots_per_circuit * b.n_settings
    checks["B_never_exceeds_baseline_budget"] = bool((b.total_shots <= budget).all())
    checks["B_min_budget_utilisation"] = float((b.total_shots / budget).min()) if len(b) else None
    base = a[a.method == "baseline"]
    checks["A_baseline_total_is_N_times_settings"] = bool(
        (base.total_shots == base.shots_per_circuit * base.n_settings).all())
    # value sanity
    checks["ideal_values_bounded"] = bool((df.ideal.abs() <= 1 + 1e-9).all())
    dup = df.groupby(["block", "instance", "noise", "shots_per_circuit", "comparison", "method", "observable",
                      "repetition"]).size()
    checks["no_duplicate_units"] = bool((dup == 1).all())
    # independent repetitions: baseline estimates should not be identical across all reps
    var = base.groupby(["block", "instance", "noise", "shots_per_circuit", "observable"]).estimate.std()
    checks["repetitions_not_identical_fraction"] = float((var > 0).mean())
    checks["passed"] = all(v for k, v in checks.items() if isinstance(v, bool))
    (run_dir / "validation_report.json").write_text(json.dumps(checks, indent=2, default=str))
    return checks


def load_validation(run_dir: str | Path) -> dict[str, Any]:
    return json.loads(Path(run_dir, "validation_report.json").read_text())


__all__ = ["validate_run", "load_validation", "pd"]
