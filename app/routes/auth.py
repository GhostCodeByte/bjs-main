"""Routen fuer Login, Administration, Dashboard und Event-Ansichten."""

from collections import defaultdict
import csv
import io
import json
import logging
import re
import secrets
import sqlite3
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from app import get_db
from app.db_registry import DbRegistry, Disziplin, default_meta_db_path
from app.disziplinen_config import (
    get_disziplinen_tab_konstanten,
    get_hardcoded_disziplinen,
)
from app.services_auswertung import AuswertungService
from app.services_csv_import import (
    import_students_csv_into_db,
    import_students_csv_to_new_db,
)
from app.services_riegen import (
    auto_create_riegen_and_assign,
    parse_leader_names_csv,
    replace_placeholder_names,
)

auth_bp = Blueprint("auth", __name__, template_folder="../templates")
logger = logging.getLogger(__name__)
_PLACEHOLDER_RIEGENFUEHRER_RE = re.compile(r"^Riegenfuehrer\s*\d+$", re.IGNORECASE)

# Einfaches In-Memory-Rate-Limit pro IP und Login-Modus.
_RATE_LIMIT_BUCKETS = {}
_RATE_LIMIT_WINDOW = 300  # Sekunden
_RATE_LIMIT_MAX = 10
_DEVICE_COOKIE_NAME = "device_id"
_EVENT_PASSWORD_KEY = "event_password"


def _generate_event_pin(length: int = 6) -> str:
    """Erzeugt eine numerische Event-PIN mit erlaubten fuehrenden Nullen."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _ensure_event_pin(db) -> str | None:
    """Liefert die Event-PIN der aktiven DB und legt sie bei Bedarf automatisch an."""
    if db is None:
        return None
    event_pin = db.get_setting(_EVENT_PASSWORD_KEY, None)
    if event_pin:
        return str(event_pin).strip()

    event_pin = _generate_event_pin()
    db.set_setting(_EVENT_PASSWORD_KEY, event_pin)
    logger.info("Automatische Event-PIN fuer aktive Datenbank erstellt.")
    return event_pin


def _check_rate_limit(
    key: str, limit: int = _RATE_LIMIT_MAX, window: int = _RATE_LIMIT_WINDOW
):
    """Prueft das einfache In-Memory-Rate-Limit fuer einen Schluessel."""
    now = time.time()
    bucket = _RATE_LIMIT_BUCKETS.setdefault(key, [])
    _RATE_LIMIT_BUCKETS[key] = [ts for ts in bucket if ts > now - window]
    if len(_RATE_LIMIT_BUCKETS[key]) >= limit:
        return False
    _RATE_LIMIT_BUCKETS[key].append(now)
    return True


def _require_admin():
    """Prueft, ob die aktuelle Session Admin-Rechte hat."""
    return session.get("role") == "admin"


def _require_admin_or_event():
    """Prueft, ob die Session Admin- oder Event-Rechte hat."""
    return session.get("role") in ("admin", "event")


def _require_event():
    """Prueft, ob die aktuelle Session als Event eingeloggt ist."""
    return session.get("role") == "event"


def _disziplin_to_dict(d) -> dict:
    """Wandelt eine Disziplin in ein Dictionary fuer JSON und Templates um."""
    meta_by_name = {definition.name: definition for definition in get_hardcoded_disziplinen()}
    meta = meta_by_name.get(d.name)
    return {
        "id": d.id,
        "name": d.name,
        "format": d.format,
        "num_rounds": d.num_rounds,
        "label": meta.label if meta else d.name,
        "display_name": meta.label if meta else d.name,
        "hinweis": meta.hinweis if meta else "",
    }


def _wants_json_response() -> bool:
    """Erkennt Fetch/AJAX-Aufrufe, die JSON statt Redirect erwarten."""
    accept = (request.headers.get("Accept") or "").lower()
    return request.is_json or "application/json" in accept


def _build_empty_riegen_page_data() -> dict[str, Any]:
    """Liefert Default-Werte fuer Riegenseiten ohne aktive Datenbank."""
    return {
        "riegen": [],
        "stats": {
            "students_total": 0,
            "students_assigned": 0,
            "students_unassigned": 0,
            "riegen_total": 0,
            "profil_total": 0,
            "profil_assigned": 0,
        },
        "classes": [],
        "leader_name_stats": {
            "with_extra_leader": 0,
            "missing_extra_leader": 0,
        },
    }


def _build_riegen_page_data(db) -> dict[str, Any]:
    """Aggregiert Kennzahlen fuer Riegenverwaltung und Workflow-Modals."""
    if db is None:
        return _build_empty_riegen_page_data()

    try:
        riegen = db.get_all_riegen_with_progress()
    except Exception:
        riegen = []

    try:
        stats = db.get_riegen_stats()
        classes = db.get_present_classes()
    except Exception:
        empty = _build_empty_riegen_page_data()
        stats = empty["stats"]
        classes = empty["classes"]

    leader_name_stats = {
        "with_extra_leader": sum(
            1
            for riege in riegen
            if not _PLACEHOLDER_RIEGENFUEHRER_RE.match(
                str(riege.get("name", "") or "").strip()
            )
        ),
        "missing_extra_leader": sum(
            1
            for riege in riegen
            if _PLACEHOLDER_RIEGENFUEHRER_RE.match(
                str(riege.get("name", "") or "").strip()
            )
        ),
    }

    return {
        "riegen": riegen,
        "stats": stats,
        "classes": classes,
        "leader_name_stats": leader_name_stats,
    }


def _get_current_year_db(registry: DbRegistry):
    """Liefert die neueste registrierte Datenbank fuer das aktuelle Kalenderjahr."""
    return registry.find_latest_db_for_year(datetime.now().year)


def _get_active_event_year(registry: DbRegistry, db) -> int:
    """Leitet das Event-Jahr der aktiven Datenbank robust aus Registry oder Dateinamen ab."""
    db_path = Path(getattr(db, "db_path", "") or "")
    if db_path:
        registered = registry.get_by_name(db_path.name)
        if registered and registered.year is not None:
            return int(registered.year)
        match = re.match(r"^BJS_(\d{4})_\d+\.db$", db_path.name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return datetime.now().year


def _get_progress_num_rounds(registry: DbRegistry, disziplin: Optional[str]) -> int:
    """Liefert die Rundenzahl fuer einen Disziplinfilter, sonst den sicheren Default."""
    if not disziplin:
        return 3
    disziplin_info = registry.get_disziplin_by_name(disziplin)
    if not disziplin_info:
        return 3
    return max(int(disziplin_info.num_rounds or 0), 1)


def _resolve_assignment_genders(geschlecht: str) -> list[str]:
    """Normalisiert Riegen-Geschlecht in konkrete Zielgeschlechter fuer Zuweisungen."""
    geschlecht_text = str(geschlecht or "").strip().lower()
    if geschlecht_text in {"beide", "mw", "m+w", "m/w", "both", "m w", "m,w"}:
        return ["m", "w"]
    if geschlecht_text in {"m", "jungen", "male"}:
        return ["m"]
    if geschlecht_text in {"w", "maedchen", "mädchen", "female"}:
        return ["w"]
    return [geschlecht_text or "mw"]


def _get_existing_custom_leader_names(db) -> list[str]:
    """Liest bestehende nicht-Platzhalter-Riegenführer in stabiler Reihenfolge aus."""
    riegen = db.get_all_riegen_with_progress()
    custom_names = [
        str(riege.get("name", "")).strip()
        for riege in sorted(riegen, key=lambda eintrag: eintrag.get("id", 0))
        if str(riege.get("name", "")).strip()
        and not _PLACEHOLDER_RIEGENFUEHRER_RE.match(str(riege.get("name", "")).strip())
    ]
    return custom_names


def _format_export_result(value: Any, *, result_format: str) -> str:
    """Formatiert Ergebniswerte fuer den CSV-Export."""
    if value in (None, ""):
        return ""
    number = float(value)
    if result_format == "time":
        return f"{number:.2f}".replace(".", ",")
    return f"{number:.2f}".replace(".", ",")


def _export_auswertung_by_class(*, db, registry: DbRegistry, service: AuswertungService) -> Path:
    """Erzeugt einen Klassen-export der Auswertung als verschachtelte CSV-Ordnerstruktur."""
    referenzjahr = _get_active_event_year(registry, db)
    projektwurzel = Path(current_app.root_path).parent
    datenbank_name = Path(getattr(db, "db_path", "auswertung")).stem
    zielordner = (
        projektwurzel
        / "auswertung_exports"
        / f"{datenbank_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    zielordner.mkdir(parents=True, exist_ok=True)

    kandidaten = db.get_auswertung_candidates()
    klassen_map: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

    for schueler in kandidaten:
        breakdown = service.build_student_breakdown(
            schueler,
            referenzjahr=referenzjahr,
        )
        klasse = int(schueler.get("klasse") or 0)
        klassenbuchstabe = str(schueler.get("klassenbuchstabe") or "").strip().lower()
        klassen_map[(klasse, klassenbuchstabe)].append(
            {
                "schueler": schueler,
                "breakdown": breakdown or {},
            }
        )

    for (klasse, klassenbuchstabe), eintraege in sorted(
        klassen_map.items(),
        key=lambda item: (item[0][0], item[0][1]),
    ):
        stufenordner = zielordner / str(klasse)
        stufenordner.mkdir(parents=True, exist_ok=True)
        klassenname = f"{klasse}{klassenbuchstabe}"
        dateipfad = stufenordner / f"{klassenname}.csv"
        with dateipfad.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";")
            writer.writerow(
                [
                    "Vorname",
                    "Name",
                    "Sprint Bestes Ergebnis",
                    "Sprint Punkte",
                    "Lauf Bestes Ergebnis",
                    "Lauf Punkte",
                    "Weitsprung Bestes Ergebnis",
                    "Weitsprung Punkte",
                    "Wurf/Stoss Bestes Ergebnis",
                    "Wurf/Stoss Punkte",
                    "Gesamtpunktzahl",
                    "Urkunde",
                ]
            )

            sortierte_eintraege = sorted(
                eintraege,
                key=lambda item: (
                    str(item["schueler"].get("name") or "").lower(),
                    str(item["schueler"].get("vorname") or "").lower(),
                ),
            )
            for eintrag in sortierte_eintraege:
                schueler = eintrag["schueler"]
                breakdown = eintrag["breakdown"]
                disziplinen = breakdown.get("disziplinen", {})
                writer.writerow(
                    [
                        schueler.get("vorname", ""),
                        schueler.get("name", ""),
                        _format_export_result(
                            disziplinen.get("sprint", {}).get("best_value"),
                            result_format="time",
                        ),
                        disziplinen.get("sprint", {}).get("points", ""),
                        _format_export_result(
                            disziplinen.get("lauf", {}).get("best_value"),
                            result_format="time",
                        ),
                        disziplinen.get("lauf", {}).get("points", ""),
                        _format_export_result(
                            disziplinen.get("sprung", {}).get("best_value"),
                            result_format="distance",
                        ),
                        disziplinen.get("sprung", {}).get("points", ""),
                        _format_export_result(
                            disziplinen.get("wurf", {}).get("best_value"),
                            result_format="distance",
                        ),
                        disziplinen.get("wurf", {}).get("points", ""),
                        breakdown.get("gesamtpunktzahl", ""),
                        breakdown.get("urkunde", "") or "",
                    ]
                )

    latest_dir = projektwurzel / "auswertung_exports" / "latest"
    if latest_dir.exists() or latest_dir.is_symlink():
        shutil.rmtree(latest_dir, ignore_errors=True)
    shutil.copytree(zielordner, latest_dir)
    return zielordner


def _build_zip_from_directory(source_dir: Path) -> io.BytesIO:
    """Packt einen Exportordner rekursiv als ZIP in einen Speicherpuffer."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zip_file.write(path, arcname=path.relative_to(source_dir))
    zip_buffer.seek(0)
    return zip_buffer


