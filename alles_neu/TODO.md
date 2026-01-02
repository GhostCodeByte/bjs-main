# TODO – Projekt-Härtung & Fertigstellung (alles_neu)

Ziel: Funktionsgleich und besser als `old/`, mit klarer Struktur, Sicherheit, Stabilität und Betrieb.

## 1) Quick Wins (Sofort)
- [x] Logout-Route implementieren und Template-Link fixen.
- [x] Session-Logik prüfen: `is_logged_in` nicht direkt auf `False` setzen beim Laden von `/input`.
- [x] Fehlermeldungen/Validierung für Login (Disziplin Pflicht, falsches Passwort → klare Meldung).
- [x] README aktualisieren auf neue Struktur (`alles_neu`), Startbefehle, Admin-Tool, Datenfluss.
- [x] Admin-Login-Button in Auth ergänzen (führt zum Admin-Login-Flow).
- [x] Minimalen Upload-/Import-Flow für externe DB-Datei skizzieren (Endpoint + UI-Hook).

## 2) Auth & Sicherheit
- [x] Passwörter/PINs nicht hardcoden: Konfig über `.env` (Admin-PW, Station-PIN-Seeds/Counts).
- [x] CSRF-Schutz aktivieren (Flask-WTF oder `flask-wtf/csrf` Blueprint).
- [x] Station-Logins: Im Admin-Bereich Anzahl Logins pro Station festlegen; 6-stellige zufällige PINs generieren; Single-Session-Policy (keine Ablaufzeit; wenn PIN schon aktiv → Fehlermeldung); Admin kann Sessions/PINs gezielt abmelden.
- [x] Geräte-Bindung: Beim Login eindeutige Geräte-ID speichern, in DB ablegen und im Admin-Portal anzeigen; pro PIN nur eine aktive Geräte-ID zulassen.
- [x] Rate-Limiting/Brute-Force-Schutz für Logins (Admin + Station).

## 3) Datenbank & Konsistenz
- [x] Externer Admin-Workflow: DB wird offline erzeugt/exportiert (SQLite, Dateiname mit Jahr/Version).
- [x] App-Flow: Upload-/Import-Endpunkt für bereitgestellte DB (Schema muss komplett sein; Zielpfad `DB_PATH` konfigurierbar).
- [x] Kein Pfad-Dualismus: App nutzt die hochgeladene DB; Admin erzeugt nur offline (keine getrennten Live-Kopien).
- [x] Transaktionen kapseln, Fehler behandeln (Rollback bei Insert/Update).
- [x] Indizes prüfen (z. B. auf `Schueler_Disziplin_Ergebnis(SchuelerID, Disziplin, ErgebnisNR, created_at)`).
- [x] Sicherstellen: UNIQUE/Constraint-Logik gegen doppelte Riegenführer-Namen & Rundeneinträge.
- [x] Versionierung + asynchrone, regelmäßige Backups der DB; Backup-Intervall im Admin-Bereich konfigurierbar.

## 4) Admin-Tool (Kivy)
- [x] UX-Hinweise/Fehleranzeigen ergänzen (ValidationError, ErrorPopup, SuccessPopup).
- [x] Validierung der Eingaben (Stufe, Geschlecht, Profil, Klassenendungen).
- [x] CSV-Schema dokumentieren; Fehlermeldung bei falschem Header/Delimiter.
- [x] Fortschritts-/Log-Output bei Anlage von Riegen/Schülern und beim Export der DB-Datei.
- [x] Optional: Admin-Tool auch als CLI/Headless-Export für Serverbetrieb (kein Upload nötig auf demselben Gerät).

## 5) Disziplin-Konfiguration (Admin-Bereich)
- [x] Admin-Login-Flow (separate Rolle/Passwort) implementieren; Auth-View um Admin-Login-Button erweitern.
- [x] CRUD für Disziplinen (Name frei benennbar; aktiv/inaktiv nicht nötig).
- [x] Pro Disziplin konfigurierbar: Ergebnis-Format Zeit `mm:ss` (Sekunden ≤ 60), Distanz `m`; Anzahl Ergebnisse/Runden frei setzbar.
- [x] Validierungsschemata hinterlegen (Zeiten/Distanz) und im Input-Flow nutzen. *(Basis-Validierung in `_validate_and_normalize_result` vorhanden)*
- [x] Speicherung in DB (Tabellen z. B. `Disziplinen`, `Disziplin_Config`, Versions-/Änderungsmetadaten).
- [x] Import/Export der Disziplin-Konfiguration (JSON/CSV) analog zur DB-Upload-Strategie.
- [x] Rollen-/Zugriffsschutz für diesen Bereich (nur Admin). *(Admin-Dashboard mit `_require_admin()` geschützt)*

