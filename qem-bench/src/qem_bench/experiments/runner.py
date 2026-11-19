"""Experiment orchestration: resumable, never-overwriting, fully logged runs."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from qem_bench.circuits import build_instance
from qem_bench.config import SCHEMA_VERSION, ExperimentConfig
from qem_bench.execution.runner import ConditionRunner, compile_instance, folding_weights
from qem_bench.execution.simulator import NoisySimulator
from qem_bench.experiments.environment import environment_info
from qem_bench.logging import get_logger
from qem_bench.noise.validation import noise_scaling_report, state_fidelity_under_noise

log = get_logger(__name__)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.rename(path)


def new_run_dir(cfg: ExperimentConfig, out_root: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / f"{cfg.profile}_{stamp}_{cfg.config_hash()}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing run directory {run_dir}")
    return run_dir


def run_experiment(cfg: ExperimentConfig, out_root: str | Path, resume: str | Path | None = None) -> Path:
    run_dir = Path(resume) if resume else new_run_dir(cfg, Path(out_root))
    if resume:
        prev = json.loads((run_dir / "config_resolved.json").read_text())
        if prev["config_hash"] != cfg.config_hash():
            raise ValueError("cannot resume: configuration hash differs from the original run")
    for sub in ("raw", "zne_points", "circuits"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    (run_dir / "config_resolved.json").write_text(json.dumps(
        {"config_hash": cfg.config_hash(), "schema_version": SCHEMA_VERSION, "config": cfg.model_dump(mode="json")},
        indent=2))
    (run_dir / "environment.json").write_text(json.dumps(environment_info(), indent=2))
    run_id = run_dir.name
    t_start = time.perf_counter()
    for block in cfg.blocks:
        reps = block.repetitions or cfg.repetitions
        mode = block.sampling_mode or cfg.sampling_mode
        for inst_name in block.instances:
            t0 = time.perf_counter()
            bench = build_instance(cfg.instances[inst_name])
            t_construct = time.perf_counter() - t0
            for nref in block.noise:
                spec = cfg.resolve_noise(nref)
                ci = compile_instance(bench, block.zne.scale_factors, block.zne.folding, cfg.optimization_level,
                                      cfg.seed, folding_weights(spec))
                chunk = f"{block.name}__{inst_name}__{spec.name}"
                raw_path = run_dir / "raw" / f"{chunk}.parquet"
                if raw_path.exists():
                    log.info("resume: skipping completed chunk %s", chunk)
                    continue
                log.info("running %s (%d shots settings x %d reps, mode=%s)", chunk, len(block.shots), reps, mode)
                sim = NoisySimulator(spec, mode)
                runner = ConditionRunner(ci, spec, cfg, block, sim)
                labels = (block.name, inst_name, spec.name)
                rows, zrows = [], []
                for shots in block.shots:
                    for rep in range(reps):
                        r, z = runner.run_rep(shots, rep, labels)
                        for d in r:
                            d.update(shots_per_circuit=shots, repetition=rep)
                        for d in z:
                            d.update(shots_per_circuit=shots, repetition=rep)
                        rows += r
                        zrows += z
                meta = {"run_id": run_id, "schema_version": SCHEMA_VERSION, "config_hash": cfg.config_hash(),
                        "timestamp": datetime.now(UTC).isoformat(), "root_seed": cfg.seed,
                        "block": block.name, "instance": inst_name, "family": bench.family,
                        "circuit_params": json.dumps(bench.params), "n_qubits": bench.n_qubits,
                        "noise": spec.name, "noise_base": nref.base, "p1": spec.p1, "p2": spec.p2,
                        "readout_p01": spec.readout_p01, "readout_p10": spec.readout_p10, "thermal": spec.thermal,
                        "gate_multiplier": nref.gate_multiplier, "readout_multiplier": nref.readout_multiplier,
                        "sampling_mode": mode, "folding": block.zne.folding,
                        "scale_factors": json.dumps(list(block.zne.scale_factors)),
                        "zne_allocation_B": block.zne.allocation_equal_budget,
                        "calibration_mode": runner.cal_mode, "n_settings": len(ci.settings)}
                df = pd.DataFrame(rows).assign(**meta)
                _atomic_parquet(pd.DataFrame(zrows).assign(**meta), run_dir / "zne_points" / f"{chunk}.parquet")
                cm = pd.DataFrame(ci.complexity)
                scal = pd.DataFrame(noise_scaling_report(ci, spec, check_unitary=bench.n_qubits <= 6))
                cm = cm.merge(scal, on=["setting", "scale_nominal"], how="left")
                cm = cm.assign(**meta, ideal_values=json.dumps(ci.ideal), reference=json.dumps(bench.reference),
                               t_construct_s=t_construct, t_transpile_s=ci.transpile_time_s,
                               t_distribution_s=sum(sim.distribution_time.values()),
                               state_fidelity=state_fidelity_under_noise(ci, spec, cfg.optimization_level))
                _atomic_parquet(cm, run_dir / "circuits" / f"{chunk}.parquet")
                _atomic_parquet(df, raw_path)  # written last: marks the chunk complete
    write_manifest(run_dir, cfg, time.perf_counter() - t_start)
    return run_dir


def write_manifest(run_dir: Path, cfg: ExperimentConfig, wall_s: float) -> None:
    files = []
    for p in sorted(run_dir.rglob("*.parquet")):
        files.append({"path": str(p.relative_to(run_dir)), "sha256": _sha(p), "rows": len(pd.read_parquet(p))})
    manifest = {"run_id": run_dir.name, "profile": cfg.profile, "config_hash": cfg.config_hash(),
                "schema_version": SCHEMA_VERSION, "completed_utc": datetime.now(UTC).isoformat(),
                "wall_clock_s_this_invocation": wall_s, "files": files}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def load_run(run_dir: str | Path, table: str = "raw") -> pd.DataFrame:
    parts = sorted(Path(run_dir, table).glob("*.parquet"))
    if not parts:
        raise FileNotFoundError(f"no {table} data in {run_dir}")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