def _build_event_progress_cards(
    db, disziplinen: list[dict[str, Any]]
) -> dict[str, Any]:
    """Aggregiert den Event-Fortschritt pro Disziplin ueber alle Riegen."""
    if db is None or not disziplinen:
        return {
            "summary": {
                "percent_complete": 0.0,
                "completed_slots": 0,
                "total_slots": 0,
                "active_slots": 0,
                "open_slots": 0,
            },
            "cards": [],
            "total_riegen": 0,
        }

    riegen_rows = db.cursor.execute(
        """
        SELECT r.ID, r.Name, COUNT(s.SchuelerID) AS total_schueler
        FROM Riegenfuehrer r
        LEFT JOIN Schueler s ON s.RiegenfuehrerID = r.ID
        GROUP BY r.ID, r.Name
        ORDER BY r.Name
        """
    ).fetchall()

    riegen = [
        {
            "id": row[0],
            "name": row[1],
            "total_schueler": row[2] or 0,
        }
        for row in riegen_rows
        if (row[2] or 0) > 0
    ]
    if not riegen:
        return {
            "summary": {
                "percent_complete": 0.0,
                "completed_slots": 0,
                "total_slots": 0,
                "active_slots": 0,
                "open_slots": 0,
            },
            "cards": [],
            "total_riegen": 0,
        }

    latest_rows = db.cursor.execute(
        """
        SELECT latest.SchuelerID, latest.Disziplin, COUNT(*) AS recorded_rounds
        FROM (
            SELECT e.SchuelerID, e.Disziplin, e.ErgebnisNR, e.status
            FROM Schueler_Disziplin_Ergebnis e
            INNER JOIN (
                SELECT SchuelerID, Disziplin, ErgebnisNR, MAX(ID) AS max_id
                FROM Schueler_Disziplin_Ergebnis
                GROUP BY SchuelerID, Disziplin, ErgebnisNR
            ) newest ON newest.max_id = e.ID
            WHERE e.status IN ('OK', 'ABWESEND')
        ) latest
        GROUP BY latest.SchuelerID, latest.Disziplin
        """
    ).fetchall()

    rounds_by_student_and_disziplin: dict[str, dict[int, int]] = defaultdict(dict)
    for schueler_id, disziplin_name, recorded_rounds in latest_rows:
        rounds_by_student_and_disziplin[disziplin_name][schueler_id] = recorded_rounds or 0

    schueler_rows = db.cursor.execute(
        """
        SELECT SchuelerID, RiegenfuehrerID
        FROM Schueler
        WHERE RiegenfuehrerID IS NOT NULL
        """
    ).fetchall()
    schueler_to_riege = {row[0]: row[1] for row in schueler_rows}

    riege_student_rounds: dict[str, dict[int, list[int]]] = {
        disziplin["name"]: defaultdict(list) for disziplin in disziplinen
    }
    for disziplin_name, student_rounds in rounds_by_student_and_disziplin.items():
        if disziplin_name not in riege_student_rounds:
            continue
        for schueler_id, recorded_rounds in student_rounds.items():
            riege_id = schueler_to_riege.get(schueler_id)
            if riege_id is None:
                continue
            riege_student_rounds[disziplin_name][riege_id].append(recorded_rounds)

    cards = []
    completed_slots = 0
    active_slots = 0
    open_slots = 0
    total_slots = len(riegen) * len(disziplinen)

    for disziplin in disziplinen:
        offene_riegen = 0
        aktive_riegen = 0
        fertige_riegen = 0
        num_rounds = max(int(disziplin.get("num_rounds") or 0), 1)
        riege_progress = riege_student_rounds.get(disziplin["name"], {})

        for riege in riegen:
            student_rounds = riege_progress.get(riege["id"], [])
            started_students = sum(1 for count in student_rounds if count > 0)
            completed_students = sum(1 for count in student_rounds if count >= num_rounds)

            if started_students == 0:
                offene_riegen += 1
            elif completed_students >= riege["total_schueler"]:
                fertige_riegen += 1
            else:
                aktive_riegen += 1

        percent_complete = round((fertige_riegen / len(riegen)) * 100, 1) if riegen else 0.0
        completed_slots += fertige_riegen
        active_slots += aktive_riegen
        open_slots += offene_riegen

        cards.append(
            {
                "name": disziplin["name"],
                "label": disziplin.get("display_name") or disziplin.get("label") or disziplin["name"],
                "num_rounds": num_rounds,
                "total_riegen": len(riegen),
                "offen": offene_riegen,
                "aktiv": aktive_riegen,
                "fertig": fertige_riegen,
                "percent_complete": percent_complete,
            }
        )

    return {
        "summary": {
            "percent_complete": round((completed_slots / total_slots) * 100, 1) if total_slots else 0.0,
            "completed_slots": completed_slots,
            "total_slots": total_slots,
            "active_slots": active_slots,
            "open_slots": open_slots,
        },
        "cards": cards,
        "total_riegen": len(riegen),
    }


