#!/usr/bin/env bash
# Build, push and roll out QEM-Bench on an AWS Lightsail container service.
#   ./deploy/lightsail/deploy.sh            build + release (local use)
#   ./deploy/lightsail/deploy.sh build      build the linux/amd64 image qem-bench:latest only
#   ./deploy/lightsail/deploy.sh release    push qem-bench:latest and deploy it (used by GitHub Actions)
# Settings come from deploy/lightsail/lightsail.env if present, otherwise from the environment.
# The container service is created automatically the first time.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/deploy/lightsail"
ENV_FILE="$HERE/lightsail.env"
STEP="${1:-all}"
[ "$STEP" = "--create" ] && STEP=all
IMAGE="${IMAGE:-qem-bench:latest}"

if [ -f "$ENV_FILE" ]; then set -a; . "$ENV_FILE"; set +a; fi

build() {
  echo "==> Building linux/amd64 image $IMAGE"
  docker buildx build --platform linux/amd64 -t "$IMAGE" --load "$ROOT"
}

release() {
  for v in AWS_REGION SERVICE_NAME SERVICE_POWER MONGO_URL DB_NAME ADMIN_PASSWORD JWT_SECRET CORS_ORIGINS; do
    [ -n "${!v:-}" ] || { echo "Missing setting: $v (lightsail.env or environment)"; exit 1; }
  done
  export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
  svc_state() { aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].state' --output text 2>/dev/null || echo MISSING; }

  if [ "$(svc_state)" = "MISSING" ]; then
    echo "==> Creating container service $SERVICE_NAME ($SERVICE_POWER, 1 node)"
    aws lightsail create-container-service --service-name "$SERVICE_NAME" --power "$SERVICE_POWER" --scale 1 >/dev/null
  fi
  echo "==> Waiting for $SERVICE_NAME to accept a deployment"
  for _ in $(seq 1 80); do
    case "$(svc_state)" in READY|RUNNING) break ;; esac
    sleep 15
  done

  echo "==> Pushing $IMAGE"
  aws lightsail push-container-image --service-name "$SERVICE_NAME" --label app --image "$IMAGE"

  RENDERED="$(mktemp "${TMPDIR:-/tmp}/qem-deploy-XXXXXX.json")"
  trap 'rm -f "$RENDERED"' EXIT
  python3 - "$HERE/deployment.template.json" "$RENDERED" <<'PY'
import json, os, sys
tpl = json.load(open(sys.argv[1]))
c = tpl["containers"]["app"]
c["image"] = f":{os.environ['SERVICE_NAME']}.app.latest"
c["environment"] = {k: os.environ[k] for k in ("MONGO_URL", "DB_NAME", "ADMIN_PASSWORD", "JWT_SECRET", "CORS_ORIGINS")}
json.dump(tpl, open(sys.argv[2], "w"))
PY

  echo "==> Creating deployment"
  aws lightsail create-container-service-deployment --service-name "$SERVICE_NAME" --cli-input-json "file://$RENDERED" >/dev/null
  echo "    Waiting for the new deployment to go ACTIVE (usually 3-6 minutes)"
  sleep ${DEPLOY_SETTLE_S:-20}
  for _ in $(seq 1 60); do
    next=$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].nextDeployment.state' --output text)
    cur=$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].currentDeployment.state' --output text)
    if [ "$next" = "None" ] && [ "$cur" = "ACTIVE" ]; then break; fi
    if [ "$cur" = "FAILED" ] || [ "$next" = "FAILED" ]; then
      echo "Deployment FAILED. Recent container log:"
      aws lightsail get-container-log --service-name "$SERVICE_NAME" --container-name app --query 'logEvents[-40:].message' --output text || true
      exit 1
    fi
    sleep 15
  done
  URL=$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].url' --output text)
  echo "==> Live at $URL"
  curl -fsS --retry 5 --retry-delay 10 "${URL%/}/api/health" && echo
  [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "### Deployed to $URL" >> "$GITHUB_STEP_SUMMARY"
  [ -n "${GITHUB_OUTPUT:-}" ] && echo "url=$URL" >> "$GITHUB_OUTPUT"
  return 0
}

case "$STEP" in
  build) build ;;
  release) release ;;
  all) build; release ;;
  *) echo "usage: $0 [build|release]"; exit 2 ;;
esac
