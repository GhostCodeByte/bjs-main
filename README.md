# BJS Projektstruktur

Dieses Projekt ist eine Flask-Webanwendung zur Verwaltung von Schülerdaten, Riegen und Disziplinen. Die Struktur wurde modularisiert und klar in Backend (inkl. Datenbank) und Frontend (Templates/Static) getrennt.

## Strukturübersicht

```
backend/
    backend.py              # Datenbank-Backend und Logik (CRUD, CSV-Import, RiegenManager)
    database/
        bjs.db              # SQLite-Datenbank
app/
    __init__.py             # Flask-App, Blueprints, DB-Pfad
    routes/
        auth.py             # Login/Logout, Admin
        schueler.py         # Schüler-Aktionen/Ergebnisse
        riegen.py           # Laden von Riegen/Disziplinen
        debug.py            # Debug-Endpunkte (nur Entwicklung)
frontend/
    static/
        styles.css          # Styles fürs Frontend
    templates/
        admin.html          # Admin-Oberfläche
        index.html          # Hauptseite
        login.html          # Login-Seite
main.py                     # Startet die Anwendung
README.md                   # Diese Datei
todo.txt                    # Offene Punkte/ToDos
```

## Wichtige Komponenten

- main.py: Startet die Anwendung und lädt die Flask-App aus `app/__init__.py`.
- app/__init__.py: Initialisiert Flask, Sessions und registriert die Blueprints. Setzt `template_folder` und `static_folder` auf `frontend/templates` bzw. `frontend/static`.
- app/routes/: Enthält die modularen Routen für Authentifizierung, Schüler-Aktionen, Riegen-Laden und optionale Debug-Endpunkte.
- backend/: Beinhaltet die komplette Datenbanklogik (SQLite), inkl. CSV-Import und Riegen-Management.
- frontend/: Enthält Templates (Jinja2) und statische Assets (CSS).

## Starten der Anwendung

```bash
python main.py
```

- Die Anwendung läuft auf http://localhost:5000
- Serverseitige Sessions werden im Ordner `flask_session` abgelegt.

## Debug-Hinweis

- Der `debug`-Blueprint stellt Endpunkte wie `/debug_db`, `/debug_post_data`, `/debug_current_session` und `/debug_frontend_data` bereit, um während der Entwicklung Datenstrukturen und Session-Zustände zu prüfen.
- Diese Endpunkte sind nur für die Entwicklung gedacht und sollten in produktiven Umgebungen deaktiviert/entfernt werden.

---
