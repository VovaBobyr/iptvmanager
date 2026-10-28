#!/usr/bin/env bash
set -euo pipefail

mkdir -p data
pid_file="data/codespaces-server.pid"
log_file="data/codespaces-server.log"

if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
  exit 0
fi

nohup python -m uvicorn iptv_manager.app:app --host 0.0.0.0 --port 8000 >"$log_file" 2>&1 &
echo $! >"$pid_file"
