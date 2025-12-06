# TODO – Projekt-Härtung & Fertigstellung (alles_neu)

Ziel: Funktionsgleich und besser als `old/`, mit klarer Struktur, Sicherheit, Stabilität und Betrieb.

## 1) Quick Wins (Sofort)
- [ ] Logout-Route implementieren und Template-Link fixen.
- [ ] Session-Logik prüfen: `is_logged_in` nicht direkt auf `False` setzen beim Laden von `/input`.
- [ ] Fehlermeldungen/Validierung für Login (Disziplin Pflicht, falsches Passwort → klare Meldung).
- [ ] README aktualisieren auf neue Struktur (`alles_neu`), Startbefehle, Admin-Tool, Datenfluss.
- [ ] Admin-Login-Button in Auth ergänzen (führt zum Admin-Login-Flow).
- [ ] Minimalen Upload-/Import-Flow für externe DB-Datei skizzieren (Endpoint + UI-Hook).

## 2) Auth & Sicherheit
- [ ] Passwörter/PINs nicht hardcoden: Konfig über `.env` (Admin-PW, Station-PIN-Seeds/Counts).
- [ ] CSRF-Schutz aktivieren (Flask-WTF oder `flask-wtf/csrf` Blueprint).
- [ ] Station-Logins: Im Admin-Bereich Anzahl Logins pro Station festlegen; 6-stellige zufällige PINs generieren; Single-Session-Policy (keine Ablaufzeit; wenn PIN schon aktiv → Fehlermeldung); Admin kann Sessions/PINs gezielt abmelden.
- [ ] Geräte-Bindung: Beim Login eindeutige Geräte-ID speichern, in DB ablegen und im Admin-Portal anzeigen; pro PIN nur eine aktive Geräte-ID zulassen.
- [ ] Rate-Limiting/Brute-Force-Schutz für Logins (Admin + Station).

## 3) Datenbank & Konsistenz
- [ ] Externer Admin-Workflow: DB wird offline erzeugt/exportiert (SQLite, Dateiname mit Jahr/Version).
- [ ] App-Flow: Upload-/Import-Endpunkt für bereitgestellte DB (Schema muss komplett sein; Zielpfad `DB_PATH` konfigurierbar).
- [ ] Kein Pfad-Dualismus: App nutzt die hochgeladene DB; Admin erzeugt nur offline (keine getrennten Live-Kopien).
- [ ] Transaktionen kapseln, Fehler behandeln (Rollback bei Insert/Update).
- [ ] Indizes prüfen (z. B. auf `Schueler_Disziplin_Ergebnis(SchuelerID, Disziplin, ErgebnisNR, created_at)`).
- [ ] Sicherstellen: UNIQUE/Constraint-Logik gegen doppelte Riegenführer-Namen & Rundeneinträge.
- [ ] Versionierung + asynchrone, regelmäßige Backups der DB; Backup-Intervall im Admin-Bereich konfigurierbar.

## 4) Admin-Tool (Kivy)
- [ ] UX-Hinweise/Fehleranzeigen ergänzen (CSV-Import, Riegenanlage, Export-Status).
- [ ] Validierung der Eingaben (Stufe, Geschlecht, Profil, Klassenendungen).
- [ ] CSV-Schema dokumentieren; Fehlermeldung bei falschem Header/Delimiter.
- [ ] Fortschritts-/Log-Output bei Anlage von Riegen/Schülern und beim Export der DB-Datei.
- [ ] Optional: Admin-Tool auch als CLI/Headless-Export für Serverbetrieb (kein Upload nötig auf demselben Gerät).

## 5) Disziplin-Konfiguration (Admin-Bereich)
- [ ] Admin-Login-Flow (separate Rolle/Passwort) implementieren; Auth-View um Admin-Login-Button erweitern.
- [ ] CRUD für Disziplinen (Name frei benennbar; aktiv/inaktiv nicht nötig).
- [ ] Pro Disziplin konfigurierbar: Ergebnis-Format Zeit `mm:ss` (Sekunden ≤ 60), Distanz `m`; Anzahl Ergebnisse/Runden frei setzbar.
- [ ] Validierungsschemata hinterlegen (Zeiten/Distanz) und im Input-Flow nutzen.
- [ ] Speicherung in DB (Tabellen z. B. `Disziplinen`, `Disziplin_Config`, Versions-/Änderungsmetadaten).
- [ ] Import/Export der Disziplin-Konfiguration (JSON/CSV) analog zur DB-Upload-Strategie.
- [ ] Rollen-/Zugriffsschutz für diesen Bereich (nur Admin).

## 6) Erfassungs-Flow (Input)
- [ ] Abwesend-Button mit Route + DB-Status (`status='ABWESEND'`) verdrahten; abwesende Schüler im Dropdown automatisch überspringen (nicht entfernen); Abwesenheit disziplinspezifisch (pro Disziplin neu setzen).
- [ ] Ergebnis-Validierung (Formate aus Disziplin-Config; Zeit mm:ss mit Sekunden ≤ 60, Distanz m).
- [ ] Riege erneut laden, obwohl fertig: Hinweis anzeigen; neue Ergebnisse anhängen (alte nicht überschreiben, beide behalten).
- [ ] Statuszähler (runde1/2/3, abwesend) korrekt aus DB/Session ableiten.

## 7) Frontend/UI
- [ ] Mobile/iPad-Optimierung (Touch, große Buttons, Fokus/Enter-Flow).
- [ ] Visuelles Feedback nach Speichern (Toast/Banner).
- [ ] Dropdown-Status-String klarer (Name + ✓/✗/□), laufende Runde hervorheben; abwesende im Auto-Select überspringen.
- [ ] Loading/Disabled-States bei Requests (Fetch).

## 8) Monitoring & Übersicht
- [ ] Übersicht „Fortschritt aller Riegen“ (Dashboard).
- [ ] Live-Event-Login + separate Stats-Seite; optional Live-Bestenliste pro Disziplin.

## 9) Tests & Qualität
- [ ] Unit-Tests für DB-Layer (add_entry, get_rounds_done, Riegen-Logik, Disziplin-Config, Station-PIN-Logik).
- [ ] Integrationstests für Login → Get Riege → next_student → Abwesend; Admin-Login → Disziplin-CRUD → Validierung im Input.
- [ ] Lint/Format (black/ruff) und Pre-commit-Hooks.

## 10) Deployment/Betrieb
- [ ] Konfig via ENV (.env.example pflegen): SECRET_KEY, DB_PATH (Upload-Ziel), ADMIN_PW, Station-PIN-Parametrisierung, DEBUG.
- [ ] Dev/Prod-Konfig trennen (Debug nur lokal); HTTPS nicht zwingend, aber Session-Flags sinnvoll setzen.
- [ ] Start-Skripte/Dokumentation (Flask, externer Admin-Export, Upload/Import in App, Station-PIN-Generierung/Verteilung).
- [ ] Sicherstellen: keine sensiblen Dateien im Repo (DB/CSV optional gitignored); Upload-Speicherort mit restriktiven Rechten; Versionierung + regelmäßige Backups (asynchron).

## 11) Migration von `old/`
- [ ] Vergleiche `old/todo.txt` mit obiger Liste; offene Punkte übertragen/abhaken.
- [ ] Prüfe, ob alte Features (Abwesenheit, Markierungen, Fortschrittslogik) vollständig in `alles_neu` sind.
- [ ] Entferne obsolet gewordene Duplikate, nachdem Funktionalität verifiziert ist.

## 12) Offene Fachfragen (klären)
- [ ] Live-Bestenliste erwünscht?
