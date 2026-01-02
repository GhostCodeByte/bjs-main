# BJS – Bundesjugendspiele Verwaltung

Dieses Projekt ist eine Flask-Webanwendung zur Verwaltung von Schülerdaten, Riegen und Disziplinen für Bundesjugendspiele. Die neue Struktur (`alles_neu/`) bietet verbesserte Sicherheit, modulare Architektur und ein separates 


-Tool.

---

## Strukturübersicht

```
alles_neu/
├── app/                        # Flask-Webanwendung
│   ├── __init__.py             # App-Factory, Blueprints, DB-Setup
│   ├── database/
│   │   ├── database.py         # Haupt-Datenbank-Klasse (Runtime)
│   │   ├── create_data.py      # Hilfsskripte für Testdaten
│   │   └── bjs_database_YYYY.db # SQLite-Datenbank (Jahr-basiert)
│   ├── routes/
│   │   ├── auth.py             # Login/Logout, Admin-Dashboard, PIN-Verwaltung
│   │   └── input.py            # Erfassungs-Flow (Ergebnisse, Abwesenheit)
│   ├── static/
│   │   ├── auth.css            # Styles für Login
│   │   └── input.css           # Styles für Erfassung
│   └── templates/
│       ├── auth.html           # Login-Seite (Station + Admin)
│       ├── input.html          # Ergebnis-Erfassung
│       ├── admin_dashboard.html # Admin-Dashboard
│       ├── admin_disziplinen.html # Disziplin-Verwaltung
│       └── dashboard.html      # Fortschritts-Übersicht
├── admin/                      # Offline-Admin-Tool (Kivy)
│   ├── admin.py                # Kivy-App für Riegen-/DB-Verwaltung
│   ├── admin_database.py       # DB-Schema und Hilfsfunktionen
│   ├── utils.py                # CSV-Import, Riegen-Erstellung
│   ├── main.kv                 # Kivy-UI-Definition
│   └── test_data.csv           # Beispiel-CSV für Import
├── main.py                     # Flask-App starten
├── .env                        # Umgebungsvariablen (nicht im Repo)
└── TODO.md                     # Projekt-Roadmap
```

---

## Schnellstart

### 1. Umgebung einrichten

```bash
cd alles_neu
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Umgebungsvariablen konfigurieren

Erstelle eine `.env`-Datei in `alles_neu/`:

```env
SECRET_KEY=dein-geheimer-schluessel-hier
ADMIN_PASSWORD=sicheres-admin-passwort
DB_PATH=alles_neu/app/database/bjs_database_2025.db
STATION_DEFAULT_PIN=123456
STATION_DEFAULT_NAME=Station
STATION_DEFAULT_MAX_LOGINS=1
STATION_DEFAULT_PIN_LENGTH=6
```

### 3. Flask-App starten

```bash
cd alles_neu
python main.py
```

Die Anwendung läuft auf **http://localhost:5000**

---

## Datenfluss

```
┌─────────────────┐     CSV-Import      ┌──────────────────┐
│  Schülerdaten   │ ──────────────────► │   Admin-Tool     │
│  (CSV-Datei)    │                     │   (Kivy/CLI)     │
└─────────────────┘                     └────────┬─────────┘
                                                 │
                                                 │ Erstellt DB offline
                                                 ▼
                                        ┌──────────────────┐
                                        │  SQLite-DB       │
                                        │  (bjs_YYYY.db)   │
                                        └────────┬─────────┘
                                                 │
                        ┌────────────────────────┼────────────────────────┐
                        │                        │                        │
                        ▼                        ▼                        ▼
               ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
               │  Admin-Upload   │     │  Station-Login  │     │  Dashboard      │
               │  (Web-UI)       │     │  (PIN-basiert)  │     │  (Fortschritt)  │
               └────────┬────────┘     └────────┬────────┘     └─────────────────┘
                        │                       │
                        ▼                       ▼
               ┌─────────────────────────────────────────────┐
               │           Flask-Webanwendung                │
               │  • Ergebnis-Erfassung                       │
               │  • Abwesenheits-Markierung                  │
               │  • Live-Fortschritts-Tracking               │
               │  • Disziplin-Konfiguration                  │
               └─────────────────────────────────────────────┘