## 6) Erfassungs-Flow (Input)
- [x] Abwesend-Button mit Route + DB-Status (`status='ABWESEND'`) verdrahten; abwesende Schüler im Dropdown automatisch überspringen (nicht entfernen); Abwesenheit disziplinspezifisch (pro Disziplin neu setzen).
- [x] Ergebnis-Validierung (Formate aus Disziplin-Config; Zeit mm:ss mit Sekunden ≤ 60, Distanz m).
- [x] Riege erneut laden, obwohl fertig: Hinweis anzeigen; neue Ergebnisse anhängen (alte nicht überschreiben, beide behalten). *(Append-only-Logik in DB implementiert)*
- [x] Statuszähler (runde1/2/3, abwesend) korrekt aus DB/Session ableiten. *(via `build_status_payload` und `_compute_progress`)*

## 7) Frontend/UI
- [x] Mobile/iPad-Optimierung (Touch, große Buttons, Fokus/Enter-Flow). *(Input-Template hat große Buttons, Touch-optimiert)*
- [x] Visuelles Feedback nach Speichern (Toast/Banner). *(Toast-Notifications mit showToast(), flashSaveSuccess() implementiert)*
- [x] Dropdown-Status-String klarer (Name + ✓/✗/□), laufende Runde hervorheben; abwesende im Auto-Select überspringen. *(Symbole ✅/❌/⬜ implementiert, `findNextNonAbsentStudent` vorhanden)*
- [x] Loading/Disabled-States bei Requests (Fetch). *(setButtonLoading(), Loading-Overlay implementiert)*

## 8) Monitoring & Übersicht
- [x] Übersicht „Fortschritt aller Riegen" (Dashboard). *(dashboard.html mit get_all_riegen_with_progress(), Live-Aktualisierung)*
- [x] Live-Event-Login + separate Stats-Seite; optional Live-Bestenliste pro Disziplin. *(stats.html mit get_bestenliste(), Auto-Refresh alle 30s)*

## 9) Tests & Qualität
- [x] Unit-Tests für DB-Layer (add_entry, get_rounds_done, Riegen-Logik, Disziplin-Config, Station-PIN-Logik). *(pytest: `tests/conftest.py`, `tests/test_database.py`)*
- [x] Integrationstests für Login → Get Riege → next_student → Abwesend; Admin-Login → Disziplin-CRUD → Validierung im Input. *(`tests/test_integration.py`)*
- [x] Lint/Format (black/ruff) und Pre-commit-Hooks. *(`pyproject.toml`, `.pre-commit-config.yaml`, `requirements-dev.txt`)*

## 10) Deployment/Betrieb
- [x] Konfig via ENV (.env.example pflegen): SECRET_KEY, DB_PATH (Upload-Ziel), ADMIN_PW, Station-PIN-Parametrisierung, DEBUG. *(.env vorhanden, App liest aus ENV)*
- [x] Dev/Prod-Konfig trennen (Debug nur lokal); HTTPS nicht zwingend, aber Session-Flags sinnvoll setzen. *(config.py mit Dev/Prod/Test Klassen)*
- [x] Start-Skripte/Dokumentation (Flask, externer Admin-Export, Upload/Import in App, Station-PIN-Generierung/Verteilung). *(`scripts/start_dev.sh`, `scripts/start_prod.sh`, `scripts/admin_export.sh`, README aktualisiert)*
- [x] Sicherstellen: keine sensiblen Dateien im Repo (DB/CSV optional gitignored); Upload-Speicherort mit restriktiven Rechten; Versionierung + regelmäßige Backups (asynchron). *(`.gitignore` erweitert; Backup-Handling bereits integriert)*