def _get_device_id() -> str:
    """Liest oder erzeugt eine stabile Geraete-ID fuer Stations-Logins."""
    return (
        request.cookies.get(_DEVICE_COOKIE_NAME)
        or request.headers.get("X-Device-Id")
        or session.get("device_id")
        or f"device-{uuid.uuid4()}"
    )


def _get_event_password():
    """Liest das aktuell gueltige Event-Passwort aus DB oder Konfiguration."""
    db = get_db()
    if db is None:
        return current_app.config.get("EVENT_PASSWORD")
    pw = _ensure_event_pin(db)
    if pw:
        return pw
    return current_app.config.get("EVENT_PASSWORD")


def _seed_default_pin():
    """Automatische Default-PIN-Erzeugung ist deaktiviert."""
    return


@auth_bp.before_app_request
def _before_request_seed_pin():
    """Default-PINs werden nicht mehr automatisch erstellt."""
    return


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Verarbeitet den Login fuer Admin-, Event- und Stationszugriffe."""
    if request.method == "POST":
        login_mode = request.form.get("mode", "station")
        rate_key = f"{login_mode}:{request.remote_addr}"
        if not _check_rate_limit(rate_key):
            flash("Zu viele Versuche. Bitte später erneut versuchen.", "error")
            resp = make_response(render_template("auth.html"))
            resp.status_code = 429
            return resp

        password = (request.form.get("password") or "").strip()
        discipline = (request.form.get("discipline") or "").strip()

        if login_mode == "admin":
            admin_pw = current_app.config.get("ADMIN_PASSWORD", "admin123")
            if password != admin_pw:
                flash("Ungültige Admin-Zugangsdaten.", "error")
                resp = make_response(render_template("auth.html"))
                resp.status_code = 401
                return resp

            session.clear()
            session["is_logged_in"] = True
            session["role"] = "admin"
            session["admin_login_at"] = time.time()
            session.permanent = True
            flash("Admin-Login erfolgreich.", "success")
            return redirect(url_for("auth.admin_dashboard"))

        if login_mode == "event":
            event_password = str(_get_event_password() or "").strip()
            if not event_password:
                flash(
                    "Event-Zugang ist nicht eingerichtet. Bitte Event-PIN im Admin-Bereich setzen.",
                    "error",
                )
                resp = make_response(render_template("auth.html"))
                resp.status_code = 503
                return resp
            if not password:
                flash("Event-Passwort erforderlich.", "error")
                resp = make_response(render_template("auth.html"))
                resp.status_code = 401
                return resp
            if password != event_password:
                flash("Ungültiges Event-Passwort.", "error")
                resp = make_response(render_template("auth.html"))
                resp.status_code = 401
                return resp
            session.clear()
            session["is_logged_in"] = True
            session["role"] = "event"
            session["event_login_at"] = time.time()
            session.permanent = True
            flash("Event-Login erfolgreich.", "success")
            return redirect(url_for("auth.event_overview"))

        # Stations-Login erwartet immer eine konkrete Disziplin.
        if not discipline:
            flash("Bitte Disziplin auswählen.", "error")
            resp = make_response(render_template("auth.html"))
            resp.status_code = 400
            return resp
        if not password or len(password) != 6 or not password.isdigit():
            flash("PIN muss 6-stellig sein.", "error")
            resp = make_response(render_template("auth.html"))
            resp.status_code = 400
            return resp

        device_id = _get_device_id()
        pin = password
        db = get_db()
        if db is None:
            flash("Keine Datenbank vorhanden. Bitte zuerst CSV importieren.", "error")
            resp = make_response(render_template("auth.html"))
            resp.status_code = 503
            return resp
        ok, msg = db.claim_station_pin(
            pin=pin, device_id=device_id, discipline=discipline
        )
        if not ok:
            flash(msg, "error")
            resp = make_response(render_template("auth.html"))
            resp.status_code = 401
            return resp

        session.clear()
        session["is_logged_in"] = True
        session["role"] = "station"
        session["discipline"] = discipline
        session["station_pin"] = pin
        session["device_id"] = device_id
        session["station_login_at"] = time.time()
        session.permanent = True

        resp = redirect(url_for("input.input_page"))
        if not request.cookies.get(_DEVICE_COOKIE_NAME):
            resp = make_response(resp)
            resp.set_cookie(
                _DEVICE_COOKIE_NAME,
                device_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
                secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
            )
        flash("Login erfolgreich.", "success")
        return resp

    if session.get("is_logged_in"):
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("auth.admin_dashboard"))
        if role == "event":
            return redirect(url_for("auth.event_overview"))
        if role == "station":
            return redirect(url_for("input.input_page"))

    registry = _get_registry()
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]

    resp = make_response(render_template("auth.html", disziplinen=disziplinen))
    if not request.cookies.get(_DEVICE_COOKIE_NAME):
        device_id = _get_device_id()
        resp.set_cookie(
            _DEVICE_COOKIE_NAME,
            device_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
            secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        )
    return resp


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    """Meldet den aktuellen Nutzer ab und raeumt Stations-Sessions auf."""
    role = session.get("role")
    pin = session.get("station_pin")
    device_id = session.get("device_id")
    if role == "station" and pin and device_id:
        try:
            db = get_db()
            db.revoke_station_pin(pin, device_id)
        except Exception:
            pass
    session.clear()
    resp = redirect(url_for("auth.login"))
    resp.set_cookie(
        _DEVICE_COOKIE_NAME,
        "",
        expires=0,
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
    )
    flash("Abgemeldet.", "info")
    return resp


# ============================================
# Admin Dashboard
# ============================================


@auth_bp.route("/admin", methods=["GET"])
def admin_dashboard():
    """
    Admin-UI soll aufgeräumt sein:
    - Event-PIN Verwaltung
    - Stations-PIN Generierung + Verwaltung (aktiv/inaktiv, löschen)
    - Datenbank-Auswahl
    Keine Fortschritts-/Bestenlisten-Stats hier (gehört auf Event-Page).
    """
    if not _require_admin():
        return redirect(url_for("auth.login"))

    # Die Datenbankauswahl wird aus der globalen Registry geladen.
    registry = _get_registry()
    db = get_db()
    active_db = registry.get_active_db_path()
    dbs = registry.list_dbs()
    current_year_db = _get_current_year_db(registry)

    # Ohne aktive Datenbank zeigt das Dashboard nur Verwaltungsfunktionen ohne Laufzeitdaten.
    pins = []
    event_pin = None
    if db is not None:
        pins = db.cursor.execute(
            """
            SELECT id, station, discipline, pin, max_logins, active, created_at
            FROM Station_Pin
            ORDER BY created_at DESC
            """
        ).fetchall()
        event_pin = _ensure_event_pin(db)

    data = {
        "pins": [
            {
                "id": row[0],
                "station": row[1],
                "discipline": row[2],
                "pin": row[3],
                "max_logins": row[4],
                "active": bool(row[5]),
                "created_at": row[6],
            }
            for row in pins
        ],
        "event_password_set": bool(event_pin),
        "event_pin": event_pin,
        "dbs": dbs,
        "active_db_path": active_db,
        "active_db_name": Path(active_db).name if active_db else None,
        "no_database": db is None,
        "current_year_db_name": current_year_db.name if current_year_db else None,
        "has_current_year_db": current_year_db is not None,
    }

    return render_template("admin_dashboard.html", **data)


@auth_bp.route("/admin/stations", methods=["GET"])
def admin_list_stations():
    """
    Stations == Disziplinen:
    Diese Route liefert die Disziplinen als "stations" für Dropdowns (Admin UI / Login UI).
    """
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    registry = _get_registry()
    disziplinen = registry.get_disziplinen()

    stations = [
        {
            "id": d.id,
            "name": d.name,
            "display_name": _disziplin_to_dict(d)["display_name"],
            "format": d.format,
            "num_rounds": d.num_rounds,
            "active": True,
        }
        for d in disziplinen
    ]
    return jsonify({"stations": stations})


@auth_bp.route("/admin/stations", methods=["POST"])
def admin_create_station():
    """
    Stations == Disziplinen:
    Stationen werden nicht mehr separat erstellt. Bitte Disziplinen-Verwaltung nutzen.
    """
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"error": "Stationen werden über Disziplinen verwaltet."}), 410


# Stationen entsprechen fachlich den Disziplinen und werden deshalb nicht separat gepflegt.
# Änderungen laufen zentral über die Disziplinen-Verwaltung unter `/admin/disziplinen`.


@auth_bp.route("/admin/generate_pin", methods=["POST"])
def admin_generate_pin():
    """
    Generiert einen 6-stelligen Stations-PIN für eine bestehende Disziplin (Stations == Disziplinen).
    Erwartet station_id (= disziplin_id) aus Dropdown.
    """
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}

    station_id = payload.get("station_id")
    if station_id is None:
        return jsonify({"error": "station_id erforderlich"}), 400

    registry = _get_registry()
    disziplin_id = int(station_id)

    # Die PIN-Tabelle speichert Namen, deshalb wird die ID vorher aufgelöst.
    disziplin = registry.get_disziplin(disziplin_id)
    if not disziplin:
        return jsonify({"error": "Disziplin nicht gefunden"}), 404

    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503

    try:
        pin = db.generate_station_pin(
            station=disziplin.name,
            discipline=disziplin.name,
            max_logins=1,
            length=6,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Fehler: {e}"}), 500

    return jsonify(
        {
            "pin": pin,
            "station_id": disziplin_id,
            "station": disziplin.name,
            "max_logins": 1,
        }
    )


@auth_bp.route("/admin/revoke_pin", methods=["POST"])
def admin_revoke_pin():
    """Deaktiviert alle aktiven Sessions zu einem Stations-PIN."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    pin = payload.get("pin")
    if not pin:
        return jsonify({"error": "pin erforderlich"}), 400
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    revoked = db.deactivate_pin(pin)
    return jsonify({"revoked": revoked})


