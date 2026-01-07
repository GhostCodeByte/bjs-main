#!/usr/bin/env sh
# Start the Flask development server for the BJS app.
# Usage: chmod +x scripts/start_dev.sh && ./scripts/start_dev.sh

set -eu

# Resolve project root (script may be called from anywhere)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# Optional: activate virtualenv if present
if [ -f "venv/bin/activate" ]; then
  . "venv/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
  . ".venv/bin/activate"
fi

export ENV=development
export FLASK_APP=main.py
export FLASK_ENV=development
export PYTHONPATH="${PROJECT_ROOT}"

echo "Starting Flask dev server (http://127.0.0.1:5000) with ENV=${ENV}"
exec python -m flask run --debug --host=127.0.0.1 --port=5000
