#!/usr/bin/env bash
set -euo pipefail

if ! python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  python -m pip install -r requirements.txt
fi

mkdir -p data
exec env PYTHONPATH=src uvicorn a_stock_platform.app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
