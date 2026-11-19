# Owner auth + custom simulation runs API regression tests (sequential, one class so xdist keeps order)
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PW = "qem-VUuXkDCWds9b"
CREATED = []


def xff():
    return {"X-Forwarded-For": f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"}


def small(**kw):
    body = {"name": "TEST_run", "instances": ["bell_cx"], "noise": [{"base": "moderate"}], "shots": [1024],
            "methods": ["readout", "zne_linear"], "comparisons": ["A", "B"], "repetitions": 3, "seed": 7}
    body.update(kw)
    return body


def wait_done(s, rid, timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        d = s.get(f"{BASE_URL}/api/runs/{rid}").json()
        if d["status"] != "running":
            return d
        time.sleep(1.5)
    raise AssertionError("run did not finish")


def wait_idle(s, timeout=150):
    t = time.time()
    while time.time() - t < timeout:
        if not any(r["status"] == "running" for r in s.get(f"{BASE_URL}/api/runs").json()):
            return
        time.sleep(2)
    pytest.skip("another run is in progress")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def H(s):
    r = s.post(f"{BASE_URL}/api/auth/login", json={"password": PW}, headers=xff())
    if r.status_code != 200:
        pytest.skip("login failed")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module", autouse=True)
def cleanup(s):
    yield
    r = s.post(f"{BASE_URL}/api/auth/login", json={"password": PW}, headers=xff())
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    for rid in CREATED:
        if s.get(f"{BASE_URL}/api/runs/{rid}").json().get("status") == "running":
            s.post(f"{BASE_URL}/api/runs/{rid}/cancel", headers=h)
        s.delete(f"{BASE_URL}/api/runs/{rid}", headers=h)


class TestCustomRuns:
    # Auth
    def test_login_wrong(self, s):
        r = s.post(f"{BASE_URL}/api/auth/login", json={"password": "nope"}, headers=xff())
        assert r.status_code == 401 and r.json()["detail"] == "Wrong password"

    def test_login_ok_and_me(self, s, H):
        r = s.get(f"{BASE_URL}/api/auth/me", headers=H)
        assert r.status_code == 200 and r.json()["role"] == "owner"
        assert s.get(f"{BASE_URL}/api/auth/me").status_code == 401
        assert s.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401

    # Options
    def test_options(self, s):
        o = s.get(f"{BASE_URL}/api/runs/options").json()
        for k in ("instances", "noise", "shots", "methods", "zne_presets", "max_units"):
            assert k in o
        assert "ideal" not in [n["name"] for n in o["noise"]]
        assert o["max_units"] == 20000 and "baseline" in o["methods"] and 1024 in o["shots"]

    # Auth required on mutating endpoints
    def test_start_requires_token(self, s):
        assert s.post(f"{BASE_URL}/api/runs", json=small()).status_code == 401
        assert s.post(f"{BASE_URL}/api/runs/x/cancel").status_code == 401
        assert s.delete(f"{BASE_URL}/api/runs/x").status_code == 401

    # Validation
    def test_validation(self, s, H):
        wait_idle(s)
        cases = [small(instances=["nope"]), small(noise=[{"base": "ideal"}]), small(shots=[333]),
                 small(repetitions=1), small(repetitions=101), small(methods=["bogus"]), small(comparisons=["C"]),
                 small(instances=[i["name"] for i in s.get(f"{BASE_URL}/api/runs/options").json()["instances"]],
                       noise=[{"base": "low"}, {"base": "high"}, {"base": "moderate"}], shots=[256, 512, 1024, 2048, 4096, 8192, 16384],
                       repetitions=100)]
        for c in cases:
            r = s.post(f"{BASE_URL}/api/runs", json=c, headers=H)
            assert r.status_code == 422, (c, r.status_code, r.text)
        assert "Design too large" in r.json()["detail"]

    def test_unknown_id(self, s):
        assert s.get(f"{BASE_URL}/api/runs/does-not-exist").status_code == 404
        assert s.get(f"{BASE_URL}/api/runs/does-not-exist/conditions").status_code == 404
        assert s.get(f"{BASE_URL}/api/runs/does-not-exist/tests").status_code == 404

    # Full run lifecycle with scaled noise
    def test_run_lifecycle(self, s, H):
        wait_idle(s)
        body = small(noise=[{"base": "moderate"}, {"base": "high", "gate_multiplier": 2, "readout_multiplier": 1}],
                     instances=["bell_cx", "ghz_3"], shots=[512, 1024])
        r = s.post(f"{BASE_URL}/api/runs", json=body, headers=H)
        assert r.status_code == 201, r.text
        d = r.json()
        rid = d["run_id"]
        CREATED.append(rid)
        assert d["status"] == "running" and "_id" not in d
        assert d["spec"]["methods"][0] == "baseline"
        assert any(n.get("label") == "high_g2_r1" for n in d["spec"]["noise"])
        # second start while running -> 409, delete running -> 409
        assert s.post(f"{BASE_URL}/api/runs", json=small(), headers=H).status_code == 409
        assert s.delete(f"{BASE_URL}/api/runs/{rid}", headers=H).status_code == 409
        assert s.get(f"{BASE_URL}/api/runs/{rid}/conditions").status_code in (409, 200)
        done = wait_done(s, rid)
        assert done["status"] == "completed", done.get("error")
        res = done["result"]
        assert res["n_raw_rows"] > 0 and res["n_conditions"] > 0 and res["n_tests"] > 0 and res["n_failed_rows"] == 0
        assert any(x["run_id"] == rid for x in s.get(f"{BASE_URL}/api/runs").json())
        # conditions + filters
        c = s.get(f"{BASE_URL}/api/runs/{rid}/conditions").json()
        assert c["total"] > 0 and {r["noise"] for r in c["rows"]} == {"moderate", "high_g2_r1"}
        assert {r["method"] for r in c["rows"]} == {"baseline", "readout", "zne_linear"}
        f = s.get(f"{BASE_URL}/api/runs/{rid}/conditions", params={"comparison": "A", "shots_per_circuit": 1024,
                                                                   "instance": "ghz_3", "noise": "high_g2_r1", "method": "readout"}).json()
        assert f["total"] == 1 and f["rows"][0]["instance"] == "ghz_3" and f["rows"][0]["noise"] == "high_g2_r1"
        t = s.get(f"{BASE_URL}/api/runs/{rid}/tests", params={"comparison": "B"}).json()
        assert t["total"] > 0 and sum(t["outcome_counts"].values()) == t["total"]
        assert all(r["comparison"] == "B" for r in t["rows"])
        # cancel completed -> 409
        assert s.post(f"{BASE_URL}/api/runs/{rid}/cancel", headers=H).status_code == 409

    def test_cancel_and_delete(self, s, H):
        wait_idle(s)
        r = s.post(f"{BASE_URL}/api/runs", json=small(instances=["ghz_6", "qaoa_n6_p2"], noise=[{"base": "moderate_thermal"}],
                                                          methods=["readout", "zne_richardson", "combined_richardson"],
                                                          shots=[4096, 8192, 16384], repetitions=30), headers=H)
        assert r.status_code == 201, r.text
        rid = r.json()["run_id"]
        CREATED.append(rid)
        time.sleep(0.5)
        assert s.get(f"{BASE_URL}/api/runs/{rid}/conditions").status_code == 409
        c = s.post(f"{BASE_URL}/api/runs/{rid}/cancel", headers=H)
        assert c.status_code == 200
        time.sleep(2)
        d = s.get(f"{BASE_URL}/api/runs/{rid}").json()
        assert d["status"] == "cancelled"
        assert s.get(f"{BASE_URL}/api/runs/{rid}/tests").status_code == 409
        time.sleep(3)
        assert s.get(f"{BASE_URL}/api/runs/{rid}").json()["status"] == "cancelled"
        assert s.delete(f"{BASE_URL}/api/runs/{rid}", headers=H).status_code == 200
        assert rid not in [x["run_id"] for x in s.get(f"{BASE_URL}/api/runs").json()]
        assert s.get(f"{BASE_URL}/api/runs/{rid}").status_code == 404

    # Published endpoints unchanged
    def test_published_endpoints(self, s):
        for p in ("overview", "filters", "conditions", "tests", "figures", "reproducibility"):
            assert s.get(f"{BASE_URL}/api/qem/{p}").status_code == 200, p
        assert s.get(f"{BASE_URL}/api/qem/overview").json()["standard"]["n_raw_rows"] == 255960

    # Brute-force lockout (distinct XFF so the real IP is not locked)
    def test_lockout(self, s):
        h = xff()
        codes = [s.post(f"{BASE_URL}/api/auth/login", json={"password": "bad"}, headers=h).status_code for _ in range(5)]
        assert codes == [401] * 5
        r = s.post(f"{BASE_URL}/api/auth/login", json={"password": PW}, headers=h)
        assert r.status_code == 429, r.status_code
