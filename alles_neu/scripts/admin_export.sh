#!/usr/bin/env sh
# Helper script to run the admin CLI for exporting/importing the offline DB.
# Usage:
#   chmod +x scripts/admin_export.sh
#   scripts/admin_export.sh --csv path/to/schueler.csv --output bjs_database_2025.db
#
# Optional flags:
#   --log path/to/log.txt        Append CLI output to a log file
#   --quiet                     Reduce verbosity
#   --help                      Show this help
#
# Notes:
# - The CLI lives at alles_neu/admin/cli.py and supports CSV -> SQLite export.
# - The resulting DB file can be uploaded via the web UI (/admin/upload_db).
# - Adjust DEFAULT_OUTPUT_DIR to control where the DB file is written.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADMIN_DIR="${PROJECT_ROOT}/admin"
DEFAULT_OUTPUT_DIR="${ADMIN_DIR}"

CSV_FILE=""
OUTPUT_FILE=""
LOG_FILE=""
QUIET=0

show_help() {
  sed -n '1,30p' "$0"
  exit 0
}

# Parse args
while [ $# -gt 0 ]; do
  case "$1" in
    --csv)
      CSV_FILE="$2"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --log)
      LOG_FILE="$2"
      shift 2
      ;;
    --quiet)
      QUIET=1
      shift
      ;;
    --help|-h)
      show_help
      ;;
    *)
      echo "Unbekannte Option: $1" >&2
      exit 1
      ;;
  esac
done

if [ -z "${CSV_FILE}" ]; then
  echo "Fehler: --csv ist erforderlich" >&2
  exit 1
fi

if [ -z "${OUTPUT_FILE}" ]; then
  year="$(date +%Y)"
  OUTPUT_FILE="bjs_database_${year}.db"
fi

# Resolve paths
CSV_PATH="$(cd "$(dirname "${CSV_FILE}")" && pwd)/$(basename "${CSV_FILE}")"
OUTPUT_PATH="${DEFAULT_OUTPUT_DIR}/${OUTPUT_FILE}"

if [ ! -f "${CSV_PATH}" ]; then
  echo "Fehler: CSV nicht gefunden: ${CSV_PATH}" >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

# Activate virtualenv if present
if [ -f "venv/bin/activate" ]; then
  . "venv/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
  . ".venv/bin/activate"
fi

export PYTHONPATH="${PROJECT_ROOT}"

CMD="python -m admin.cli --csv \"${CSV_PATH}\" --output \"${OUTPUT_PATH}\""
[ "${QUIET}" -eq 1 ] && CMD="${CMD} --quiet"

echo "Starte Export:"
echo "  CSV:     ${CSV_PATH}"
echo "  Output:  ${OUTPUT_PATH}"
[ -n "${LOG_FILE}" ] && echo "  Log:     ${LOG_FILE}"
[ "${QUIET}" -eq 1 ] && echo "  Mode:    quiet"

# Run command
if [ -n "${LOG_FILE}" ]; then
  LOG_PATH="$(cd "$(dirname "${LOG_FILE}")" && pwd)/$(basename "${LOG_FILE}")"
  eval "${CMD}" 2>&1 | tee -a "${LOG_PATH}"
else
  eval "${CMD}"
fi

echo "Fertig. Datei gespeichert unter: ${OUTPUT_PATH}"
