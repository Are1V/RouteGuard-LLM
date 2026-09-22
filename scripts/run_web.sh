#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_host="${ROUTEGUARD_API_HOST:-127.0.0.1}"
api_port="${ROUTEGUARD_API_PORT:-8000}"
web_host="${ROUTEGUARD_WEB_HOST:-127.0.0.1}"
web_port="${ROUTEGUARD_WEB_PORT:-3000}"
# Prefer an activated environment, then the repository's .venv, then PATH, so the
# script works whether the project was installed into a venv, conda, or the system.
find_python() {
  local candidate
  for candidate in \
    "${ROUTEGUARD_PYTHON:-}" \
    "${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python}" \
    "$project_dir/.venv/bin/python" \
    "$(command -v python3 || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]] &&
      "$candidate" -c "import routeguard, uvicorn, fastapi" 2>/dev/null; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if ! python_bin="$(find_python)"; then
  echo "RouteGuard is not installed with its API extra in any Python on this machine." >&2
  echo "Run:  python3 -m venv .venv && .venv/bin/pip install -e '.[dev,api]'" >&2
  echo "Or set ROUTEGUARD_PYTHON to the interpreter that has it installed." >&2
  exit 1
fi
if [[ ! -d "$project_dir/apps/web/node_modules" ]]; then
  echo "Frontend dependencies not found. Run: cd apps/web && npm install" >&2
  exit 1
fi

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://$api_host:$api_port/api/v1}"
export ROUTEGUARD_CORS_ORIGINS="${ROUTEGUARD_CORS_ORIGINS:-http://localhost:$web_port,http://$web_host:$web_port}"

"$python_bin" -m uvicorn apps.api.main:app \
  --app-dir "$project_dir" --host "$api_host" --port "$api_port" &
api_pid=$!

cleanup() {
  kill "$api_pid" 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready_url="http://$api_host:$api_port/api/v1/ready"
for _ in {1..100}; do
  if "$python_bin" -c "import urllib.request; urllib.request.urlopen('$ready_url', timeout=1).read()" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$api_pid" 2>/dev/null; then
    echo "The RouteGuard API failed to start." >&2
    exit 1
  fi
  sleep 0.2
done

if ! kill -0 "$api_pid" 2>/dev/null; then
  echo "The RouteGuard API stopped before the frontend could start." >&2
  exit 1
fi

echo "RouteGuard API: http://$api_host:$api_port/docs"
echo "RouteGuard web: http://$web_host:$web_port"
cd "$project_dir/apps/web"
npm run dev -- --hostname "$web_host" --port "$web_port"