```

---

## Admin-Tool (Kivy)

Das Admin-Tool dient zur **Offline-Vorbereitung** der Datenbank:

### Starten (GUI)

```bash
cd alles_neu/admin
python admin.py
```

### Starten (CLI/Headless)

```bash
cd alles_neu
python -m admin.cli --csv path/to/schueler.csv --output bjs_database_2025.db
```

### Funktionen

1. **CSV-Import**: Schülerdaten aus CSV importieren
2. **Riegen erstellen**: Riegenführer anlegen und Schüler zuweisen
3. **DB exportieren**: Fertige Datenbank für Web-App erzeugen

### CSV-Format

```csv
Geschlecht;Klasse;Name;Vorname;Geburtsjahr;Profil
m;5a;Mustermann;Max;2012;False
w;5a;Musterfrau;Maria;2012;True
```

| Spalte      | Beschreibung                          | Beispiel     |
|-------------|---------------------------------------|--------------|
| Geschlecht  | `m` oder `w`                          | `m`          |
| Klasse      | Stufe + Buchstabe                     | `5a`         |
| Name        | Nachname                              | `Mustermann` |
| Vorname     | Vorname                               | `Max`        |
| Geburtsjahr | Geburtsjahr (4-stellig)               | `2012`       |
| Profil      | Sportprofil (`True`/`False`)          | `False`      |

---

## Web-App Nutzung

### Login-Typen

| Typ     | Authentifizierung       | Zugriff                        |
|---------|-------------------------|--------------------------------|
| Station | 6-stelliger PIN         | Ergebnis-Erfassung             |
| Admin   | Admin-Passwort          | Dashboard, PIN-Verwaltung, DB  |

### Station-Login

1. Disziplin auswählen
2. PIN eingeben (vom Admin bereitgestellt)
3. Ergebnisse erfassen

### Admin-Dashboard

- **PIN-Verwaltung**: PINs generieren/widerrufen
- **DB-Upload**: Neue Datenbank hochladen
- **Session-Übersicht**: Aktive Geräte einsehen
- **Disziplin-Konfiguration**: Disziplinen verwalten
- **Fortschritts-Dashboard**: Riegen-Übersicht

---

## Disziplin-Konfiguration

Disziplinen können im Admin-Bereich verwaltet werden:

| Einstellung        | Beschreibung                            |
|--------------------|----------------------------------------|
| Name               | Frei benennbar (z.B. "Sprint 50m")     |
| Format             | `time` (mm:ss) oder `distance` (Meter) |
| Anzahl Runden      | 1-3 Versuche pro Schüler               |

### API-Endpunkte

- `GET /admin/disziplinen` – Disziplin-Übersicht
- `POST /admin/disziplinen` – Disziplin erstellen
- `PUT /admin/disziplinen/<id>` – Disziplin bearbeiten
- `DELETE /admin/disziplinen/<id>` – Disziplin löschen
- `GET /admin/disziplinen/export` – JSON-Export
- `POST /admin/disziplinen/import` – JSON-Import

---

## Sicherheitsfeatures

- **CSRF-Schutz**: Flask-WTF für alle Formulare
- **Rate-Limiting**: Brute-Force-Schutz für Logins
- **Geräte-Bindung**: PIN nur auf einem Gerät aktiv
- **Session-Verwaltung**: Admin kann Sessions widerrufen
- **Automatische Backups**: Vor DB-Upload + regelmäßig

---


## Deployment & Umgebungen

- `ENV`/`FLASK_ENV` steuert die Config-Klasse (`development`, `production`, `testing`)
- `.env` enthält Secrets/DB-Pfad; in Prod `DEBUG=False`, `SESSION_COOKIE_SECURE=True` setzen
- `DB_PATH` konfiguriert die DB, Uploads/Backups laufen mit SameSite+HttpOnly-Cookies

### Entwicklung

```bash
cd alles_neu
ENV=development python main.py
# oder via Skript:
./scripts/start_dev.sh
```

### Produktion (Gunicorn)

```bash
cd alles_neu
ENV=production HOST=0.0.0.0 PORT=5000 WORKERS=4 TIMEOUT=120 ./scripts/start_prod.sh
# alternativ direkt:
gunicorn -w 4 -b 0.0.0.0:5000 main:app
```



### Admin-Export (Offline-DB)

```bash
cd alles_neu
./scripts/admin_export.sh --csv path/to/schueler.csv --output bjs_database_2025.db
```

### Empfohlene Einstellungen



```env
DEBUG=False
SECRET_KEY=<langer-zufälliger-schlüssel>
SESSION_COOKIE_SECURE=True  # Bei HTTPS
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_HTTPONLY=True
```

## Tests & Qualität

```bash
cd alles_neu
pip install -r requirements-dev.txt
pytest
pre-commit install
pre-commit run --all-files
```

- Lint/Format: `black`, `ruff` (Konfiguration in `pyproject.toml`)
- Git-Hygiene: `.env`, `*.db`, Test-Artefakte sind gitignored; keine DB/CSV ins Repo committen.

## Backup & Wiederherstellung

### Manuelles Backup

```python
from app.database.database import Database
db = Database()
backup_path = db.backup_to_file(label="manual")
print(f"Backup erstellt: {backup_path}")
```

### Automatische Backups

Backups werden automatisch erstellt:
- Vor jedem DB-Upload
- Konfigurierbar im Admin-Bereich (Intervall)

---

## Troubleshooting

### PIN funktioniert nicht

1. Prüfe im Admin-Dashboard, ob der PIN aktiv ist
2. Prüfe, ob der PIN bereits auf einem anderen Gerät verwendet wird
3. Widerrufe den PIN und erstelle einen neuen

### Datenbank-Fehler

1. Prüfe den DB_PATH in `.env`
2. Stelle sicher, dass die DB-Datei existiert
3. Führe ggf. einen DB-Upload durch

### Session abgelaufen

- Bei Stations-Login: Erneut mit PIN anmelden
- Bei Admin-Login: Erneut mit Passwort anmelden

---

## Lizenz

Dieses Projekt ist für den internen Schulgebrauch bestimmt.
