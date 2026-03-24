# Entwicklerdoku BJS Verwaltung

## Architektur in kurz

Die App besteht aus zwei SQLite-Ebenen:

- `database/bjs_meta.db`
  speichert aktive Event-DB und globale Disziplinen
- aktive Event-Datenbank
  speichert Schueler, Riegen, Ergebnisse, PINs, Sessions und Backups

Die Web-App arbeitet immer nur mit genau einer aktiven Event-Datenbank gleichzeitig.

## Wichtige Dateien

- `app/__init__.py`
  App-Factory, Logging, CSRF, Fehlerhandler, `get_db()`
- `app/db_registry.py`
  Meta-DB fuer aktive Event-DB und Disziplinen
- `app/database/database.py`
  SQLite-Zugriff fuer Event-Daten
- `app/routes/auth.py`
  Login, Admin, Event, Dashboard, Import, Backups
- `app/routes/input.py`
  Stations-Erfassung
- `app/services_csv_import.py`
  CSV-Import in neue Event-DB
- `app/services_riegen.py`
  Riegenerzeugung und Namensersetzung

## Fachlicher Ablauf im Code

### Import

1. CSV kommt ueber `auth.py`
2. `services_csv_import.py` erzeugt eine neue Event-DB
3. `db_registry.py` registriert sie
4. die DB wird aktiv gesetzt
5. danach startet die Riegenerzeugung

### Stations-Login

1. Login mit `PIN + Disziplin`
2. `Database.claim_station_pin()` bindet den PIN an ein Geraet
3. `input.py` laedt eine Riege
4. Ergebnisse werden ueber `Database.add_entry()` gespeichert

### Event-Ansichten

- Dashboard und Bestenlisten laufen ueber `auth.py`
- Disziplinfilter und Ergebnisformat kommen aus der Meta-DB

## Lokale Entwicklung

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Ohne gesetztes `ENV` startet die App im Development-Modus.

## Produktion intern

- Produktion nur ueber `scripts/start_linux_prod.sh`
- harte Konfigurationspruefungen nur bei `ENV=production`
- unsichere Defaults blockieren den Produktionsstart
- Standardziel: internes Netz, SQLite, 1 Gunicorn-Worker mit Threads

## Wartungshinweise

- Bei Aenderungen an `database.py` immer auf Migrationen achten.
- Bei Aenderungen an Disziplinen sowohl Meta-DB als auch UI-Flows pruefen.
- Bei Session-/PIN-Aenderungen immer Login, Logout und Mehrgeraeteverhalten testen.
- Auto-Backups existieren im Code, gehoeren aber derzeit nicht zum Standard-Produktivbetrieb.