@auth_bp.route("/admin/pins/delete", methods=["POST"])
def admin_delete_pin():
    """Loescht einen Stations-PIN inklusive Sessions dauerhaft."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    pin = payload.get("pin")
    if not pin:
        return jsonify({"error": "pin erforderlich"}), 400
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    deleted = db.delete_pin(pin)
    return jsonify({"deleted": deleted})


@auth_bp.route("/admin/pins/deactivate", methods=["POST"])
def admin_deactivate_pin():
    """Deaktiviert einen Stations-PIN, ohne ihn aus der Datenbank zu entfernen."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    pin = payload.get("pin")
    if not pin:
        return jsonify({"error": "pin erforderlich"}), 400
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    count = db.deactivate_pin(pin)
    return jsonify({"deactivated": count})


@auth_bp.route("/admin/sessions/deactivate", methods=["POST"])
def admin_deactivate_session():
    """Deaktiviert gezielt aktive Stations-Sessions."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    count = db.deactivate_session(
        session_id=payload.get("session_id"),
        pin=payload.get("pin"),
        device_id=payload.get("device_id"),
    )
    return jsonify({"deactivated": count})


@auth_bp.route("/admin/sessions/delete", methods=["POST"])
def admin_delete_session():
    """Loescht gespeicherte Stations-Sessions."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    count = db.delete_session(
        session_id=payload.get("session_id"),
        pin=payload.get("pin"),
        device_id=payload.get("device_id"),
    )
    return jsonify({"deleted": count})


