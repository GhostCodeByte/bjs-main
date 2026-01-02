#!/usr/bin/env sh
# Start the Flask app in production using gunicorn.
# Usage: chmod +x scripts/start_prod.sh && ./scripts/start_prod.sh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Optional: activate virtualenv if present
if [ -f "venv/bin/activate" ]; then
  . "venv/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
  . ".venv/bin/activate"
fi

export ENV=production
export FLASK_APP=main:app
export PYTHONPATH="${PROJECT_ROOT}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
WORKERS="${WORKERS:-4}"
TIMEOUT="${TIMEOUT:-120}"

echo "Starting gunicorn on ${HOST}:${PORT} with ${WORKERS} workers (timeout=${TIMEOUT}s)"
exec gunicorn -w "${WORKERS}" -b "${HOST}:${PORT}" --timeout "${TIMEOUT}" main:app
