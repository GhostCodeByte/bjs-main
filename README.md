# BJS Verwaltung

Web-App für die Bundesjugendspiele

## Ablauf am Eventtag

### 1. Eventvorbereitung

1. Als Admin anmelden
2. „Neue Datenbank erstellen“
3. Schüler-CSV importieren
4. Die neue Event-Datenbank wird erstellt
5. Riegen werden automatisch eingeteilt
6. Riegenführernamen per CSV hochladen
7. Die Riegenführer werden automatisch einer Riege zugeteilt
8. Falls noch Riegenführer fehlen:
   Riegeneinteilung -> Riegenführer-CSV nochmal mit neuen Namen hochladen oder unten von Hand eintragen
9. Riegeneinteilung herunterladen:
   Riegeneinteilung -> „Riegeneinteilung herunterladen“
10. Für die Event-Übersicht wird ein Event-Passwort bzw. eine Event-PIN gesetzt

### 2. Während des Events

1. Für jedes iPad an jeder Station wird im Admin-Bereich eine PIN erstellt
2. Der Schüler an der jeweiligen Station meldet sich an; jede PIN wird für eine spezielle Disziplin erstellt und kann sich auch nur dafür anmelden
3. Jede Riege wird durch den jeweiligen Riegenführer repräsentiert
4. Wenn eine Riege an eine Station kommt, wird der Riegenführer ausgewählt und die Liste der Schüler erscheint
5. Die Schüler machen der Reihe nach die Disziplin, und die Ergebnisse werden für alle eingetragen

### 3. Nach dem Event

1. Der Admin meldet sich wieder an
2. Erstellt einen Export von allen Ergebnissen, Punkten etc.
3. Die Datenbank kann danach gelöscht werden, muss aber nicht, und kann auch einfach aufbewahrt werden

## Anmeldungen

### Admin

* Für Import, Riegen, PINs, Datenbankverwaltung und Export
* Anmeldung mit einer festgelegten PIN nur für Organisatoren

### Station

* Login mit PIN + Disziplin
* Erfasst Ergebnisse nur für diese Disziplin
* Jede PIN kann immer nur an einem iPad aktiv sein, damit nicht Ergebnisse von anderen eingetragen werden können

### Event

* Eigener Login für die Übersicht

## Disziplinen

* Die Disziplinen sind mit den originalen Formeln und Rechnungsfaktoren gespeichert
* Weitere Informationen sind im Admin-Bereich unter „Auswertung“

## Import

### Schüler-CSV

Pflichtspalten:

* `Geschlecht`
* `Klasse`
* `Name`
* `Vorname`
* `Geburtsjahr`
* `Profil`

Beispiel:

```csv
Geschlecht;Klasse;Name;Vorname;Geburtsjahr;Profil
m;5a;Mustermann;Max;2012;False
w;5a;Musterfrau;Mia;2012;True
```

### Riegenführer-CSV

Pflichtspalten:

* `Name`

Beispiel:

```csv
Name
Emil
Jan
```

## Export

Beim Export wird eine ZIP-Datei erstellt, in der für jede Klassenstufe ein Ordner ist. Darin befindet sich für jede Klasse eine CSV mit allen Ergebnissen.
