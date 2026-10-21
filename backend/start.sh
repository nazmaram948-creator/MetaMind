#!/usr/bin/env bash
set -euo pipefail

export DEV_MODE="${DEV_MODE:-true}"
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
