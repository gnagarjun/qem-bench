"""Owner-started simulation runs: launched as subprocesses, each saved separately with its own analysis."""

import asyncio
import gzip
import io
import json
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field, field_validator

from auth import require_owner
from util import filt, records

QEM = (Path(__file__).parent / os.environ["QEM_BENCH_DIR"]).resolve()
RUNS = (Path(__file__).parent / os.environ["QEM_RUNS_DIR"]).resolve()
STORED = ["analysis/aggregated.csv", "analysis/comparisons.csv", "analysis/summary.json", "spec.json", "run.log"]
METHODS = ["baseline", "readout", "zne_linear", "zne_richardson", "combined_linear", "combined_richardson"]
ZNE_PRESETS = {"1-3-5": [1.0, 3.0, 5.0], "1-2-3": [1.0, 2.0, 3.0], "1-3-5-7": [1.0, 3.0, 5.0, 7.0]}
MAX_UNITS = 20000
router = APIRouter(prefix="/api/runs")
db = None
_procs: dict[str, asyncio.subprocess.Process] = {}
_start_lock = asyncio.Lock()
_cache: dict[str, pd.DataFrame] = {}


def _yaml(name: str) -> dict:
    return yaml.safe_load((QEM / "configs" / name).read_text())


def options() -> dict:
    inst = _yaml("circuits.yaml")["instances"]
    levels = _yaml("noise_models.yaml")["levels"]
    return {"instances": [{"name": k, "family": v["family"], "n_qubits": v["params"].get("n_qubits", 2), **v["params"]}
                          for k, v in inst.items()],
            "noise": [{"name": k, **v} for k, v in levels.items() if k != "ideal"],
            "shots": _yaml("shot_budgets.yaml")["budgets"]["all"], "methods": METHODS,
            "zne_presets": ZNE_PRESETS, "max_units": MAX_UNITS}


class NoiseIn(BaseModel):
    base: str
    gate_multiplier: float = Field(1.0, ge=0, le=10)
    readout_multiplier: float = Field(1.0, ge=0, le=10)


class RunIn(BaseModel):
    name: str = Field("", max_length=80)
    instances: list[str] = Field(min_length=1)
    noise: list[NoiseIn] = Field(min_length=1, max_length=12)
    shots: list[int] = Field(min_length=1)
    methods: list[str] = Field(min_length=1)
    comparisons: list[Literal["A", "B"]] = Field(["A", "B"], min_length=1)
    repetitions: int = Field(10, ge=2, le=100)
    zne_scales: Literal["1-3-5", "1-2-3", "1-3-5-7"] = "1-3-5"
    folding: Literal["global", "local"] = "global"
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)

    @field_validator("methods")
    @classmethod
    def _m(cls, v):
        if set(v) - set(METHODS):
            raise ValueError("unknown method")
        return ["baseline"] + [m for m in METHODS if m in v and m != "baseline"]


def _spec(body: RunIn, opts: dict) -> dict:
    names = {i["name"] for i in opts["instances"]}
    levels = {n["name"] for n in opts["noise"]}
    if set(body.instances) - names:
        raise HTTPException(422, "Unknown circuit selected")
    if any(n.base not in levels for n in body.noise):
        raise HTTPException(422, "Unknown noise level selected")
    if set(body.shots) - set(opts["shots"]):
        raise HTTPException(422, "Unsupported shot budget")
    noise, seen = [], set()
    for n in body.noise:
        plain = n.gate_multiplier == 1.0 and n.readout_multiplier == 1.0
        ref = {"base": n.base} if plain else {"base": n.base, "gate_multiplier": n.gate_multiplier,
                                              "readout_multiplier": n.readout_multiplier,
                                              "label": f"{n.base}_g{n.gate_multiplier:g}_r{n.readout_multiplier:g}"}
        key = ref.get("label", n.base)
        if key not in seen:
            seen.add(key)
            noise.append(ref)
    units = len(set(body.instances)) * len(noise) * len(set(body.shots)) * body.repetitions
    if units > MAX_UNITS:
        raise HTTPException(422, f"Design too large ({units:,} condition-repetitions; limit {MAX_UNITS:,}). Reduce the selection.")
    return {"name": body.name.strip(), "seed": body.seed if body.seed is not None else int(uuid.uuid4().int % 2**31),
            "repetitions": body.repetitions, "instances": list(dict.fromkeys(body.instances)), "noise": noise,
            "shots": sorted(set(body.shots)), "methods": body.methods, "comparisons": sorted(set(body.comparisons)),
            "zne": {"scale_factors": ZNE_PRESETS[body.zne_scales], "folding": body.folding}, "units": units}


def _log(run_id: str) -> Path:
    return RUNS / run_id / "run.log"


def _progress(doc: dict) -> dict:
    total = len(doc["spec"]["instances"]) * len(doc["spec"]["noise"])
    text = _log(doc["run_id"]).read_text() if _log(doc["run_id"]).exists() else "\n".join(doc.get("log_tail") or [])
    done = text.count("running custom__")
    stage = "finished" if doc["status"] == "completed" else "analysing" if "analysing" in text else "simulating"
    return {"chunks_total": total, "chunks_started": done, "stage": stage, "log_tail": text.splitlines()[-12:]}


