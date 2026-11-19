import json

import pandas as pd
import pytest
import yaml

from qem_bench.config import load_config
from qem_bench.experiments.runner import load_run, run_experiment
from qem_bench.experiments.validation import validate_run


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    cfg = load_config("smoke", "configs")
    out = tmp_path_factory.mktemp("runs")
    return cfg, run_experiment(cfg, out)


def test_smoke_pipeline_valid(smoke_run):
    cfg, run = smoke_run
    rep = validate_run(run, cfg)
    assert rep["passed"], rep
    man = json.loads((run / "manifest.json").read_text())
    assert man["config_hash"] == cfg.config_hash() and man["files"]
    for f in ("config_resolved.json", "environment.json"):
        assert (run / f).exists()


def test_resource_accounting_in_data(smoke_run):
    _, run = smoke_run
    df = load_run(run)
    a = df[df.comparison == "A"]
    ro = a[a.method == "readout"]
    assert (ro.calibration_shots > 0).all()
    z = a[a.method == "zne_linear"]
    assert (z.primary_shots == z.shots_per_circuit * z.n_settings * 3).all()
    assert (df.t_postprocess_s >= 0).all() and "t_calibration_s" in df


def test_resume_skips_and_no_overwrite(smoke_run, tmp_path):
    cfg, run = smoke_run
    before = {p.name: p.stat().st_mtime for p in (run / "raw").glob("*.parquet")}
    run_experiment(cfg, run.parent, resume=run)
    after = {p.name: p.stat().st_mtime for p in (run / "raw").glob("*.parquet")}
    assert before == after


def test_resume_rejects_changed_config(smoke_run, config_dir):
    _, run = smoke_run
    p = config_dir / "experiments.yaml"
    d = yaml.safe_load(p.read_text())
    d["profiles"]["smoke"]["repetitions"] = 6
    p.write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError):
        run_experiment(load_config("smoke", config_dir), run.parent, resume=run)


def test_failed_calibration_recorded_not_dropped(config_dir, tmp_path):
    p = config_dir / "default.yaml"
    d = yaml.safe_load(p.read_text())
    d["readout"]["condition_failure"] = 1.0000001  # force every calibration to be rejected
    p.write_text(yaml.safe_dump(d))
    e = config_dir / "experiments.yaml"
    x = yaml.safe_load(e.read_text())
    x["profiles"]["smoke"]["blocks"][0]["instances"] = ["bell_cx"]
    x["profiles"]["smoke"]["blocks"][0]["shots"] = [256]
    e.write_text(yaml.safe_dump(x))
    cfg = load_config("smoke", config_dir)
    run = run_experiment(cfg, tmp_path)
    df = load_run(run)
    failed = df[df.method.isin(["readout", "combined_linear", "combined_richardson"])]
    assert (failed.status == "failed").all() and (failed.failure_reason.str.contains("ill-conditioned")).all()
    assert (df[df.method == "baseline"].status == "ok").all()
    rep = validate_run(run, cfg)
    assert rep["complete"] and rep["failed_have_reason"]


def test_low_shot_and_high_noise_edge(config_dir, tmp_path):
    n = config_dir / "noise_models.yaml"
    d = yaml.safe_load(n.read_text())
    d["levels"]["moderate"] = {"p1": 0.05, "p2": 0.3, "readout_p01": 0.2, "readout_p10": 0.25}
    n.write_text(yaml.safe_dump(d))
    e = config_dir / "experiments.yaml"
    x = yaml.safe_load(e.read_text())
    x["profiles"]["smoke"]["blocks"][0]["shots"] = [16]
    e.write_text(yaml.safe_dump(x))
    cfg = load_config("smoke", config_dir)
    run = run_experiment(cfg, tmp_path)
    assert validate_run(run, cfg)["complete"]
    assert isinstance(load_run(run), pd.DataFrame)
