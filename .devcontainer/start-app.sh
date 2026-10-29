#!/usr/bin/env bash
set -euo pipefail

mkdir -p data
pid_file="data/codespaces-server.pid"
log_file="data/codespaces-server.log"
health_url="http://127.0.0.1:8000/healthz"

app_is_healthy() {
  curl --silent --fail --max-time 2 "$health_url" >/dev/null 2>&1
}

if app_is_healthy; then
  exit 0
fi

if [[ -f "$pid_file" ]]; then
  previous_pid="$(cat "$pid_file")"
  if kill -0 "$previous_pid" 2>/dev/null; then
    previous_command="$(ps -p "$previous_pid" -o args= 2>/dev/null || true)"
    if [[ "$previous_command" == *"uvicorn iptv_manager.app:app"* ]]; then
      kill "$previous_pid" 2>/dev/null || true
    fi
  fi
  rm -f "$pid_file"
fi

nohup python -m uvicorn iptv_manager.app:app --host 0.0.0.0 --port 8000 >"$log_file" 2>&1 &
server_pid=$!
echo "$server_pid" >"$pid_file"

for _ in {1..20}; do
  if app_is_healthy; then
    exit 0
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    cat "$log_file" >&2
    rm -f "$pid_file"
    exit 1
  fi
  sleep 0.5
done

echo "IPTV Manager did not become healthy at $health_url" >&2
cat "$log_file" >&2
exit 1
