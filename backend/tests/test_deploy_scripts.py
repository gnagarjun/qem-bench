# Deploy tooling tests: deploy/lightsail/deploy.sh release with a stub `aws` (no real AWS), setup-github-oidc.sh
# with a stub `aws`, and static checks of the GitHub Actions workflow.
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy/lightsail/deploy.sh"
OIDC = ROOT / "deploy/lightsail/setup-github-oidc.sh"
WF = ROOT / ".github/workflows/deploy-lightsail.yml"
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

STUB_AWS = r"""#!/usr/bin/env bash
# Stub aws CLI. State lives in $STUB_DIR.
echo "$*" >> "$STUB_DIR/calls.log"
args="$*"
case "$args" in
  "sts get-caller-identity"*) echo 123456789012 ;;
  "iam get-open-id-connect-provider"*) [ -f "$STUB_DIR/provider" ] || exit 254 ;;
  "iam create-open-id-connect-provider"*) touch "$STUB_DIR/provider"; echo '{}' ;;
  "iam get-role"*"--query"*) echo "arn:aws:iam::123456789012:role/qem-bench-github-deploy" ;;
  "iam get-role"*) [ -f "$STUB_DIR/role" ] || exit 254; echo '{}' ;;
  "iam create-role"*)
     touch "$STUB_DIR/role"
     prev=""; for a in "$@"; do [ "$prev" = "--assume-role-policy-document" ] && printf '%s' "$a" > "$STUB_DIR/trust.json"; prev="$a"; done
     echo '{}' ;;
  "iam update-assume-role-policy"*)
     prev=""; for a in "$@"; do [ "$prev" = "--policy-document" ] && printf '%s' "$a" > "$STUB_DIR/trust_updated.json"; prev="$a"; done ;;
  "iam put-role-policy"*)
     prev=""; for a in "$@"; do [ "$prev" = "--policy-document" ] && printf '%s' "$a" > "$STUB_DIR/policy.json"; prev="$a"; done ;;
  "lightsail get-container-services"*"containerServices[0].state"*)
     [ -f "$STUB_DIR/created" ] || { echo "NotFoundException" >&2; exit 254; }
     echo READY ;;
  "lightsail create-container-service "*) touch "$STUB_DIR/created"; echo '{}' ;;
  "lightsail push-container-image"*) echo "Refer to this image as \":${SVC}.app.1\"" ;;
  "lightsail create-container-service-deployment"*)
     f="${args##*file://}"; f="${f%% *}"; cp "$f" "$STUB_DIR/rendered.json"; echo 7 ;;
  "lightsail get-container-services"*"currentDeployment.version"*)
     # new deployment is version 7; STUB_CUR / STUB_NEXT simulate its state, STUB_ROLLBACK a silent rollback to 6
     if [ -n "$STUB_ROLLBACK" ]; then printf '6\tACTIVE\tNone\tNone\n'
     elif [ -n "$STUB_NEXT" ]; then printf '6\tACTIVE\t7\t%s\n' "$STUB_NEXT"
     else printf '7\t%s\tNone\tNone\n' "${STUB_CUR:-ACTIVE}"; fi ;;
  "lightsail get-container-services"*"containerServices[0].url"*) echo "$STUB_URL" ;;
  "lightsail get-container-log"*) echo "stub container log line" ;;
  *) echo "unexpected aws call: $args" >&2; exit 99 ;;
esac
"""

PASSWORD = 'p"w\\ x\'q $HOME `id` ok'


def _stub_env(tmp_path, **extra):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    aws = bindir / "aws"
    aws.write_text(STUB_AWS)
    aws.chmod(aws.stat().st_mode | stat.S_IEXEC)
    stub = tmp_path / "stub"
    stub.mkdir(exist_ok=True)
    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}", "HOME": os.environ.get("HOME", "/root"), "TMPDIR": str(tmp_path),
        "STUB_DIR": str(stub), "SVC": "TEST-qem", "STUB_URL": f"{BASE_URL}/",
        "AWS_REGION": "us-east-1", "SERVICE_NAME": "TEST-qem", "SERVICE_POWER": "medium",
        "MONGO_URL": "mongodb+srv://u:p%40ss@x.mongodb.net/?retryWrites=true&w=majority", "DB_NAME": "qem_bench",
        "ADMIN_PASSWORD": PASSWORD, "JWT_SECRET": "a" * 64, "CORS_ORIGINS": "https://a.example,https://b.example",
        "DEPLOY_SETTLE_S": "0", "GITHUB_OUTPUT": str(tmp_path / "gh_output"), "GITHUB_STEP_SUMMARY": str(tmp_path / "gh_summary"),
    }
    env.update(extra)
    return env, stub


def _run(script, args, env):
    return subprocess.run(["bash", str(script), *args], env=env, capture_output=True, text=True, timeout=120)


