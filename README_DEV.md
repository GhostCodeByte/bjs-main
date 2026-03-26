# Entwicklerdoku BJS Verwaltung

## Zweck

Die App verwaltet Bundesjugendspiele als Flask-Webanwendung.

Rollen:

- `Admin`
- `Station`
- `Event`

Die Anwendung arbeitet immer mit genau einer aktiven Event-Datenbank.

## Projektaufbau

### `main.py`

Startpunkt der App. Importiert `create_app()` und startet Flask.

### `app/__init__.py`

App-Factory.

Verantwortlich fuer:

- Laden der Flask-Konfiguration
- Logging
- CSRF
- Fehlerhandler
- Aufloesen der aktiven Event-Datenbank
- Registrieren der Blueprints

### `app/core/`

Technische Grundbausteine.

- `settings.py`
  Flask-Konfiguration fuer Development, Test und Produktion
- `registry.py`
  Zugriff auf die Meta-Datenbank
- `disziplinen.py`
  feste Disziplindefinitionen und UI-Texte

### `app/routes/`

HTTP-Endpunkte.

- `auth.py`
  Login, Admin-Bereich, Dashboard, Event-Seiten, Import, Export, Backups
- `input.py`
  Stations-Erfassung

### `app/services/`

Fachlogik ohne HTTP-spezifischen Code.

- `csv_import.py`
  CSV-Import in Event-Datenbanken
- `riegen.py`
  Riegenerzeugung und Namensersetzung
- `auswertung.py`
  Punkteberechnung, Gesamtwertung, Urkunden

### `app/database/database.py`

SQLite-Zugriffsschicht fuer die Event-Datenbank.

Diese Datei ist die zentrale Stelle fuer:

- Tabellenaufbau
- Migrationen
- CRUD-Zugriffe
- Auswertungsabfragen
- PIN- und Sessionlogik
- Backup-Logik

### `app/templates/` und `app/static/`

- `templates/`
  Jinja-Templates
- `static/`
  CSS und statische Dateien

## Datenbankmodell

Es gibt zwei SQLite-Ebenen.

### 1. Meta-Datenbank

Standardpfad:

- `database/bjs_meta.db`

Zweck:

- registrierte Event-Datenbanken verwalten
- aktive Event-Datenbank merken
- globale Konfigurationswerte speichern

Wichtige Tabellen:

#### `Db_Registry`

Speichert bekannte Event-Datenbanken.

Wichtige Spalten:

- `name`
- `path`
- `label`
- `year`
- `created_at`
- `file_size`
- `extra_json`

#### `App_Config`

Key-Value-Tabelle fuer globale Werte.

Wichtiger Eintrag:

- `active_db_path`

#### `Disziplinen`

Historisch als Tabelle vorhanden, fachlich aber statisch.
Die aktuell verwendeten Disziplinen kommen aus `app/core/disziplinen.py`.

### 2. Event-Datenbank

Zweck:

- alle Daten eines einzelnen Events speichern

Wichtige Tabellen:

#### `Schueler`

Stammdaten der Teilnehmer.

Wichtige Spalten:

- `SchuelerID`
- `Name`
- `Vorname`
- `Geschlecht`
- `Klasse`
- `Klassenbuchstabe`
- `Geburtsjahr`
- `Bundesjugentspielalter`
- `Profil`
- `RiegenfuehrerID`
- `Gesamtpunktzahl`
- `Urkunde`

#### `Riegenfuehrer`

Speichert Riegen und ihre Eigenschaften.

Wichtige Spalten:

- `ID`
- `Name`
- `Geschlecht`
- `Profil`
- `Stufe`
- `Klassenendungen`

#### `Schueler_Disziplin_Ergebnis`

Speichert Ergebnisse pro Schueler, Disziplin und Runde.

Wichtige Spalten:

- `ID`
- `SchuelerID`
- `Disziplin`
- `ErgebnisNR`
- `result_value`
- `status`
- `source_ipad_number`
- `source_station`
- `created_at`

Hinweis:

- dieselbe Runde kann mehrfach gespeichert werden
- fuer Auswertungen wird in der Regel der neueste Eintrag je Schueler/Disziplin/Runde verwendet

#### `Station_Pin`

PINs fuer Stations-Logins.

Wichtige Spalten:

- `station`
- `discipline`
- `pin`
- `max_logins`
- `active`

#### `Station_Session`

Aktive Geraetebindungen fuer PINs.

Wichtige Spalten:

- `pin`
- `device_id`
- `discipline`
- `active`

#### `App_Settings`

Key-Value-Tabelle pro Event-Datenbank.

Beispiel:

- Event-PIN

#### `Backup_Config` und `Backup_History`

Konfiguration und Verlauf fuer Datenbank-Backups.

## Aktive Datenbank

Die aktive Event-Datenbank wird ueber die Meta-Datenbank bestimmt.

Ablauf in `app/__init__.py`:

