#!/usr/bin/env bash
set -euo pipefail

resolve_container() {
  local candidate
  for candidate in "$@"; do
    if docker container inspect "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

labels=(
  "production"
  "preview"
)

production_candidates=(
  "curriculum-planner-web"
  "curriculum-planner-web-1"
)

preview_candidates=(
  "curriculum-planner-preview-web"
  "curriculum-planner-preview-web-1"
)

for label in "${labels[@]}"; do
  if [[ "$label" == "production" ]]; then
    candidates=("${production_candidates[@]}")
  else
    candidates=("${preview_candidates[@]}")
  fi

  if ! container="$(resolve_container "${candidates[@]}")"; then
    echo "=== $label ==="
    echo "status: not running"
    echo
    continue
  fi

  echo "=== $label ==="
  echo "container: $container"
  docker container inspect -f 'image: {{.Config.Image}}' "$container"
  docker container inspect -f 'ports: {{range $p, $bindings := .NetworkSettings.Ports}}{{printf "%s -> " $p}}{{range $bindings}}{{printf "%s:%s " .HostIp .HostPort}}{{end}}{{end}}' "$container"
  docker container inspect -f 'db mount: {{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Source}}{{end}}{{end}}' "$container"
  docker container inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$container" | sed -n 's/^DATABASE_URL=/database_url: /p'
  echo
done
