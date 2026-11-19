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
  svc_state() {
    local out
    if out=$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].state' --output text 2>&1); then
      echo "$out"
    elif grep -q "NotFoundException\|does not exist" <<<"$out"; then
      echo MISSING
    else
      echo "AWS error while reading the container service: $out" >&2
      exit 1
    fi
  }

  if [ "$(svc_state)" = "MISSING" ]; then
    echo "==> Creating container service $SERVICE_NAME ($SERVICE_POWER, 1 node)"
    aws lightsail create-container-service --service-name "$SERVICE_NAME" --power "$SERVICE_POWER" --scale 1 >/dev/null
  fi
  echo "==> Waiting for $SERVICE_NAME to accept a deployment"
  ready=0
  for _ in $(seq 1 80); do
    state=$(svc_state)
    case "$state" in READY|RUNNING) ready=1; break ;; esac
    sleep 15
  done
  [ "$ready" = 1 ] || { echo "Service $SERVICE_NAME did not become READY in 20 minutes (state: $state)"; exit 1; }

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
  VERSION=$(aws lightsail create-container-service-deployment --service-name "$SERVICE_NAME" --cli-input-json "file://$RENDERED" \
    --query 'containerService.nextDeployment.version' --output text)
  case "$VERSION" in ''|None) echo "Lightsail did not return a deployment version"; exit 1 ;; esac
  echo "    Waiting for deployment version $VERSION to go ACTIVE (usually 3-6 minutes)"
  sleep "${DEPLOY_SETTLE_S:-20}"
  active=0
  for _ in $(seq 1 60); do
    read -r cur_v cur next_v next < <(aws lightsail get-container-services --service-name "$SERVICE_NAME" --output text \
      --query 'containerServices[0].[currentDeployment.version, currentDeployment.state, nextDeployment.version, nextDeployment.state]')
    if [ "$cur_v" = "$VERSION" ] && [ "$cur" = "ACTIVE" ]; then active=1; break; fi
    if { [ "$next_v" = "$VERSION" ] && [ "$next" = "FAILED" ]; } || { [ "$cur_v" = "$VERSION" ] && [ "$cur" = "FAILED" ]; } \
       || { [ "$next_v" = "None" ] && [ "$cur_v" != "$VERSION" ]; }; then
      echo "Deployment version $VERSION FAILED (still serving version $cur_v). Recent container log:"
      aws lightsail get-container-log --service-name "$SERVICE_NAME" --container-name app --query 'logEvents[-40:].message' --output text || true
      exit 1
    fi
    sleep 15
  done
  [ "$active" = 1 ] || { echo "Deployment version $VERSION did not become ACTIVE in 15 minutes"; exit 1; }
  URL=$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].url' --output text)
  echo "==> Live at $URL"
  curl -fsS --retry 5 --retry-delay 10 "${URL%/}/api/health" && echo
  [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "### Deployed version $VERSION to $URL" >> "$GITHUB_STEP_SUMMARY"
  [ -n "${GITHUB_OUTPUT:-}" ] && echo "url=$URL" >> "$GITHUB_OUTPUT"
  return 0
}

case "$STEP" in
  build) build ;;
  release) release ;;
  all) build; release ;;
  *) echo "usage: $0 [build|release]"; exit 2 ;;
esac