async def _watch(run_id: str, proc: asyncio.subprocess.Process, t0: datetime):
    code = await proc.wait()
    _procs.pop(run_id, None)
    doc = await db.custom_runs.find_one({"run_id": run_id}, {"_id": 0, "status": 1})
    if doc and doc["status"] == "cancelled":
        return
    end = datetime.now(timezone.utc)
    upd = {"status": "completed" if code == 0 else "failed", "finished_at": end.isoformat(),
           "wall_s": (end - t0).total_seconds()}
    lines = _log(run_id).read_text().splitlines()
    upd["log_tail"] = lines[-12:]
    if code == 0:
        s = json.loads((RUNS / run_id / "analysis" / "summary.json").read_text())
        upd["result"] = {k: s.get(k) for k in ("n_raw_rows", "n_failed_rows", "n_conditions", "n_tests")}
        upd["stored"] = await _store(run_id)
    else:
        upd["error"] = "\n".join(lines[-5:])
    await db.custom_runs.update_one({"run_id": run_id}, {"$set": upd})


def _fs() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name="run_files")


async def _store(run_id: str) -> bool:
    """Copy a run's analysis outputs into MongoDB so they survive container restarts and redeploys."""
    for rel in STORED:
        path = RUNS / run_id / rel
        if not path.exists():
            if rel.startswith("analysis/"):
                return False
            continue
        if not await db["run_files.files"].find_one({"filename": f"{run_id}/{rel}"}):
            await _fs().upload_from_stream(f"{run_id}/{rel}", gzip.compress(path.read_bytes()))
    return True


async def startup():
    await db.custom_runs.update_many({"status": "running"}, {"$set": {"status": "failed", "error": "Server restarted during the run"}})
    async for d in db.custom_runs.find({"status": "completed", "stored": {"$ne": True}}, {"run_id": 1}):
        if await _store(d["run_id"]):
            await db.custom_runs.update_one({"run_id": d["run_id"]}, {"$set": {"stored": True}})


@router.get("/options")
def get_options():
    return options()


@router.get("")
async def list_runs():
    docs = await db.custom_runs.find({"deleted": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [{**d, "progress": _progress(d)} if d["status"] == "running" else d for d in docs]


@router.post("", status_code=201)
async def start_run(body: RunIn, _: str = Depends(require_owner)):
    spec = _spec(body, options())
    async with _start_lock:
        if await db.custom_runs.find_one({"status": "running"}):
            raise HTTPException(409, "Another run is in progress. Wait for it to finish.")
        return await _launch(spec)


async def _launch(spec: dict) -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    out = RUNS / run_id
    out.mkdir(parents=True)
    (out / "spec.json").write_text(json.dumps(spec, indent=2))
    t0 = datetime.now(timezone.utc)
    doc = {"run_id": run_id, "name": spec["name"] or f"Run {run_id[:15]}", "spec": spec, "status": "running",
           "created_at": t0.isoformat(), "finished_at": None, "wall_s": None, "error": None, "result": None}
    await db.custom_runs.insert_one(dict(doc))
    log = open(_log(run_id), "w")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "scripts/run_custom.py", "--spec", str(out / "spec.json"), "--out", str(out),
        cwd=str(QEM), stdout=log, stderr=asyncio.subprocess.STDOUT, start_new_session=True,
        env={**os.environ, "PYTHONPATH": str(QEM / "src"), "MPLBACKEND": "Agg"})
    log.close()
    _procs[run_id] = proc
    asyncio.create_task(_watch(run_id, proc, t0))
    return doc


async def _get(run_id: str) -> dict:
    doc = await db.custom_runs.find_one({"run_id": run_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Run not found")
    return doc


@router.get("/{run_id}")
async def get_run(run_id: str):
    doc = await _get(run_id)
    return {**doc, "progress": _progress(doc)}


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, _: str = Depends(require_owner)):
    doc = await _get(run_id)
    if doc["status"] != "running":
        raise HTTPException(409, "Run is not in progress")
    await db.custom_runs.update_one({"run_id": run_id}, {"$set": {"status": "cancelled", "finished_at": datetime.now(timezone.utc).isoformat()}})
    proc = _procs.get(run_id)
    if proc and proc.returncode is None:
        os.killpg(proc.pid, signal.SIGTERM)
    return {"ok": True}


@router.delete("/{run_id}")
async def delete_run(run_id: str, _: str = Depends(require_owner)):
    doc = await _get(run_id)
    if doc["status"] == "running":
        raise HTTPException(409, "Cancel the run before deleting it")
    await db.custom_runs.update_one({"run_id": run_id}, {"$set": {"deleted": True}})
    return {"ok": True}


async def _table(doc: dict, name: str) -> pd.DataFrame:
    if doc["status"] != "completed":
        raise HTTPException(409, "Results are available once the run has completed")
    key = f"{doc['run_id']}/analysis/{name}.csv"
    if key not in _cache:
        if not doc.get("stored"):
            raise HTTPException(404, "Result files for this run are no longer available")
        stream = await _fs().open_download_stream_by_name(key)
        _cache[key] = pd.read_csv(io.BytesIO(gzip.decompress(await stream.read())))
        if len(_cache) > 40:
            _cache.pop(next(iter(_cache)))
    return _cache[key]


@router.get("/{run_id}/conditions")
async def run_conditions(run_id: str, instance: Optional[str] = None, noise: Optional[str] = None,
                         shots_per_circuit: Optional[int] = None, comparison: Optional[str] = None,
                         method: Optional[str] = None, limit: int = Query(500, le=2000)):
    a = await _table(await _get(run_id), "aggregated")
    a = filt(a[a.primary_observable], instance=instance, noise=noise, shots_per_circuit=shots_per_circuit,
             comparison=comparison, method=method)
    return {"total": len(a), "rows": records(a.head(limit))}


@router.get("/{run_id}/tests")
async def run_tests(run_id: str, comparison: Optional[str] = None, limit: int = Query(500, le=2000)):
    c = await _table(await _get(run_id), "comparisons")
    c = filt(c[c.primary_observable], comparison=comparison)
    return {"total": len(c), "outcome_counts": c.outcome.value_counts().to_dict(), "rows": records(c.sort_values("q_bh").head(limit))}
