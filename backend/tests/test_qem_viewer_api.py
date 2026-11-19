# QEM-Bench read-only results viewer API regression tests
import json
import os
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/qem"
DATA = Path("/app/backend/viewer_data")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def summary():
    return json.loads((DATA / "summary_standard.json").read_text())


# Overview
def test_overview_values(s, summary):
    r = s.get(f"{API}/overview")
    assert r.status_code == 200
    st = r.json()["standard"]
    assert st["n_raw_rows"] == 255960 == summary["n_raw_rows"]
    assert st["n_conditions"] == 8532
    v = {k: st["hypotheses"][k]["verdict"] for k in ["H1", "H2", "H3", "H4", "H5"]}
    assert v == {"H1": "SUPPORTED", "H2": "SUPPORTED", "H3": "SUPPORTED", "H4": "NOT SUPPORTED", "H5": "SUPPORTED"}
    assert "pilot" in r.json() and r.json()["pilot"]["mode_equivalence"] is not None


# Filters
def test_filters(s):
    r = s.get(f"{API}/filters")
    assert r.status_code == 200
    d = r.json()
    for k in ("block", "instance", "noise", "shots_per_circuit", "comparison", "method"):
        assert len(d[k]) > 0
    assert "ghz_4" in d["instance"] and 256 in d["shots_per_circuit"]


# Conditions
def test_conditions_default_and_filters(s):
    r = s.get(f"{API}/conditions")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] > 0 and all(x["block"] == "core" and x["primary_observable"] for x in d["rows"])
    r2 = s.get(f"{API}/conditions", params=dict(instance="ghz_4", noise="moderate", shots_per_circuit=4096,
                                               comparison="A", method="readout"))
    d2 = r2.json()
    assert d2["total"] >= 1
    for x in d2["rows"]:
        assert (x["instance"], x["noise"], x["shots_per_circuit"], x["comparison"], x["method"]) == \
               ("ghz_4", "moderate", 4096, "A", "readout")


def test_conditions_primary_only_false(s):
    a = s.get(f"{API}/conditions", params={"primary_only": "true"}).json()["total"]
    b = s.get(f"{API}/conditions", params={"primary_only": "false"}).json()["total"]
    assert b >= a


def test_conditions_limit_cap(s):
    assert s.get(f"{API}/conditions", params={"limit": 5000}).status_code == 422


def test_conditions_bad_shots(s):
    assert s.get(f"{API}/conditions", params={"shots_per_circuit": "abc"}).status_code == 422


def test_conditions_unknown_instance_empty(s):
    r = s.get(f"{API}/conditions", params={"instance": "nope"})
    assert r.status_code == 200 and r.json()["total"] == 0


# Series
def test_series(s):
    r = s.get(f"{API}/series", params=dict(instance="ghz_4", noise="moderate", comparison="A"))
    assert r.status_code == 200
    d = r.json()
    assert d["observable"] and len(d["points"]) > 0
    assert {"method", "shots_per_circuit", "rmse"} <= set(d["points"][0])


def test_series_unknown_instance_404(s):
    assert s.get(f"{API}/series", params={"instance": "nope"}).status_code == 404


# Pareto
def test_pareto(s):
    r = s.get(f"{API}/pareto", params=dict(instance="ghz_4", noise="moderate"))
    assert r.status_code == 200
    pts = r.json()["points"]
    assert len(pts) > 0 and any(p["pareto_optimal"] for p in pts)
    ts = [p["total_shots"] for p in pts]
    assert ts == sorted(ts)


def test_pareto_unknown_404(s):
    assert s.get(f"{API}/pareto", params={"instance": "nope"}).status_code == 404


# Tests
def test_tests_endpoint(s):
    r = s.get(f"{API}/tests", params=dict(comparison="B", shots_per_circuit=256))
    assert r.status_code == 200
    d = r.json()
    assert d["total"] > 0 and sum(d["outcome_counts"].values()) == d["total"]
    assert all(x["comparison"] == "B" and x["shots_per_circuit"] == 256 for x in d["rows"])


def test_tests_outcome_filter(s):
    d = s.get(f"{API}/tests", params=dict(comparison="B", shots_per_circuit=256, outcome="better_practical")).json()
    assert all(x["outcome"] == "better_practical" for x in d["rows"])


# Figures
def test_figures_list_and_images(s):
    r = s.get(f"{API}/figures")
    assert r.status_code == 200
    figs = r.json()
    assert len(figs) == 12
    for f in figs:
        img = s.get(f"{API}/figures/{f['png']}")
        assert img.status_code == 200 and img.headers["content-type"] == "image/png"
        assert img.content[:4] == b"\x89PNG"


@pytest.mark.parametrize("name", ["..%2Fsummary_standard.json", "..%2F..%2Fserver.py", "%2e%2e%2f%2e%2e%2f.env",
                                  "figures.json", "nonexistent.png", "..%2F..%2F..%2Fetc%2Fpasswd"])
def test_figure_traversal_404(s, name):
    r = s.get(f"{API}/figures/{name}")
    assert r.status_code == 404, f"{name} -> {r.status_code}"


# Reproducibility
def test_reproducibility(s):
    r = s.get(f"{API}/reproducibility")
    assert r.status_code == 200
    d = r.json()
    assert d["config_hashes"] == ["87821ca68ff11fc6"]
    assert d["environment"]["python"] and len(d["commands"]) == 4
    assert len(d["timing"]) > 0 and all(t["shots_per_circuit"] == 4096 for t in d["timing"])