1. `DbRegistry` wird fuer die Meta-Datenbank erzeugt.
2. `active_db_path` wird gelesen.
3. Wenn die Datei existiert, wird sie verwendet.
4. Wenn nicht, wird die neueste Datenbank fuer das aktuelle Jahr gesucht.
5. Diese wird dann als aktiv gesetzt.

Alle Request-gebundenen Datenbankzugriffe laufen ueber `get_db()`.

## Request-Fluss

Typischer Ablauf:

1. Request trifft auf eine Route in `app/routes/`
2. Route prueft Session, Rolle und Eingaben
3. Route holt die aktive Event-Datenbank ueber `get_db()`
4. Route ruft `Database`-Methoden oder einen Service auf
5. Rueckgabe als HTML, Redirect, JSON oder Download

## Wichtige Fluesse

### CSV-Import

Beteiligte Dateien:

- `app/routes/auth.py`
- `app/services/csv_import.py`
- `app/core/registry.py`
- `app/database/database.py`

Ablauf:

1. Admin laedt CSV hoch
2. CSV wird gelesen und validiert
3. neue Event-Datenbank wird erstellt oder bestehende befuellt
4. Datenbank wird in `Db_Registry` eingetragen
5. Datenbank wird aktiv gesetzt

### Riegeneinteilung

Beteiligte Dateien:

- `app/routes/auth.py`
- `app/services/riegen.py`
- `app/database/database.py`

Ablauf:

1. vorhandene Klassen werden aus `Schueler` gelesen
2. pro Klasse werden Riegen erzeugt
3. Schueler werden ueber Klasse, Profil und Geschlecht zugeordnet
4. Platzhalternamen koennen spaeter ersetzt werden

### Stations-Login

Beteiligte Dateien:

- `app/routes/auth.py`
- `app/database/database.py`

Ablauf:

1. Login mit PIN und Disziplin
2. `claim_station_pin(...)` prueft aktive Sessions
3. PIN wird an ein Geraet gebunden
4. Rolle `station` wird in die Session geschrieben

### Ergebniserfassung

Beteiligte Dateien:

- `app/routes/input.py`
- `app/database/database.py`

Ablauf:

1. Riege wird geladen
2. Schuelerliste wird in der Session gehalten
3. Ergebnisse werden rundenweise gespeichert
4. Status und Fortschritt werden aus Session + DB berechnet

### Auswertung

Beteiligte Dateien:

- `app/services/auswertung.py`
- `app/routes/auth.py`
- `app/database/database.py`

Ablauf:

1. Auswertungskandidaten werden geladen
2. Punkte je Disziplin werden berechnet
3. niedrigste Disziplin faellt bei vier vorhandenen Werten weg
4. Gesamtpunktzahl und Urkunde werden in `Schueler` geschrieben
5. Export wird pro Klasse als CSV gebaut

## Disziplinen und Auswertung

Disziplinen sind statisch.

Quelle:

- `app/core/disziplinen.py`

Die Bewertungsparameter sind ebenfalls statisch.

Quelle:

- `app/services/auswertung.py`

Es gibt dafuer keine separate editierbare Konfigurationsdatei mehr.

## Wo Aenderungen typischerweise passieren

### Neues Feld in einer Tabelle

Datei:

- `app/database/database.py`

Zusatz:

- Migration mitdenken
- lesende und schreibende Methoden anpassen

### CSV-Import aendern

Datei:

- `app/services/csv_import.py`

### Riegenlogik aendern

Datei:

- `app/services/riegen.py`

### Punktelogik aendern

Datei:

- `app/services/auswertung.py`

### Admin- oder Event-Seite aendern

Dateien:

- `app/routes/auth.py`
- passendes Template in `app/templates/`

### Stationsseite aendern

Dateien:

- `app/routes/input.py`
- `app/templates/input.html`

## Technische Hinweise

### `auth.py` ist gross

Die Datei enthaelt einen grossen Teil der Admin- und Eventlogik.
Bei Aenderungen zuerst die konkrete Route suchen und dann die darunter aufgerufenen Hilfsfunktionen verfolgen.

### `database.py` ist zentral

Wenn unklar ist, wo Daten geschrieben oder gelesen werden, ist `app/database/database.py` meist die richtige Stelle.

### Migrationen passieren im Code

Tabellenanpassungen werden nicht ueber ein externes Migrationstool verwaltet, sondern direkt in `Database`.
Bei Struktur-Aenderungen immer bestehende `.db`-Dateien mitdenken.

## Lokale Entwicklung

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Ohne gesetztes `ENV` startet die App im Development-Modus.

## Produktionsmodus

Produktion wird ueber `ENV=production` aktiviert.

Dann greifen zusaetzliche Pruefungen, zum Beispiel fuer:

- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `SESSION_COOKIE_SECURE`
- `PREFERRED_URL_SCHEME`

## Sinnvolle Lesereihenfolge

1. `main.py`
2. `app/__init__.py`
3. `app/routes/auth.py`
4. `app/routes/input.py`
5. `app/services/`
6. `app/database/database.py`
