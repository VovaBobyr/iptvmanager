#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
port="${1:-8000}"
python -m uvicorn iptv_manager.app:app --host 0.0.0.0 --port "$port"
