#!/bin/bash
# start_linux_prod.sh
# Startet die Anwendung im Produktions-Modus (nutzt Conda 'base' Environment)

# 1. Zum Projektverzeichnis wechseln (wo dieses Skript liegt)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "--- Starte BJS Produktion (Conda Base) ---"

# 2. Versuche Conda zu initialisieren
# Da 'conda activate' in Skripten oft Probleme macht, nutzen wir den Hook.
if ! command -v conda &> /dev/null
then
    echo "Conda Befehl nicht gefunden. Suche in Standard-Pfaden..."
    POSSIBLE_PATHS=(
        "$HOME/anaconda3/etc/profile.d/conda.sh"
        "$HOME/miniconda3/etc/profile.d/conda.sh"
        "/opt/conda/etc/profile.d/conda.sh"
        "/usr/local/miniconda3/etc/profile.d/conda.sh"
    )

    CONDA_FOUND=false
    for path in "${POSSIBLE_PATHS[@]}"; do
        if [ -f "$path" ]; then
            source "$path"
            CONDA_FOUND=true
            echo "Conda gefunden in: $path"
            break
        fi
    done
else
    # Conda ist im Pfad, Hook initialisieren
    eval "$(conda shell.bash hook)"
fi

# 3. Base Environment aktivieren
echo "Aktiviere Conda 'base' Environment..."
conda activate base

# 4. Prüfen ob gunicorn installiert ist
if ! command -v gunicorn &> /dev/null
then
    echo "Gunicorn ist nicht installiert. Installiere es jetzt..."
    pip install gunicorn
fi

# 5. Umgebungsvariablen für Produktion setzen
export ENV=production
export FLASK_APP=main:app
# PYTHONPATH stellt sicher, dass Module im aktuellen Ordner gefunden werden
export PYTHONPATH=$(pwd)

# Einstellungen
HOST="0.0.0.0"
PORT="5000"
# Anzahl Worker: Formel (2 x CPUs) + 1 ist oft gut. 4 reicht locker für 20 Geräte.
WORKERS=4

echo "Starten auf http://$HOST:$PORT mit $WORKERS Workern..."
echo "Druecke STRG+C zum Beenden."

# 6. Gunicorn starten
exec gunicorn -w $WORKERS \
    -b $HOST:$PORT \
    --access-logfile - \
    --error-logfile - \
    --timeout 120 \
    main:app
