#!/bin/bash
# Startet die Anwendung reproduzierbar im Produktions-Modus.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_DIR"

echo "--- Starte BJS Produktion ---"

if [ -f ".venv/bin/activate" ]; then
    echo "Aktiviere projektlokales Virtual Environment (.venv)..."
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
fi

if ! command -v gunicorn >/dev/null 2>&1; then
    echo "Gunicorn wurde nicht gefunden."
    echo "Installiere die Abhaengigkeiten zuerst, z. B. mit:"
    echo "  python -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

export ENV=production
export FLASK_APP=main:app
export PYTHONPATH="$PROJECT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
# SQLite laeuft stabiler mit einem Worker und Threads statt mehreren Prozessen.
WORKERS="${WORKERS:-1}"
THREADS="${THREADS:-8}"

echo "Projektverzeichnis: $PROJECT_DIR"
echo "Starten auf http://$HOST:$PORT mit $WORKERS Worker und $THREADS Threads..."
echo "Druecke STRG+C zum Beenden."

exec gunicorn \
    --workers "$WORKERS" \
    --threads "$THREADS" \
    --bind "$HOST:$PORT" \
    --access-logfile - \
    --error-logfile - \
    --timeout 120 \
    main:app
