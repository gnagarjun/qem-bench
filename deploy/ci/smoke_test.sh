#!/usr/bin/env bash
# End-to-end check of a running QEM-Bench server: site, published data, owner login and one tiny simulation.
#   ./deploy/ci/smoke_test.sh http://127.0.0.1:8000 <owner-password> [--no-run]
# --no-run skips the simulation (used against the live site so no run is created there).
set -euo pipefail
B="${1%/}"
PW="$2"
MODE="${3:-}"
j() { python3 -c "import sys,json;d=json.load(sys.stdin);print($1)"; }

echo "-- waiting for $B/api/health"
for _ in $(seq 1 60); do curl -fsS "$B/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -fsS "$B/api/health" | grep -q '"ok":true'
echo "-- website"
curl -fsS "$B/" | grep -q "QEM-Bench | Results Viewer"
curl -fsS -o /dev/null "$B/run-simulations-deep-link"
echo "-- published results"
test "$(curl -fsS "$B/api/qem/overview" | j "len(d['standard']['runs'])")" -ge 1
test "$(curl -fsS "$B/api/qem/conditions?limit=5" | j "len(d['rows'])")" -ge 1
echo "-- owner login"
test "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$B/api/auth/login" -H 'Content-Type: application/json' -d '{"password":"wrong"}')" = 401
TOKEN=$(curl -fsS -X POST "$B/api/auth/login" -H 'Content-Type: application/json' -d "$(python3 -c 'import json,sys;print(json.dumps({"password":sys.argv[1]}))' "$PW")" | j "d['token']") \
  || { echo "owner login failed: check the password"; exit 1; }
curl -fsS "$B/api/auth/me" -H "Authorization: Bearer $TOKEN" >/dev/null
if [ "$MODE" = "--no-run" ]; then echo "SMOKE TEST PASSED (no simulation)"; exit 0; fi
echo "-- tiny simulation run"
RID=$(curl -fsS -X POST "$B/api/runs" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"ci smoke","instances":["bell_cx"],"noise":[{"base":"moderate"}],"shots":[1024],"methods":["readout","zne_linear"],"repetitions":3}' | j "d['run_id']")
for _ in $(seq 1 90); do
  STATUS=$(curl -fsS "$B/api/runs/$RID" | j "d['status']")
  [ "$STATUS" != "running" ] && break
  sleep 2
done
if [ "$STATUS" != "completed" ]; then curl -fsS "$B/api/runs/$RID"; echo; echo "run ended as $STATUS"; exit 1; fi
test "$(curl -fsS "$B/api/runs/$RID/conditions" | j "d['total']")" -ge 1
curl -fsS -X DELETE "$B/api/runs/$RID" -H "Authorization: Bearer $TOKEN" >/dev/null
echo "SMOKE TEST PASSED"
