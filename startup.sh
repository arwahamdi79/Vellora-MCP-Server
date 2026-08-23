#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
python -m db.init_db
echo "Vellora database ready."
echo "Starting platform on http://127.0.0.1:${PLATFORM_PORT:-5000}"
exec python platform/app.py
