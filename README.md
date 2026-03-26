# BJS Verwaltung

Web-App fuer die Bundesjugendspiele.

## Projektstruktur

Die Python-Logik ist jetzt nach Verantwortung getrennt:

- `app/core/`
  Konfiguration, Registry und statische Disziplin-Definitionen
- `app/services/`
  CSV-Import, Riegenlogik und Auswertung
- `app/routes/`
  Flask-Routen fuer Admin, Event und Stations-Erfassung
- `app/database/`
  SQLite-Zugriffsschicht und Datenbankdateien

## Ablauf am Eventtag

### 1. Eventvorbereitung

1. Als Admin anmelden
2. "Neue Datenbank erstellen"
3. Schueler-CSV importieren
4. Die neue Event-Datenbank wird erstellt
5. Riegen werden automatisch eingeteilt
6. Riegenfuehrernamen per CSV hochladen
7. Die Riegenfuehrer werden automatisch einer Riege zugeteilt
8. Falls noch Riegenfuehrer fehlen:
   Riegeneinteilung -> Riegenfuehrer-CSV nochmal mit neuen Namen hochladen oder unten von Hand eintragen
9. Riegeneinteilung herunterladen:
   Riegeneinteilung -> "Riegeneinteilung herunterladen"
10. Fuer die Event-Uebersicht wird ein Event-Passwort bzw. eine Event-PIN gesetzt

### 2. Waehrend des Events

1. Fuer jedes iPad an jeder Station wird im Admin-Bereich eine PIN erstellt
2. Der Schueler an der jeweiligen Station meldet sich an; jede PIN wird fuer eine spezielle Disziplin erstellt und kann sich auch nur dafuer anmelden
3. Jede Riege wird durch den jeweiligen Riegenfuehrer repraesentiert
4. Wenn eine Riege an eine Station kommt, wird der Riegenfuehrer ausgewaehlt und die Liste der Schueler erscheint
5. Die Schueler machen der Reihe nach die Disziplin, und die Ergebnisse werden fuer alle eingetragen

### 3. Nach dem Event

1. Der Admin meldet sich wieder an
2. Erstellt einen Export von allen Ergebnissen, Punkten etc.
3. Die Datenbank kann danach geloescht werden, muss aber nicht, und kann auch einfach aufbewahrt werden

## Anmeldungen

### Admin

- Fuer Import, Riegen, PINs, Datenbankverwaltung und Export
- Anmeldung mit einer festgelegten PIN nur fuer Organisatoren

### Station

- Login mit PIN + Disziplin
- Erfasst Ergebnisse nur fuer diese Disziplin
- Jede PIN kann immer nur an einem iPad aktiv sein, damit nicht Ergebnisse von anderen eingetragen werden koennen

### Event

- Eigener Login fuer die Uebersicht

## Disziplinen

- Die Disziplinen sind mit den originalen Formeln und Rechnungsfaktoren fest im Code hinterlegt
- Weitere Informationen sind im Admin-Bereich unter "Auswertung"

## Import

### Schueler-CSV

Pflichtspalten:

- `Geschlecht`
- `Klasse`
- `Name`
- `Vorname`
- `Geburtsjahr`
- `Profil`

Beispiel:

```csv
Geschlecht;Klasse;Name;Vorname;Geburtsjahr;Profil
m;5a;Mustermann;Max;2012;False
w;5a;Musterfrau;Mia;2012;True
```

### Riegenfuehrer-CSV

Pflichtspalten:

- `Name`

Beispiel:

```csv
Name
Emil
Jan
```

## Export

Beim Export wird eine ZIP-Datei erstellt, in der fuer jede Klassenstufe ein Ordner ist. Darin befindet sich fuer jede Klasse eine CSV mit allen Ergebnissen.