class TestDeployRelease:
    def test_release_creates_service_pushes_and_renders(self, tmp_path):
        assert not (ROOT / "deploy/lightsail/lightsail.env").exists(), "lightsail.env would override test env"
        env, stub = _stub_env(tmp_path)
        r = _run(DEPLOY, ["release"], env)
        print(r.stdout, r.stderr)
        assert r.returncode == 0, r.stderr
        calls = (stub / "calls.log").read_text()
        assert "lightsail create-container-service --service-name TEST-qem --power medium --scale 1" in calls
        assert "lightsail push-container-image --service-name TEST-qem --label app --image qem-bench:latest" in calls
        assert calls.index("create-container-service ") < calls.index("push-container-image") < calls.index("create-container-service-deployment")
        d = json.loads((stub / "rendered.json").read_text())
        c = d["containers"]["app"]
        assert c["image"] == ":TEST-qem.app.latest"
        assert c["ports"] == {"8000": "HTTP"}
        assert d["publicEndpoint"]["containerPort"] == 8000
        assert d["publicEndpoint"]["healthCheck"]["path"] == "/api/health"
        assert c["environment"] == {k: env[k] for k in ("MONGO_URL", "DB_NAME", "ADMIN_PASSWORD", "JWT_SECRET", "CORS_ORIGINS")}
        assert c["environment"]["ADMIN_PASSWORD"] == PASSWORD
        assert (tmp_path / "gh_output").read_text().strip() == f"url={BASE_URL}/"
        assert "Deployed version 7 to" in (tmp_path / "gh_summary").read_text()
        # rendered temp file cleaned up by trap
        assert not list(tmp_path.glob("qem-deploy-*.json"))

    def test_release_existing_service_skips_create(self, tmp_path):
        env, stub = _stub_env(tmp_path)
        (stub / "created").touch()
        r = _run(DEPLOY, ["release"], env)
        assert r.returncode == 0, r.stderr
        assert "create-container-service " not in (stub / "calls.log").read_text()

    @pytest.mark.parametrize("missing", ["AWS_REGION", "SERVICE_NAME", "SERVICE_POWER", "MONGO_URL", "DB_NAME",
                                         "ADMIN_PASSWORD", "JWT_SECRET", "CORS_ORIGINS"])
    def test_release_missing_setting_fails(self, tmp_path, missing):
        env, stub = _stub_env(tmp_path)
        env.pop(missing)
        r = _run(DEPLOY, ["release"], env)
        assert r.returncode != 0
        assert f"Missing setting: {missing}" in r.stdout
        assert not (stub / "calls.log").exists()

    @pytest.mark.parametrize("which", ["STUB_CUR", "STUB_NEXT"])
    def test_release_failed_deployment_exits_nonzero(self, tmp_path, which):
        env, stub = _stub_env(tmp_path, **{which: "FAILED"})
        r = _run(DEPLOY, ["release"], env)
        assert r.returncode != 0
        assert "Deployment version 7 FAILED" in r.stdout
        assert "stub container log line" in r.stdout
        assert not (tmp_path / "gh_output").exists()

    def test_release_silent_rollback_exits_nonzero(self, tmp_path):
        env, stub = _stub_env(tmp_path, STUB_ROLLBACK="1")
        r = _run(DEPLOY, ["release"], env)
        assert r.returncode != 0
        assert "still serving version 6" in r.stdout
        assert not (tmp_path / "gh_output").exists()

    def test_release_aws_error_is_not_treated_as_missing_service(self, tmp_path):
        env, stub = _stub_env(tmp_path)
        bad = tmp_path / "bin" / "aws"
        bad.write_text("#!/bin/sh\necho \"$*\" >> \"$STUB_DIR/calls.log\"\necho 'An error occurred (AccessDeniedException)' >&2\nexit 254\n")
        r = _run(DEPLOY, ["release"], env)
        assert r.returncode != 0
        assert "AccessDeniedException" in r.stderr
        assert "create-container-service " not in (stub / "calls.log").read_text()

    def test_release_wait_timeout_exits_nonzero(self, tmp_path):
        # Deployment never leaves DEPLOYING: after the wait loop runs out, release must fail, not report success.
        env, stub = _stub_env(tmp_path, STUB_NEXT="DEPLOYING")
        sleep = tmp_path / "bin" / "sleep"
        sleep.write_text("#!/bin/sh\nexit 0\n")
        sleep.chmod(0o755)
        r = _run(DEPLOY, ["release"], env)
        assert r.returncode != 0, "deploy.sh reported success although the deployment never became ACTIVE"
        assert not (tmp_path / "gh_output").exists()

    def test_bad_step_usage(self, tmp_path):
        env, _ = _stub_env(tmp_path)
        r = _run(DEPLOY, ["bogus"], env)
        assert r.returncode == 2


