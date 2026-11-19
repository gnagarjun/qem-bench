#!/usr/bin/env bash
# Build the QEM-Bench image, push it to Lightsail and roll out a new deployment.
#   ./deploy/lightsail/deploy.sh            build + push + deploy
#   ./deploy/lightsail/deploy.sh --create   first time: also create the container service
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/deploy/lightsail"
ENV_FILE="$HERE/lightsail.env"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE (copy lightsail.env.example and fill it in)"; exit 1; }
set -a; . "$ENV_FILE"; set +a
for v in AWS_REGION SERVICE_NAME SERVICE_POWER MONGO_URL DB_NAME ADMIN_PASSWORD JWT_SECRET CORS_ORIGINS; do
  [ -n "${!v:-}" ] || { echo "$v is empty in $ENV_FILE"; exit 1; }
done
export AWS_REGION

if [ "${1:-}" = "--create" ]; then
  echo "==> Creating container service $SERVICE_NAME ($SERVICE_POWER, 1 node)"
  aws lightsail create-container-service --service-name "$SERVICE_NAME" --power "$SERVICE_POWER" --scale 1 >/dev/null
  echo "    Waiting for the service to become READY (a few minutes)..."
  until [ "$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].state' --output text)" = "READY" ]; do sleep 15; done
fi

echo "==> Building linux/amd64 image"
docker buildx build --platform linux/amd64 -t qem-bench:latest --load "$ROOT"

echo "==> Pushing image to Lightsail"
aws lightsail push-container-image --service-name "$SERVICE_NAME" --label app --image qem-bench:latest

RENDERED="$HERE/.rendered-deployment.json"
python3 - "$HERE/deployment.template.json" "$RENDERED" <<'PY'
import json, os, sys
tpl = json.load(open(sys.argv[1]))
c = tpl["containers"]["app"]
c["image"] = f":{os.environ['SERVICE_NAME']}.app.latest"
c["environment"] = {k: os.environ[k] for k in ("MONGO_URL", "DB_NAME", "ADMIN_PASSWORD", "JWT_SECRET", "CORS_ORIGINS")}
json.dump(tpl, open(sys.argv[2], "w"), indent=2)
PY

echo "==> Creating deployment"
aws lightsail create-container-service-deployment --service-name "$SERVICE_NAME" --cli-input-json "file://$RENDERED" >/dev/null
rm -f "$RENDERED"
echo "    Waiting for the deployment to go ACTIVE..."
for _ in $(seq 1 60); do
  state=$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].currentDeployment.state' --output text)
  [ "$state" = "ACTIVE" ] && break
  [ "$state" = "FAILED" ] && { echo "Deployment FAILED. See: aws lightsail get-container-log --service-name $SERVICE_NAME --container-name app"; exit 1; }
  sleep 15
done
URL=$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --query 'containerServices[0].url' --output text)
echo "==> Live at $URL"
curl -fsS "${URL%/}/api/health" && echo
