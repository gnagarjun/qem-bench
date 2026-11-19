"""QEM-Bench results viewer API: read-only access to saved, aggregated simulation results."""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
DATA = ROOT_DIR / os.environ["QEM_VIEWER_DATA_DIR"]

app = FastAPI(title="QEM-Bench Results Viewer")
api = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)


@lru_cache(maxsize=None)
def table(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


@lru_cache(maxsize=None)
def blob(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def records(df: pd.DataFrame) -> list[dict]:
    clean = df.replace([np.inf, -np.inf], [1e308, -1e308]).astype(object).where(df.notna(), None)
    return clean.to_dict(orient="records")


def filt(df: pd.DataFrame, **kw) -> pd.DataFrame:
    for k, v in kw.items():
        if v is None or v == "":
            continue
        col = df[k]
        df = df[col == (int(v) if col.dtype.kind in "iu" else float(v) if col.dtype.kind == "f" else v)]
    return df


@api.get("/")
def root():
    return {"service": "qem-bench-viewer", "data_available": DATA.exists()}


@api.get("/qem/overview")
def overview():
    s, p = blob("summary_standard.json"), blob("summary_pilot.json")
    keys = ["runs", "config_hashes", "schema_version", "n_raw_rows", "n_failed_rows", "n_conditions", "n_tests", "repetitions",
            "blocks", "hypotheses", "core_method_summary", "eta_categories_A", "max_readout_condition_number",
            "noise_scaling_max_abs_deviation", "noise_scaling_partial_folding", "all_folds_unitary_preserving"]
    return {"standard": {k: s.get(k) for k in keys},
            "pilot": {k: p.get(k) for k in ("runs", "n_raw_rows", "mode_equivalence", "timing_median_total_s_by_method")}}


@api.get("/qem/filters")
def filters():
    a = table("aggregated")
    return {c: sorted(a[c].dropna().unique().tolist()) for c in
            ("block", "instance", "noise", "shots_per_circuit", "comparison", "method", "observable", "family")}


@api.get("/qem/conditions")
def conditions(block: Optional[str] = "core", instance: Optional[str] = None, noise: Optional[str] = None,
               shots_per_circuit: Optional[int] = None, comparison: Optional[str] = None, method: Optional[str] = None,
               primary_only: bool = True, limit: int = Query(200, le=2000), offset: int = 0):
    a = filt(table("aggregated"), block=block, instance=instance, noise=noise, shots_per_circuit=shots_per_circuit,
             comparison=comparison, method=method)
    if primary_only:
        a = a[a.primary_observable]
    return {"total": len(a), "rows": records(a.iloc[offset:offset + limit])}


@api.get("/qem/series")
def series(instance: str, noise: str = "moderate", comparison: str = "A", block: str = "core", observable: Optional[str] = None):
    a = filt(table("aggregated"), block=block, instance=instance, noise=noise, comparison=comparison)
    a = a[a.observable == observable] if observable else a[a.primary_observable]
    if a.empty:
        raise HTTPException(404, "no data for this selection")
    cols = ["method", "shots_per_circuit", "rmse", "rmse_ci_lo", "rmse_ci_hi", "total_shots", "bias"]
    return {"observable": a.observable.iloc[0], "points": records(a[cols].sort_values(["method", "shots_per_circuit"]))}


@api.get("/qem/pareto")
def pareto(instance: str, noise: str = "moderate", block: str = "core"):
    p = filt(table("pareto"), block=block, instance=instance, noise=noise)
    p = p[p.primary_observable]
    if p.empty:
        raise HTTPException(404, "no data for this selection")
    return {"observable": p.observable.iloc[0], "points": records(p.sort_values("total_shots"))}


@api.get("/qem/tests")
def tests(block: Optional[str] = "core", instance: Optional[str] = None, noise: Optional[str] = None,
          shots_per_circuit: Optional[int] = None, comparison: Optional[str] = None, method: Optional[str] = None,
          reference: Optional[str] = "baseline", outcome: Optional[str] = None, primary_only: bool = True,
          limit: int = Query(200, le=2000), offset: int = 0):
    c = filt(table("comparisons"), block=block, instance=instance, noise=noise, shots_per_circuit=shots_per_circuit,
             comparison=comparison, method=method, reference=reference, outcome=outcome)
    if primary_only:
        c = c[c.primary_observable]
    counts = c.outcome.value_counts().to_dict()
    return {"total": len(c), "outcome_counts": counts, "rows": records(c.sort_values("q_bh").iloc[offset:offset + limit])}


@api.get("/qem/figures")
def figures():
    return blob("figures/figures.json")


@api.get("/qem/figures/{name}")
def figure(name: str):
    path = (DATA / "figures" / name).resolve()
    if path.parent != (DATA / "figures").resolve() or not path.exists() or path.suffix != ".png":
        raise HTTPException(404, "figure not found")
    return FileResponse(path, media_type="image/png")


@api.get("/qem/reproducibility")
def reproducibility():
    s = blob("summary_standard.json")
    timing = table("timing_study")
    return {"environment": s["environment"], "runs": s["runs"], "config_hashes": s["config_hashes"],
            "schema_version": s["schema_version"], "analysis": s["analysis"], "manifest": blob("manifest_standard.json"),
            "timing": records(timing[timing.shots_per_circuit == 4096]),
            "commands": ["uv sync --extra dev", "uv run pytest", "uv run python scripts/run_experiment.py --profile smoke",
                         "uv run bash scripts/reproduce_all.sh"]}


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
