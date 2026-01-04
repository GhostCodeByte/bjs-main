# Einstiegspunkt der Anwendung
# - Lädt die Flask-App aus app/__init__.py
# - Startet den Dev-Server (debug=True) nur für Entwicklung
# - host='0.0.0.0' bindet an alle Interfaces (z. B. für iPads im selben Netz)
# Hinweis: Für Produktion einen WSGI-Server (z. B. gunicorn/uwsgi) verwenden.

from app import app

if __name__ == "__main__":
    # Debug-Modus nur in der Entwicklung aktivieren
    # Port bei Bedarf anpassen (Standard: 5000)
    app.run(debug=True, host='0.0.0.0', port=5000)
