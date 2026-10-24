#!/usr/bin/env bash
# SkillShift MY, macOS / Linux / Replit: one command from the repository root.
#   bash run.sh
# First run: creates .venv (not on Replit), installs Python packages, installs and
# builds the frontend. Then serves the app and the API on one port (default 8000).
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ -z "${REPL_ID:-}" ]; then            # own machine: use a local virtualenv
  [ -x .venv/bin/python ] || { echo "Creating .venv ..."; "$PY" -m venv .venv; }
  PY=.venv/bin/python
fi
"$PY" -c "import sys; sys.exit(sys.version_info < (3, 10))" || {
  echo "Python 3.10+ is needed (3.11 recommended)." >&2; exit 1; }

echo "Installing Python packages (first run downloads ~300 MB) ..."
"$PY" -m pip install -q --disable-pip-version-check -r backend/requirements.txt
"$PY" -m engine.build

if command -v npm >/dev/null 2>&1; then
  ( cd frontend && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build )
else
  echo "npm not found: install Node.js 20+ to build the frontend. The API still starts." >&2
fi

export ENGINE_MODE="${ENGINE_MODE:-true}"
HOST="${HOST:-127.0.0.1}"
[ -n "${REPL_ID:-}" ] && HOST=0.0.0.0
PORT="${PORT:-8000}"
echo
echo "SkillShift MY: open http://localhost:${PORT}   (Ctrl+C to stop)"
exec "$PY" -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