## 11) Migration von `old/`
- [x] Vergleiche `old/todo.txt` mit obiger Liste; offene Punkte übertragen/abhaken. *(Abgleich durchgeführt; offene Punkte übernommen)*
- [x] Prüfe, ob alte Features (Abwesenheit, Markierungen, Fortschrittslogik) vollständig in `alles_neu` sind. *(Funktionalität in neuen Flows vorhanden)*
- [x] Entferne obsolet gewordene Duplikate, nachdem Funktionalität verifiziert ist. *(Alte Duplikate als obsolet markiert/entfernt, Fokus auf `alles_neu`)*
- [x] De-scoped: Legacy-Punkte aus `old/todo.txt` (z. B. „Ausgabe-/Export-Ansicht (PDF-Urkunden?)“, „Schwierigkeitsgrad berechnen“) vorerst nicht übernommen.
---

## Fortschritts-Zusammenfassung

| Bereich                     | Erledigt | Offen | Status       |
|-----------------------------|----------|-------|--------------|
| 1) Quick Wins               | 6        | 0     | ✅ Fertig     |
| 2) Auth & Sicherheit        | 5        | 0     | ✅ Fertig     |
| 3) Datenbank & Konsistenz   | 7        | 0     | ✅ Fertig     |
| 4) Admin-Tool (Kivy)        | 5        | 0     | ✅ Fertig     |
| 5) Disziplin-Konfiguration  | 7        | 0     | ✅ Fertig     |
| 6) Erfassungs-Flow          | 4        | 0     | ✅ Fertig     |
| 7) Frontend/UI              | 4        | 0     | ✅ Fertig     |
| 8) Monitoring & Übersicht   | 2        | 0     | ✅ Fertig     |
| 9) Tests & Qualität         | 3        | 0     | ✅ Fertig     |
| 10) Deployment/Betrieb      | 4        | 0     | ✅ Fertig     |
| 11) Migration von `old/`    | 3        | 0     | ✅ Fertig     |
| 12) Fachfragen              | 0        | 1     | 🔴 Offen      |

**Gesamt: 51 erledigt, 0 offen**

*Zuletzt aktualisiert: nach Implementierung Punkt 9-11*

---

## Neu implementierte Features (Zusammenfassung)

### README.md
- Vollständige Dokumentation der neuen Struktur
- Startbefehle für Flask-App und Admin-Tool
- CSV-Format-Dokumentation
- Datenfluss-Diagramm
- Deployment-Anleitung

### Datenbank (database.py)
- `Disziplinen` und `Disziplin_Config` Tabellen
- `Backup_Config` und `Backup_History` Tabellen
- CRUD-Methoden für Disziplinen
- `get_all_riegen_with_progress()` für Dashboard
- `get_bestenliste()` für Live-Rangliste
- `get_stats()` für Statistiken
- Automatische Backup-Versionierung mit Thread

### Admin-Routen (auth.py)
- `/admin/disziplinen` - Disziplin-Verwaltung
- `/admin/disziplinen/create`, `/update`, `/delete` - CRUD API
- `/admin/disziplinen/export`, `/import` - JSON Im-/Export
- `/dashboard` - Fortschritts-Übersicht
- `/stats` - Statistiken & Bestenliste
- `/admin/backup` - Backup-Verwaltung

### Templates
- `admin_disziplinen.html` - Disziplin-CRUD UI
- `dashboard.html` - Riegen-Fortschritt mit Live-Updates
- `stats.html` - Bestenliste mit Filterung
- `admin_dashboard.html` - Erweitert mit Stats, Backup-Config
- `auth.html` - Dynamische Disziplinen, Loading-States
- `input.html` - Toast-Notifications, Loading-Overlay

### CSS (input.css)
- Toast-Notification System
- Loading-Overlay und Spinner
- Button Loading States
- Visual Feedback Animationen
- Progress-Bar Styling
- Mobile-Optimierung

### Admin-Tool (Kivy)
- `admin.py` - Erweitert mit Validierung, LogPopup, Error/Success Popups
- `cli.py` - Headless CLI für CSV-Import, Riegen-Erstellung, DB-Export
