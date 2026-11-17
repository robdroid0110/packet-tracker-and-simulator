#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="http://127.0.0.1:8765"
if ! curl -fsS "$URL/api/health" >/dev/null 2>&1; then
  nohup "$ROOT/netlab" serve >"$ROOT/netlab.log" 2>&1 </dev/null &
  for _ in {1..40}; do
    curl -fsS "$URL/api/health" >/dev/null 2>&1 && break
    sleep 0.1
  done
fi
xdg-open "$URL" >/dev/null 2>&1 &