class TestOidcSetup:
    def test_first_run_creates_provider_role_and_policy(self, tmp_path):
        env, stub = _stub_env(tmp_path)
        r = _run(OIDC, ["me/qem-bench", "main"], env)
        print(r.stdout, r.stderr)
        assert r.returncode == 0, r.stderr
        calls = (stub / "calls.log").read_text()
        assert "iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com" in calls
        trust = json.loads((stub / "trust.json").read_text())
        st = trust["Statement"][0]
        assert st["Principal"]["Federated"] == "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
        assert st["Action"] == "sts:AssumeRoleWithWebIdentity"
        assert st["Condition"]["StringEquals"] == {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                                                   "token.actions.githubusercontent.com:sub": "repo:me/qem-bench:ref:refs/heads/main"}
        pol = json.loads((stub / "policy.json").read_text())
        assert pol["Statement"][0]["Action"] == "lightsail:*"
        assert r.stdout.strip().endswith("arn:aws:iam::123456789012:role/qem-bench-github-deploy")

    def test_second_run_is_idempotent_and_updates_trust(self, tmp_path):
        env, stub = _stub_env(tmp_path)
        (stub / "provider").touch()
        (stub / "role").touch()
        r = _run(OIDC, ["me/renamed", "release"], env)
        assert r.returncode == 0, r.stderr
        calls = (stub / "calls.log").read_text()
        assert "create-open-id-connect-provider" not in calls and "create-role" not in calls
        trust = json.loads((stub / "trust_updated.json").read_text())
        assert trust["Statement"][0]["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"] == "repo:me/renamed:ref:refs/heads/release"
        assert "put-role-policy" in calls

    def test_missing_repo_arg(self, tmp_path):
        env, _ = _stub_env(tmp_path)
        r = _run(OIDC, [], env)
        assert r.returncode != 0 and "usage" in r.stderr


class TestWorkflowStatic:
    def wf(self):
        return yaml.safe_load(WF.read_text())

    def test_only_manual_trigger(self):
        w = self.wf()
        on = w.get("on", w.get(True))
        assert list(on.keys()) == ["workflow_dispatch"]

    def test_jobs_gating_and_permissions(self):
        w = self.wf()
        assert w["permissions"] == {"contents": "read"}
        t, d = w["jobs"]["tests"], w["jobs"]["deploy"]
        assert "permissions" not in t
        assert d["needs"] == "tests"
        assert d["if"] == "github.ref == 'refs/heads/main'"
        assert d["permissions"] == {"contents": "read", "id-token": "write"}
        assert "environment" not in d  # no approval step
        runs = " ".join(s.get("run", "") for s in t["steps"])
        assert "uv python install 3.11" in runs and "pytest tests" in runs
        assert t["defaults"]["run"]["working-directory"] == "qem-bench"

    def test_deploy_steps(self):
        d = self.wf()["jobs"]["deploy"]
        steps = d["steps"]
        names = [s.get("name", s.get("uses")) for s in steps]
        assert names.index("Check settings") < names.index("Build image (linux/amd64)") < \
            names.index("Smoke-test the image before it goes live") < names.index("Sign in to AWS (OpenID Connect, no stored keys)")
        build = next(s for s in steps if s.get("name") == "Build image (linux/amd64)")
        assert build["with"]["platforms"] == "linux/amd64" and build["with"]["load"] is True
        aws = next(s for s in steps if "configure-aws-credentials" in s.get("uses", ""))
        assert aws["with"]["role-to-assume"] == "${{ secrets.AWS_DEPLOY_ROLE_ARN }}"
        assert "aws-access-key-id" not in aws["with"]
        assert d["services"]["mongo"]["image"].startswith("mongo")
        rel = next(s for s in steps if s.get("id") == "release")
        assert rel["run"] == "bash deploy/lightsail/deploy.sh release"
        assert "--no-run" in steps[-1]["run"] and "steps.release.outputs.url" in steps[-1]["run"]

    def test_check_settings_step_fails_clearly(self, tmp_path):
        d = self.wf()["jobs"]["deploy"]
        step = next(s for s in d["steps"] if s.get("name") == "Check settings")
        env = {"PATH": os.environ["PATH"], "AWS_REGION": "us-east-1", "SERVICE_NAME": "x", "SERVICE_POWER": "medium",
               "DB_NAME": "d", "CORS_ORIGINS": "c", "MONGO_URL": "m", "ADMIN_PASSWORD": "p", "JWT_SECRET": "", "AWS_DEPLOY_ROLE_ARN": ""}
        r = subprocess.run(["bash", "-e", "-c", step["run"]], env=env, capture_output=True, text=True)
        assert r.returncode == 1
        assert "::error::Missing repository variable or secret: JWT_SECRET" in r.stdout
        assert "::error::Missing repository variable or secret: AWS_DEPLOY_ROLE_ARN" in r.stdout
        env["JWT_SECRET"] = "j"
        env["AWS_DEPLOY_ROLE_ARN"] = "arn"
        r = subprocess.run(["bash", "-e", "-c", step["run"]], env=env, capture_output=True, text=True)
        assert r.returncode == 0 and r.stdout == ""
