# BJS Verwaltung

Webanwendung zur Verwaltung von Bundesjugendspielen mit Fokus auf:

- Import von Schuelerdaten aus CSV
- automatische Riegeneinteilung
- Stations-Login per PIN
- Ergebniserfassung pro Disziplin
- Dashboard, Bestenlisten und einfache Event-Statistiken

## Ziel des Projekts

Die Anwendung dient dazu, einen Sporttag oder Bundesjugendspiele digital zu begleiten. Eine Administration importiert zuerst die Schuelerdaten und aktiviert eine Event-Datenbank. Danach koennen Stationen per PIN Ergebnisse erfassen, waehrend Event- oder Admin-Nutzer den Fortschritt live einsehen.

## Funktionen

- CSV-Import in eine neue SQLite-Datenbank
- automatische Erstellung von Riegen mit Platzhalternamen
- nachtraegliches Ersetzen der Platzhalternamen per CSV
- globale Disziplinverwaltung mit Format und Rundenzahl
- Stations-PINs fuer die Ergebniserfassung
- Event-Zugang fuer Uebersicht und Bestenlisten
- Backups der aktiven Datenbank

## Schnellstart

### 1. Umgebung vorbereiten

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Optionale `.env` anlegen

```env
SECRET_KEY=bitte-aendern
ADMIN_PASSWORD=admin123
STATION_DEFAULT_NAME=Station
STATION_DEFAULT_PIN=123456
STATION_DEFAULT_MAX_LOGINS=1
STATION_DEFAULT_PIN_LENGTH=6
```

### 3. Anwendung starten

```bash
python main.py
```

Standardadresse:

```text
http://127.0.0.1:5000
```

## Typischer Ablauf

1. Admin meldet sich an.
2. CSV mit Schuelerdaten wird importiert.
3. Die neue Event-Datenbank wird automatisch aktiviert.
4. Riegen werden erzeugt und bei Bedarf mit echten Namen versehen.
5. Disziplinen werden gepflegt.
6. Fuer Stationen werden PINs generiert.
7. Stationen erfassen Ergebnisse.
8. Event-Ansichten zeigen Fortschritt und Bestenlisten.

## CSV-Format fuer Schueler

Pflichtspalten:

- `Geschlecht`
- `Klasse`
- `Name`
- `Vorname`
- `Geburtsjahr`

Optionale Spalte:

- `Profil`

Beispiel:

```csv
Geschlecht;Klasse;Name;Vorname;Geburtsjahr;Profil
m;5a;Mustermann;Max;2012;False
w;5a;Musterfrau;Mia;2012;True
```

## Rollen in der Anwendung

- `Admin`: Datenbanken, PINs, Disziplinen, Import, Riegenverwaltung
- `Event`: Dashboard, Event-Uebersicht, Bestenlisten
- `Station`: Ergebniserfassung fuer eine Disziplin

## Wichtige Dateien

- `main.py`: Startpunkt der Flask-Anwendung
- `config.py`: Konfiguration ueber Umgebungsvariablen
- `app/routes/auth.py`: Login, Admin, Event, Dashboard
- `app/routes/input.py`: Stations-Erfassung
- `app/database/database.py`: SQLite-Zugriffsschicht
- `app/services_csv_import.py`: CSV-Import
- `app/services_riegen.py`: Riegenerzeugung und Namensersetzung
- `show_results.py`: kleines CLI-Hilfsskript fuer letzte Ergebnisse

## Hilfsskript

Letzte Ergebnisse aus einer Datenbank anzeigen:

```bash
python show_results.py database\\BJS_2026_1.db
```

## Hinweise

- Die aktive Event-Datenbank wird ueber die Meta-Datenbank verwaltet.
- Ohne aktive Event-Datenbank koennen Stations- und Event-Funktionen nicht arbeiten.
- Die Anwendung nutzt SQLite und ist damit bewusst einfach deploybar.

## Entwicklerdoku

Fuer interne Struktur, Datenfluss und Wartung:

- `README_DEV.md`
