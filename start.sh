#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
[ -d .venv ] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
if [ "${LAYA_INSTALL_ML:-0}" = 1 ]; then .venv/bin/python -m pip install -r requirements-ml.txt; fi
(cd frontend && npm install --no-audit --no-fund && npm run build)
# Optional bounded crash supervision. SIGINT/SIGTERM stop both supervisor and child.
child=''
trap 'if [ -n "$child" ]; then kill "$child" 2>/dev/null || true; fi; exit 0' INT TERM
attempt=0
while :; do
  .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8000}" &
  child=$!
  code=0
  wait "$child" || code=$?
  [ "$code" -eq 0 ] && exit 0
  attempt=$((attempt+1))
  [ "$attempt" -ge 5 ] && exit "$code"
  echo "Motor detenido ($code). Reinicio $attempt/5 en 3 segundos."
  sleep 3
done
