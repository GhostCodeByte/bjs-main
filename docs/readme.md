# BJS Verwaltung

Web-App für die Bundesjugendspiele

## Ablauf am Eventtag

### 1. Vor dem Event

1. Anmelden als Admin.
![[admin login.png]]

2. "Neue Datenbank erstellen"
3. Schüler CSV importieren
4. Die neue Event-Datenbank wird erstellt.
5. Riegen werden erstellt.
6. Riegenführernamen per CSV hochladen.
	Riegenführer CSV Import -> Datei auswählen -> Import starten
7. Riegen überprüfen.
	alle Riegen mit eigenen Riegenführer?
8. Disziplinen überprüfen.
	Oben rechts "Disziplinen" -> Disziplinen erstellen, bearbeiten oder löschen falls Nötig
9. Fuer Disziplinen werden Stations-PINs erzeugt.
10. Fuer die Event-Uebersicht wird ein Event-Passwort bzw. Event-PIN gesetzt.

### 2. Waehren des Events

1. Eine Station meldet sich mit PIN und Disziplin an.
2. Die Station waehlt eine Riege.
3. Ergebnisse werden rundenweise erfasst oder auf abwesend gesetzt.
4. Event- oder Admin-Logins sehen parallel Fortschritt, Riegenstatus und Bestenlisten.

### 3. Nach dem Event

1. Admin kann Backups erzeugen.
2. Die aktive Datenbank bleibt in `database/`.
3. Eine Backup-DB kann spaeter wieder hochgeladen oder erneut aktiviert werden.

## Anmeldungen

### Admin

- fuer Import, Disziplinen, Riegen, PINs, Backups und Datenbankauswahl

### Station

- Login mit `PIN + Disziplin`
- erfasst Ergebnisse nur fuer diese Disziplin

### Event

- eigener Login fuer Uebersicht und Bestenlisten
- kein Bearbeiten von Stammdaten

## Disziplinen

Disziplinen werden global gepflegt und bestimmen:

- den Namen im Login
- das Ergebnisformat (`time` oder `distance`)
- die Anzahl der Runden

Stations-Logins orientieren sich direkt an diesen Disziplinen. Es gibt also keine separate Stationsverwaltung neben den Disziplinen.

## CSV fuer Schueler

Pflichtspalten:

- `Geschlecht`
- `Klasse`
- `Name`
- `Vorname`
- `Geburtsjahr`

Optional:

- `Profil`

Beispiel:

```csv
Geschlecht;Klasse;Name;Vorname;Geburtsjahr;Profil
m;5a;Mustermann;Max;2012;False
w;5a;Musterfrau;Mia;2012;True
```

## Lokal starten

Ohne gesetztes `ENV` startet die App im Entwicklungsmodus.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Danach laeuft sie auf `http://127.0.0.1:5000`.

## Produktion internes Netz

Produktion soll nur ueber `scripts/start_linux_prod.sh` gestartet werden.

Wichtig:

- `SECRET_KEY=change-me` ist in Produktion verboten
- `ADMIN_PASSWORD=admin123` ist in Produktion verboten
- `STATION_DEFAULT_PIN` darf in Produktion nicht gesetzt sein
- Event-Login funktioniert nur, wenn ein Event-Passwort gesetzt wurde

Nutze `.env.example` als Vorlage und starte dann:

```bash
./scripts/start_linux_prod.sh
```

Standardbetrieb:

- `WORKERS=1`
- `THREADS=8`

Das ist absichtlich konservativ, weil SQLite mit einem Worker plus Threads fuer dieses interne Szenario robuster ist als mehrere Gunicorn-Prozesse.

## Daten und Backups

Alle SQLite-Dateien liegen in `database/`:

- `database/bjs_meta.db`
- aktive Event-Datenbanken
- erzeugte Backups

Standardempfehlung:

- manuelle Backups ueber die Admin-Funktionen
- zusaetzlich regelmaessiges Host-/Dateisystem-Backup des ganzen Ordners `database/`

## Grenzen

- Zielbild ist internes Netz, nicht oeffentliches Internet
- SQLite ist fuer wenige gleichzeitige Geraete okay, aber nicht fuer hohe Parallelitaet
- empfohlen ist 1 Gunicorn-Worker mit Threads

## Entwicklerdoku

Technischer Aufbau und interne Hinweise stehen in `README_DEV.md`.
**
