import numpy as np

from qem_bench.config import load_config
from qem_bench.experiments.runner import load_run, run_experiment

DETERMINISTIC = ["estimate", "stderr_est", "total_shots", "calibration_shots", "primary_shots"]


def test_identical_seeds_identical_results(tmp_path):
    cfg = load_config("smoke", "configs")
    r1 = load_run(run_experiment(cfg, tmp_path / "a"))
    r2 = load_run(run_experiment(cfg, tmp_path / "b"))
    keys = ["block", "instance", "noise", "shots_per_circuit", "repetition", "comparison", "method", "observable"]
    r1, r2 = r1.sort_values(keys).reset_index(drop=True), r2.sort_values(keys).reset_index(drop=True)
    for c in DETERMINISTIC:
        np.testing.assert_array_equal(r1[c].to_numpy(), r2[c].to_numpy())


def test_repetitions_use_distinct_streams(tmp_path):
    cfg = load_config("smoke", "configs")
    df = load_run(run_experiment(cfg, tmp_path))
    b = df[(df.method == "baseline") & (df.comparison == "A")]
    per = b.groupby(["instance", "shots_per_circuit", "observable"]).estimate.nunique()
    assert (per > 1).all()
    # comparison-B readout draws are independent of comparison-A draws
    a = df[(df.method == "readout") & (df.comparison == "A")].estimate.to_numpy()
    bb = df[(df.method == "readout") & (df.comparison == "B")].estimate.to_numpy()
    assert not np.allclose(a, bb)
