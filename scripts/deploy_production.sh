#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export HOST_PORT="${HOST_PORT:-8091}"
export DATA_DIR="${DATA_DIR:-/srv/data/tempo}"
export ENV_FILE="${ENV_FILE:-/srv/config/tempo/.env.prod}"
export IMAGE_NAME="${IMAGE_NAME:-tempo-web:local}"
export CONTAINER_NAME="${CONTAINER_NAME:-tempo-web}"
export APP_NAME="${APP_NAME:-Planificador curricular}"

echo "Deploying production from: $repo_root"
echo "Ref: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Branch: $(git branch --show-current 2>/dev/null || echo detached)"
echo "Production URL: https://tempo.marcos-a.com/"
echo "Host port: $HOST_PORT"
echo "Data dir: $DATA_DIR"
echo "Env file: $ENV_FILE"
echo "Container name: $CONTAINER_NAME"
echo "Image name: $IMAGE_NAME"

docker compose -f docker-compose.production.yml up -d --build

echo
"$repo_root/scripts/show_planner_runtime.sh"
