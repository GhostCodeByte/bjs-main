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

## Entwicklung lokal

Lokale Entwicklung bleibt absichtlich einfach. Ohne gesetztes `ENV` startet die App im Entwicklungsmodus und laesst sich weiter direkt mit `python main.py` starten.

### 1. Umgebung vorbereiten

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Optionale `.env` anlegen

```env
SECRET_KEY=lokal-dev-secret
ADMIN_PASSWORD=lokal-admin
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

## Produktion internes Netz

Die Produktionskonfiguration ist bewusst strenger als lokal. Produktion wird nur ueber `scripts/start_linux_prod.sh` gestartet.

### Voraussetzungen

- Linux-Host im internen Netz
- Python-Umgebung oder projektlokales `.venv`
- Abhaengigkeiten vorab installiert: `pip install -r requirements.txt`
- HTTPS oder Reverse Proxy empfohlen, wenn `SESSION_COOKIE_SECURE=true`

### Env-Datei

Nutze `.env.example` als Vorlage. Fuer Produktion muessen mindestens diese Werte gesetzt sein:

```env
ENV=production
SECRET_KEY=replace-with-a-long-random-secret
ADMIN_PASSWORD=replace-with-a-strong-admin-password
SESSION_COOKIE_SECURE=true
PREFERRED_URL_SCHEME=https
STATION_DEFAULT_NAME=Station
```

Wichtig:

- `SECRET_KEY=change-me` ist in Produktion verboten.
- `ADMIN_PASSWORD=admin123` ist in Produktion verboten.
- `STATION_DEFAULT_PIN` darf in Produktion nicht gesetzt sein.
- Ein Event-Login funktioniert nur, wenn ein Event-Passwort gesetzt wurde.

### Start

```bash
chmod +x scripts/start_linux_prod.sh
./scripts/start_linux_prod.sh
```

Standardbetrieb:

- `WORKERS=1`
- `THREADS=8`

Das ist absichtlich konservativ, weil SQLite mit einem Worker plus Threads fuer dieses interne Szenario robuster ist als mit mehreren Gunicorn-Prozessen.

### Datenordner

Alle produktionsrelevanten SQLite-Dateien liegen im Ordner `database/`:

- `database/bjs_meta.db`
- aktive Event-Datenbanken
- Backups der Event-Datenbanken

### Backup und Wiederherstellung

Im Standardbetrieb ist kein automatisches In-App-Backup aktiviert. Fuer den ersten Produktivbetrieb ist vorgesehen:

- manuelle Backups ueber die Admin-Funktionen
- zusaetzlich regelmaessiges Host-/Dateisystem-Backup des ganzen Ordners `database/`

Wiederherstellung:

1. Aktive Datenbank zusaetzlich sichern.
2. Gewuenschte Backup-Datei in `database/` ablegen.
3. Im Admin-Bereich hochladen oder als aktive DB auswaehlen.
4. Danach Login, Dashboard und Stationsfluss kurz pruefen.

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

## Hinweise

- Die aktive Event-Datenbank wird ueber die Meta-Datenbank verwaltet.
- Ohne aktive Event-Datenbank koennen Stations- und Event-Funktionen nicht arbeiten.
- Die Anwendung nutzt SQLite und ist damit bewusst einfach deploybar.

## Betriebsgrenzen

- Zielbild ist internes Netz, nicht oeffentliches Internet.
- SQLite ist fuer wenige gleichzeitige Geraete geeignet, aber nicht fuer hohe Parallelitaet.
- Das empfohlene Produktionsmodell ist 1 Gunicorn-Worker mit Threads.
- Fuer einen oeffentlichen Internetbetrieb waeren weitere Security- und Betriebsmaßnahmen noetig.

## Entwicklerdoku

Fuer interne Struktur, Datenfluss und Wartung:

- `README_DEV.md`
