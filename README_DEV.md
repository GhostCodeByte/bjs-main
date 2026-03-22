# Entwicklerdoku BJS Verwaltung

## Ueberblick

Die Codebase ist eine Flask-Anwendung mit SQLite als Laufzeitdatenbank. Fachlich gibt es zwei Ebenen:

- eine Meta-Datenbank fuer globale Konfiguration wie aktive Event-Datenbank und Disziplinen
- eine aktive Event-Datenbank fuer Schueler, Riegen, Ergebnisse, PINs, Sessions und Backups

Die Web-App arbeitet immer nur mit genau einer aktiven Event-Datenbank gleichzeitig.

## Projektstruktur

```text
bjs-main/
|-- app/
|   |-- __init__.py
|   |-- db_registry.py
|   |-- services_csv_import.py
|   |-- services_riegen.py
|   |-- database/
|   |   `-- database.py
|   |-- routes/
|   |   |-- auth.py
|   |   `-- input.py
|   |-- templates/
|   |   |-- admin_dashboard.html
|   |   |-- admin_disziplinen.html
|   |   |-- admin_riegeneinteilung.html
|   |   |-- auth.html
|   |   |-- dashboard.html
|   |   |-- input.html
|   |   `-- stats.html
|   `-- static/
|       |-- auth.css
|       `-- input.css
|-- database/
|-- scripts/
|   `-- start_linux_prod.sh
|-- config.py
|-- main.py
|-- readme.md
|-- README_DEV.md
|-- requirements.txt
`-- show_results.py
```

## Laufzeitarchitektur

### 1. App-Factory

`app/__init__.py` baut die Flask-App, laedt die Konfiguration, registriert Blueprints und stellt `get_db()` bereit. Die Datenbankverbindung wird pro Request im Flask-Kontext gecacht und am Request-Ende geschlossen.

### 2. Meta-Datenbank

`app/db_registry.py` verwaltet:

- registrierte Event-Datenbanken
- Pfad der aktiven Event-Datenbank
- globale Disziplinen

Standardpfad:

```text
alles_neu/app/database/bjs_meta.db
```

### 3. Event-Datenbank

`app/database/database.py` kapselt:

- Schueler
- Riegenfuehrer
- Ergebniszeilen
- Stations-PINs
- Stations-Sessions
- App-Einstellungen
- Backup-Konfiguration und Backup-Historie

## Wichtige Datenfluesse

### CSV-Import

1. Upload in `auth.py`
2. Importlogik in `services_csv_import.py`
3. neue SQLite-Datei wird erzeugt
4. Registry-Eintrag wird angelegt
5. neue Datenbank wird aktiv gesetzt
6. automatische Riegenerstellung wird gestartet

### Riegeneinteilung

`services_riegen.py` erzeugt Riegen regelbasiert:

- pro Klasse eine Profil-Riege, falls Profil-Schueler vorhanden sind
- pro Klasse je eine Riege fuer `m` und `w` bei Nicht-Profil
- Namen kommen aus CSV oder werden als Platzhalter `Riegenfuehrer N` erzeugt

### Stations-Erfassung

1. Login ueber `auth.py`
2. PIN wird ueber `Database.claim_station_pin()` an ein Geraet gebunden
3. `input.py` laedt eine Riege
4. Ergebnisse werden rundenweise ueber `Database.add_entry()` gespeichert
5. Statusliste und Fortschritt werden aus Session und DB zusammengesetzt

### Dashboard und Event-Uebersicht

`auth.py` rendert:

- Admin-Dashboard
- allgemeines Dashboard
- Event-Uebersicht
- Statistikseite

Die Fortschrittszahlen stammen groesstenteils aus `Database.get_all_riegen_with_progress()` und `Database.get_stats()`.

## Entwickler-Insides

- `get_db()` verwendet bewusst nur die aktive Datenbank aus der Registry. Es gibt keinen stillen Fallback.
- Die Station ist fachlich eng an die Disziplin gekoppelt. Deshalb werden Stationslisten aus den globalen Disziplinen gebaut.
- Die Session enthaelt bei Stations-Workflows einen Cache der aktuellen Schuelerliste. Das reduziert Roundtrips fuer die UI, muss aber nach jedem Speichern wieder mit der DB abgeglichen werden.
- `add_entry()` ist der fachlich kritische Punkt fuer die Ergebniserfassung. Aenderungen dort immer gegen echte Mehrfachrunden pruefen.
- `claim_station_pin()` laesst absichtlich keine harte Disziplin-Gleichheitspruefung auf dem PIN zu, damit Standard-PINs nicht unbrauchbar werden.
- Backups laufen in derselben Event-Datenbanklogik mit Historie und optionalem Hintergrundthread.

## Namens- und Kommentarstil

Fuer die Python-Module gilt jetzt als Richtung:

- sprechende Bezeichner
- deutsche Kommentare
- kurze deutsche Docstrings fuer Funktionen
- Kommentare nur dort, wo die Fachlogik nicht sofort offensichtlich ist

Wenn neue Dateien dazukommen, sollte dieser Stil beibehalten werden.

## Lokale Entwicklung

### Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Start

```bash
python main.py
```

### Konfiguration

Wichtige Variablen in `.env`:

- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `DB_PATH`
- `STATION_DEFAULT_NAME`
- `STATION_DEFAULT_PIN`
- `STATION_DEFAULT_MAX_LOGINS`
- `STATION_DEFAULT_PIN_LENGTH`

Hinweis:
`DB_PATH` wird in der aktuellen Web-App nicht als primaerer Laufzeitpfad genutzt, sobald die Registry eine aktive Event-Datenbank verwaltet.

## Wartungshinweise

- Vor groesseren Eingriffen an `database.py` immer auf Schema-Migrationen achten.
- Bei Aenderungen an Disziplinen sowohl Registry als auch UI-Flows pruefen.
- Bei Session- oder PIN-Aenderungen immer Login, Logout und Mehrgeraeteverhalten testen.
- Die bestehende Dokumentation beschreibt bewusst den aktuellen Ist-Zustand und nicht alte Planungen.

## Sinnvolle naechste technische Schritte

- echte Tests fuer Login, CSV-Import und Ergebniserfassung ergaenzen
- Route-Helfer aus `auth.py` weiter in Services zerlegen
- die Datenbankklasse langfristig in kleinere fachliche Module aufteilen