@auth_bp.route("/admin/event_password", methods=["POST"])
def admin_set_event_password():
    """
    Setzt das Event-Passwort manuell (legacy).
    """
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    password = (payload.get("password") or "").strip()
    if len(password) < 4:
        return jsonify({"error": "Passwort zu kurz"}), 400
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    db.set_setting(_EVENT_PASSWORD_KEY, password)
    return jsonify({"status": "ok"})


@auth_bp.route("/admin/event_pin/generate", methods=["POST"])
def admin_generate_event_pin():
    """
    Generiert eine neue 6-stellige Event-PIN und ersetzt die bisherige.
    """
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    # Sechs Stellen, kryptografisch zufaellig, fuehrende Nullen sind erlaubt.
    new_pin = _generate_event_pin()

    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    db.set_setting(_EVENT_PASSWORD_KEY, new_pin)
    return jsonify({"status": "ok", "event_pin": new_pin})


@auth_bp.route("/admin/backup", methods=["POST"])
def admin_backup():
    """Stoesst ein manuelles Backup der aktiven Event-Datenbank an."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    label = payload.get("label") or "manual"
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    path = db.backup_to_file(label=label, backup_type="manual")
    return jsonify({"backup_path": path})


@auth_bp.route("/admin/backup/config", methods=["PUT"])
def admin_backup_config():
    """Aktualisiert die Backup-Konfiguration der aktiven Datenbank."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    interval = payload.get("interval_minutes")
    max_backups = payload.get("max_backups")
    enabled = payload.get("enabled")
    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    db.update_backup_config(
        interval_minutes=interval, max_backups=max_backups, enabled=enabled
    )
    return jsonify({"status": "ok"})


