#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export HOST_PORT="${HOST_PORT:-8092}"
export PREVIEW_DATA_DIR="${PREVIEW_DATA_DIR:-/srv/data/tempo-preview}"
export PREVIEW_ENV_FILE="${PREVIEW_ENV_FILE:-/srv/config/tempo/.env.preview}"
export APP_NAME="${APP_NAME:-Curriculum Planner Preview}"
export REPO_URL="${REPO_URL:-https://github.com/Marcos-A/tempo}"

# Identify the build by its commit; refuses uncommitted changes unless ALLOW_DIRTY=1.
set -a
eval "$("$repo_root/scripts/build-env.sh")"
set +a
"$repo_root/scripts/update-release-info.sh" "$repo_root/build-meta/release-info.json" "$GIT_COMMIT"

echo "Deploying preview from: $repo_root"
echo "Branch: $(git branch --show-current 2>/dev/null || echo detached)"
echo "Commit: $GIT_COMMIT"
echo "Preview URL: https://tempo-preview.marcos-a.com/"
echo "Preview data dir: $PREVIEW_DATA_DIR"
echo "Preview env file: $PREVIEW_ENV_FILE"

docker compose -f docker-compose.preview.yml up -d --build

echo
"$repo_root/scripts/show_planner_runtime.sh"