@auth_bp.route("/admin/upload_db", methods=["POST"])
def admin_upload_db():
    """Laedt eine Datenbankdatei hoch, registriert sie und aktiviert sie."""
    if not _require_admin():
        flash("Nicht berechtigt.", "error")
        return redirect(url_for("auth.login"))

    file = request.files.get("db_file")
    if not file or file.filename == "":
        flash("Keine Datei ausgewählt.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    filename = secure_filename(file.filename or "")

    if not filename.lower().endswith(".db"):
        flash("Nur .db Dateien erlaubt.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    db = get_db()
    backup_path = None
    if db is not None:
        backup_label = request.form.get("label") or "upload"
        backup_path = db.backup_to_file(label=backup_label, backup_type="upload")

    # Hochgeladene Datenbanken landen gesammelt im Projektordner `database/`.
    registry = _get_registry()
    target_dir = Path(current_app.root_path).parent / "database"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file.save(tmp.name)
        temp_path = Path(tmp.name)

    try:
        if db is not None:
            db.close()
        shutil.move(str(temp_path), target_path)

        # Die hochgeladene Datenbank wird sofort registriert und aktiviert.
        registry.register_db(path=target_path, name=filename, label="Upload")
        registry.set_active_db_path(str(target_path))

        msg = f"DB '{filename}' hochgeladen und aktiviert."
        if backup_path:
            msg += f" Backup: {backup_path}"
        flash(msg, "success")
        logger.info("Datenbank hochgeladen und aktiviert: %s", filename)
    except Exception as exc:
        logger.exception("DB-Upload fehlgeschlagen: %s", exc)
        flash(f"Upload fehlgeschlagen: {exc}", "error")
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return redirect(url_for("auth.admin_dashboard"))


# ============================================
# Riegeneinteilung (Datenbankauswahl, CSV-Import und Riegenverwaltung)
# ============================================


def _get_registry() -> DbRegistry:
    """Erzeugt die Registry-Instanz fuer die globale Meta-Datenbank."""
    project_root = Path(current_app.root_path).parent
    return DbRegistry(default_meta_db_path(project_root))


@auth_bp.route("/admin/riegeneinteilung", methods=["GET"])
def admin_riegeneinteilung():
    """Zeigt die Verwaltungsseite fuer automatische und manuelle Riegeneinteilung."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    registry = _get_registry()
    db = get_db()
    active_db = registry.get_active_db_path()
    dbs = registry.list_dbs()
    current_year_db = _get_current_year_db(registry)
    riegen_data = _build_riegen_page_data(db)

    return render_template(
        "admin_riegeneinteilung.html",
        dbs=dbs,
        active_db_path=active_db,
        riegen=riegen_data["riegen"],
        stats=riegen_data["stats"],
        classes=riegen_data["classes"],
        leader_name_stats=riegen_data["leader_name_stats"],
        no_database=db is None,
        has_current_year_db=current_year_db is not None,
        current_year_db_name=current_year_db.name if current_year_db else None,
    )


@auth_bp.route("/admin/riegeneinteilung/download_csv", methods=["GET"])
def admin_download_riegeneinteilung_csv():
    """Laedt die aktuelle Riegeneinteilung als CSV herunter."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    db = get_db()
    if db is None:
        flash("Keine Datenbank vorhanden. Bitte zuerst CSV importieren.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    riegen = db.get_all_riegen_with_progress()
    def sort_key(riege: dict[str, Any]) -> tuple[int, str, int, str]:
        stufe = int(riege.get("stufe") or 0)
        klassen = str(riege.get("klassenendungen") or "").strip().lower()
        geschlecht = str(riege.get("geschlecht") or "").strip().lower()
        profil = bool(riege.get("profil"))
        if profil:
            gruppenrang = 2
        elif geschlecht == "m":
            gruppenrang = 0
        elif geschlecht == "w":
            gruppenrang = 1
        else:
            gruppenrang = 2
        return (stufe, klassen, gruppenrang, str(riege.get("name") or "").lower())

    riegen = sorted(riegen, key=sort_key)
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer, delimiter=";")
    writer.writerow(["Riegenführer", "Klasse", "Geschlecht", "Profil"])
    for riege in riegen:
        writer.writerow(
            [
                riege.get("name", ""),
                f"{riege.get('stufe', '')}{riege.get('klassenendungen', '')}",
                riege.get("geschlecht", ""),
                "Ja" if bool(riege.get("profil")) else "Nein",
            ]
        )

    filename = f"riegeneinteilung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = make_response(csv_buffer.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@auth_bp.route("/admin/select_db", methods=["POST"])
def admin_select_db():
    """Setzt eine registrierte Datenbank als aktive Event-Datenbank."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    name = (request.form.get("db_name") or "").strip()
    if not name:
        flash("Bitte eine Datenbank auswählen.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    registry = _get_registry()
    entry = registry.get_by_name(name)
    if not entry:
        flash("Datenbank nicht gefunden.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    registry.set_active_db_path(entry.path)

    # Die gecachte Verbindung muss weg, damit der naechste Request die neue DB oeffnet.
    try:
        db = get_db()
        db.close()
    except Exception:
        pass

    flash(f"Aktive DB gesetzt: {entry.name}", "success")
    return redirect(url_for("auth.admin_dashboard"))


@auth_bp.route("/admin/delete_db", methods=["POST"])
def admin_delete_db():
    """Entfernt eine Datenbank aus Registry und optional vom Dateisystem."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    name = (request.form.get("db_name") or "").strip()
    if not name:
        flash("Bitte eine Datenbank auswählen.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    registry = _get_registry()
    entry = registry.get_by_name(name)
    if not entry:
        flash("Datenbank nicht gefunden.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    # Merkt sich, ob gerade die aktive Datenbank geloescht werden soll.
    active_path = registry.get_active_db_path()
    was_active = active_path and Path(active_path) == Path(entry.path)

    if was_active:
        db = g.pop("db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception(
                    "Aktive Datenbank konnte vor dem Loeschen nicht geschlossen werden."
                )

    delete_file = request.form.get("delete_file", "true").lower() == "true"
    try:
        success = registry.delete_db(name, delete_file=delete_file)
    except Exception as exc:
        logger.exception("Loeschen der Datenbank fehlgeschlagen: %s", exc)
        flash(f"Löschen fehlgeschlagen: {exc}", "error")
        return redirect(url_for("auth.admin_dashboard"))

    if not success:
        flash("Löschen fehlgeschlagen.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    action = "gelöscht" if delete_file else "aus Registry entfernt"
    flash(f"Datenbank '{name}' wurde {action}.", "success")
    return redirect(url_for("auth.admin_dashboard"))


@auth_bp.route("/admin/riegeneinteilung/import_csv", methods=["POST"])
def admin_import_csv_to_new_db():
    """Importiert eine Schueler-CSV in eine neue oder bestehende Event-Datenbank."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    file = request.files.get("csv_file")
    if not file or not (file.filename or "").strip():
        message = "Keine CSV-Datei ausgewählt."
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    filename = secure_filename(file.filename or "")
    if not filename.lower().endswith(".csv"):
        message = "Nur .csv Dateien erlaubt."
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    import_mode = (request.form.get("import_mode") or "new_db").strip().lower()
    if import_mode not in {"new_db", "replace_existing", "append_existing"}:
        import_mode = "new_db"

    target_dir = Path(current_app.root_path).parent / "database"

    # Upload wird als Text gelesen; das Projekt erwartet hier immer Semikolon-Trennung.
    try:
        text = file.stream.read().decode("utf-8-sig", errors="replace")
    except Exception as exc:
        logger.exception("CSV-Import fehlgeschlagen: %s", exc)
        message = f"CSV Import fehlgeschlagen: {exc}"
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    registry = _get_registry()
    riegen_result = None
    imported_students = 0
    import_errors = 0
    db_name = ""
    try:
        if import_mode == "new_db":
            result = import_students_csv_to_new_db(
                csv_text=io.StringIO(text),
                target_dir=target_dir,
                delimiter=";",
            )
            registry.register_db(
                path=result.db_path,
                name=result.db_name,
                label="",
                year=datetime.now().year,
            )
            registry.set_active_db_path(result.db_path)
            g.pop("db", None)
            db = get_db()
            imported_students = result.imported
            import_errors = result.errors
            db_name = result.db_name
            leader_names = []
        else:
            db = get_db()
            if db is None:
                raise ValueError("Keine aktive Datenbank vorhanden.")
            leader_names = _get_existing_custom_leader_names(db)
            imported_students, import_errors = import_students_csv_into_db(
                db=db,
                csv_text=io.StringIO(text),
                delimiter=";",
                replace_existing=import_mode == "replace_existing",
            )
            db_name = Path(getattr(db, "db_path", "event.db")).name

        riegen_result = auto_create_riegen_and_assign(
            db=db,
            leader_names=leader_names,
            keep_existing_riegen=False,
        )
    except Exception as exc:
        message = f"Import OK, aber Riegen-Einteilung fehlgeschlagen: {exc}"
        if _wants_json_response():
            return jsonify({"error": message}), 500
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    success_message = (
        f"{imported_students} Schüler importiert, {riegen_result.created_riegen} Riegen erstellt."
    )
    flash(success_message, "success" if import_errors == 0 else "info")
    logger.info(
        "CSV importiert: db=%s imported=%s errors=%s mode=%s",
        db_name,
        imported_students,
        import_errors,
        import_mode,
    )
    if _wants_json_response():
        return jsonify(
            {
                "message": success_message,
                "db_name": db_name,
                "imported_students": imported_students,
                "import_errors": import_errors,
                "created_riegen": riegen_result.created_riegen,
                "assigned_students": riegen_result.assigned_students,
                "import_mode": import_mode,
            }
        )
    return redirect(url_for("auth.admin_riegeneinteilung"))


@auth_bp.route("/admin/riegeneinteilung/einteilen", methods=["POST"])
def admin_riegen_einteilen():
    """Create riegen with placeholder names (Riegenführer 1, 2, ...)."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    keep_existing = (request.form.get("keep_existing") or "") == "1"

    db = get_db()
    try:
        result = auto_create_riegen_and_assign(
            db=db,
            leader_names=[],  # Ohne Namen werden Platzhalter erzeugt.
            keep_existing_riegen=keep_existing,
        )
        stats = db.get_riegen_stats()
    except Exception as exc:
        flash(f"Einteilen fehlgeschlagen: {exc}", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    flash(
        "Einteilung fertig: "
        f"Riegen erstellt: {result.created_riegen}, "
        f"Schüler zugeordnet: {stats['students_assigned']}/{stats['students_total']}.",
        "success",
    )
    return redirect(url_for("auth.admin_riegeneinteilung"))


@auth_bp.route("/admin/riegeneinteilung/replace_names", methods=["POST"])
def admin_replace_leader_names():
    """Replace placeholder names with real names from uploaded CSV."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    leader_file = request.files.get("leaders_file")
    if not leader_file or not (leader_file.filename or "").strip():
        message = "Keine CSV-Datei ausgewählt."
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    try:
        raw = leader_file.stream.read().decode("utf-8-sig", errors="replace")
        leader_names = parse_leader_names_csv(csv_text=raw)
    except Exception as exc:
        logger.exception("Leiter-CSV konnte nicht gelesen werden: %s", exc)
        message = f"Leiter-CSV konnte nicht gelesen werden: {exc}"
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    if not leader_names:
        message = "Keine Namen in der CSV gefunden."
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    db = get_db()
    if db is None:
        message = "Keine Datenbank vorhanden. Bitte zuerst CSV importieren."
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))
    try:
        result = replace_placeholder_names(db=db, leader_names=leader_names)
    except Exception as exc:
        message = f"Namen ersetzen fehlgeschlagen: {exc}"
        if _wants_json_response():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    riegen_data = _build_riegen_page_data(db)
    leader_message = (
        "Alle Riegen haben einen Riegenführer zugeteilt bekommen"
        if riegen_data["leader_name_stats"]["missing_extra_leader"] == 0
        else (
            f"Es fehlen noch {riegen_data['leader_name_stats']['missing_extra_leader']} "
            "Riegenführer."
        )
    )
    success_message = (
        f"Namen ersetzt: {result.replaced} von {result.total_riegen} Riegen aktualisiert."
    )
    flash(success_message, "success")
    extra_names_message = None
    if result.unused_names > 0:
        extra_names_message = (
            "Die hochgeladene CSV hatte zu viele Riegenführer nicht alle wurden zugeteilt"
        )
        flash(extra_names_message, "info")
    if _wants_json_response():
        return jsonify(
            {
                "message": success_message,
                "replaced": result.replaced,
                "total_riegen": result.total_riegen,
                "unused_names": result.unused_names,
                "extra_names_message": extra_names_message,
                "with_extra_leader": riegen_data["leader_name_stats"][
                    "with_extra_leader"
                ],
                "missing_extra_leader": riegen_data["leader_name_stats"][
                    "missing_extra_leader"
                ],
                "leader_message": leader_message,
            }
        )
    return redirect(url_for("auth.admin_riegeneinteilung"))


@auth_bp.route("/admin/riegeneinteilung/update_riege", methods=["POST"])
def admin_update_riege():
    """Aktualisiert Stammdaten einer einzelnen Riege und weist optional neu zu."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    riegen_id_raw = (request.form.get("riegen_id") or "").strip()
    name = (request.form.get("name") or "").strip()
    stufe_raw = (request.form.get("stufe") or "").strip()
    klassen = (request.form.get("klassenendungen") or "").strip()
    geschlecht = (request.form.get("geschlecht") or "").strip()
    profil = (request.form.get("profil") or "") == "1"
    reassign = (request.form.get("reassign") or "") == "1"

    try:
        riegen_id = int(riegen_id_raw)
        stufe = int(stufe_raw)
    except Exception:
        flash("Ungültige Eingaben.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    db = get_db()
    if db is None:
        flash("Keine Datenbank vorhanden. Bitte zuerst CSV importieren.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))
    try:
        updated = db.update_riege(
            riegen_id=riegen_id,
            name=name,
            stufe=stufe,
            klassenendungen=klassen,
            geschlecht=geschlecht,
            profil=profil,
        )
        if not updated:
            flash("Riege nicht gefunden.", "error")
            return redirect(url_for("auth.admin_riegeneinteilung"))

        if reassign:
            # Bei Neuverteilung werden alte Zuweisungen zuerst geloest und dann neu aufgebaut.
            db._execute_tx(
                "UPDATE Schueler SET RiegenfuehrerID = NULL WHERE RiegenfuehrerID = ?",
                (riegen_id,),
            )
            for kl_end in klassen or "":
                if kl_end.strip():
                    if profil:
                        db.add_riegenfuehrer_to_schueler(
                            rf_id=riegen_id,
                            klassenbuchstabe=kl_end.strip().lower(),
                            stufe=stufe,
                            geschlecht="mw",
                            profil=True,
                        )
                        continue

                    for zielgeschlecht in _resolve_assignment_genders(geschlecht):
                        db.add_riegenfuehrer_to_schueler(
                            rf_id=riegen_id,
                            klassenbuchstabe=kl_end.strip().lower(),
                            stufe=stufe,
                            geschlecht=zielgeschlecht,
                            profil=False,
                        )
            db.connection.commit()
    except Exception as exc:
        flash(f"Update fehlgeschlagen: {exc}", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    flash("Riege gespeichert.", "success")
    return redirect(url_for("auth.admin_riegeneinteilung"))


@auth_bp.route("/admin/riegeneinteilung/delete_riege", methods=["POST"])
def admin_delete_riege():
    """Loescht eine Riege und hebt ihre Zuweisungen auf."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    riegen_id_raw = (request.form.get("riegen_id") or "").strip()
    try:
        riegen_id = int(riegen_id_raw)
    except Exception:
        flash("Ungültige Riegen-ID.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    db = get_db()
    if db is None:
        flash("Keine Datenbank vorhanden. Bitte zuerst CSV importieren.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))
    try:
        unassigned, deleted = db.delete_riege(riegenfuehrer_id=riegen_id)
    except Exception as exc:
        flash(f"Löschen fehlgeschlagen: {exc}", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    if deleted:
        flash(f"Riege gelöscht. Zuweisungen entfernt: {unassigned}", "success")
    else:
        flash("Riege nicht gefunden.", "error")

    return redirect(url_for("auth.admin_riegeneinteilung"))


# ============================================
# Disziplin-CRUD (liegt in der Meta-Datenbank, nicht in einzelnen Event-DBs)
# ============================================


@auth_bp.route("/admin/disziplinen", methods=["GET"])
def admin_disziplinen():
    """Zeigt die statischen Disziplinen und Auswertungskonstanten an."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    registry = _get_registry()
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]
    auswertung_config = registry.get_auswertung_config()

    return render_template(
        "admin_disziplinen.html",
        disziplinen=disziplinen,
        disziplinen_tab_konstanten=get_disziplinen_tab_konstanten(),
        auswertung_config=auswertung_config,
    )


@auth_bp.route("/admin/disziplinen/list", methods=["GET"])
def admin_disziplinen_list():
    """Liefert alle globalen Disziplinen als JSON-Liste."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    registry = _get_registry()
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]
    return jsonify({"disziplinen": disziplinen})


@auth_bp.route("/admin/disziplinen/create", methods=["POST"])
def admin_disziplinen_create():
    """Disziplinen sind statisch und koennen nicht angelegt werden."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"error": "Disziplinen sind fest im Code hinterlegt."}), 410


@auth_bp.route("/admin/disziplinen/<int:disziplin_id>", methods=["GET"])
def admin_disziplinen_get(disziplin_id: int):
    """Liefert die Daten einer einzelnen Disziplin."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    registry = _get_registry()
    disziplin = registry.get_disziplin(disziplin_id)
    if not disziplin:
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify(_disziplin_to_dict(disziplin))


@auth_bp.route("/admin/disziplinen/<int:disziplin_id>", methods=["PUT"])
def admin_disziplinen_update(disziplin_id: int):
    """Disziplinen sind statisch und koennen nicht bearbeitet werden."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"error": "Disziplinen sind fest im Code hinterlegt."}), 410


@auth_bp.route("/admin/disziplinen/<int:disziplin_id>", methods=["DELETE"])
def admin_disziplinen_delete(disziplin_id: int):
    """Disziplinen sind statisch und koennen nicht geloescht werden."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"error": "Disziplinen sind fest im Code hinterlegt."}), 410


@auth_bp.route("/admin/disziplinen/auswertung-config", methods=["GET"])
def admin_disziplinen_auswertung_config_get():
    """Liefert die bearbeitbare Auswertungskonfiguration."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    registry = _get_registry()
    return jsonify({"config": registry.get_auswertung_config()})


@auth_bp.route("/admin/disziplinen/auswertung-config", methods=["PUT"])
def admin_disziplinen_auswertung_config_put():
    """Auswertungskonfiguration ist statisch und nicht editierbar."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"error": "Die Auswertungskonfiguration ist fest im Code hinterlegt."}), 410


# ============================================
# Dashboard und Statistiken (Event und Admin)
# ============================================


def _require_dashboard_access():
    """Prueft den Zugriff auf Dashboard-Seiten fuer Admin und Event."""
    return session.get("role") in ("admin", "event")


def _require_event_access():
    """Prueft den Zugriff auf reine Event-Seiten."""
    return session.get("role") == "event"


@auth_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Rendert das Dashboard mit Riegenfortschritt und Gesamtstatistiken."""
    if not _require_dashboard_access():
        return redirect(url_for("auth.login"))

    db = get_db()
    registry = _get_registry()
    disziplin_filter = request.args.get("disziplin")
    num_rounds = _get_progress_num_rounds(registry, disziplin_filter)
    riegen = (
        db.get_all_riegen_with_progress(
            disziplin=disziplin_filter,
            num_rounds=num_rounds,
        )
        if db
        else []
    )
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]
    stats = db.get_stats() if db else {}

    return render_template(
        "dashboard.html",
        riegen=riegen,
        disziplinen=disziplinen,
        stats=stats,
        selected_disziplin=disziplin_filter,
    )


@auth_bp.route("/dashboard/data", methods=["GET"])
def dashboard_data():
    """Liefert Dashboard-Daten fuer asynchrone Aktualisierungen."""
    if not _require_dashboard_access():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    disziplin_filter = request.args.get("disziplin")
    registry = _get_registry()
    num_rounds = _get_progress_num_rounds(registry, disziplin_filter)
    riegen = (
        db.get_all_riegen_with_progress(
            disziplin=disziplin_filter,
            num_rounds=num_rounds,
        )
        if db
        else []
    )
    stats = db.get_stats() if db else {}

    return jsonify({"riegen": riegen, "stats": stats})


@auth_bp.route("/event/overview", methods=["GET"])
def event_overview():
    """Zeigt die Event-Uebersicht als kompakte Fortschrittsansicht je Disziplin."""
    if not _require_event_access():
        return redirect(url_for("auth.login"))

    db = get_db()
    registry = _get_registry()
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]
    stats = db.get_stats() if db else {}
    progress_data = _build_event_progress_cards(db, disziplinen)

    return render_template(
        "event_overview.html",
        disziplinen=disziplinen,
        stats=stats,
        event_progress=progress_data,
    )


@auth_bp.route("/stats", methods=["GET"])
def stats_page():
    """Zeigt die separate Statistikseite fuer das Event an."""
    if not _require_event_access():
        return redirect(url_for("auth.login"))

    db = get_db()
    registry = _get_registry()
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]
    stats = db.get_stats() if db else {}

    selected_disziplin = request.args.get("disziplin")
    if not selected_disziplin and disziplinen:
        selected_disziplin = disziplinen[0]["name"]

    bestenliste = []
    selected_meta = next(
        (d for d in disziplinen if d["name"] == selected_disziplin), None
    )
    if selected_disziplin and db:
        geschlecht_filter = request.args.get("geschlecht")
        bestenliste = db.get_bestenliste(
            selected_disziplin,
            limit=20,
            geschlecht=geschlecht_filter,
            result_format_override=selected_meta["format"] if selected_meta else None,
        )
    auswertung_summary = db.get_auswertung_summary() if db else {}
    gesamt_bestenliste = (
        db.get_gesamt_bestenliste(
            limit=20,
            geschlecht=request.args.get("geschlecht"),
        )
        if db
        else []
    )

    return render_template(
        "stats.html",
        disziplinen=disziplinen,
        stats=stats,
        bestenliste=bestenliste,
        selected_disziplin=selected_disziplin,
        auswertung_summary=auswertung_summary,
        gesamt_bestenliste=gesamt_bestenliste,
    )


@auth_bp.route("/stats/bestenliste", methods=["GET"])
def stats_bestenliste():
    """Liefert die Bestenliste einer Disziplin als JSON-Antwort."""
    if not _require_event_access():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    disziplin = request.args.get("disziplin")
    if not disziplin:
        return jsonify({"error": "disziplin Parameter erforderlich"}), 400

    geschlecht = request.args.get("geschlecht")
    limit = int(request.args.get("limit", 20))
    registry = _get_registry()
    selected_meta = registry.get_disziplin_by_name(disziplin)

    bestenliste = db.get_bestenliste(
        disziplin,
        limit=limit,
        geschlecht=geschlecht,
        result_format_override=selected_meta.format if selected_meta else None,
    )
    return jsonify({"bestenliste": bestenliste, "disziplin": disziplin})


@auth_bp.route("/stats/auswertung/run", methods=["POST"])
def stats_run_auswertung():
    """Berechnet Gesamtpunktzahlen, erzeugt CSV-Export und liefert ihn als ZIP."""
    if not _require_dashboard_access():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503

    registry = _get_registry()
    service = AuswertungService.from_registry(registry)
    referenzjahr = _get_active_event_year(registry, db)
    result = service.evaluate_database(db, year=referenzjahr)
    summary = db.get_auswertung_summary()
    export_dir = _export_auswertung_by_class(
        db=db,
        registry=registry,
        service=service,
    )
    zip_buffer = _build_zip_from_directory(export_dir)
    download_name = f"{export_dir.name}.zip"

    response = send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )
    response.headers["X-Evaluated-Students"] = str(result.evaluated_students)
    response.headers["X-Skipped-Students"] = str(result.skipped_students)
    response.headers["X-Total-Students"] = str(result.total_students)
    response.headers["X-Export-Dir"] = str(export_dir)
    response.headers["X-Auswertung-Summary"] = json.dumps(summary)
    return response
