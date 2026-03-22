"""Routen fuer Login, Administration, Dashboard und Event-Ansichten."""

import io
import json
import logging
import secrets
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

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
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from app import get_db
from app.db_registry import DbRegistry, Disziplin, default_meta_db_path
from app.services_csv_import import import_students_csv_to_new_db
from app.services_riegen import (
    auto_create_riegen_and_assign,
    parse_leader_names_csv,
    replace_placeholder_names,
)

auth_bp = Blueprint("auth", __name__, template_folder="../templates")
logger = logging.getLogger(__name__)

# Einfaches In-Memory-Rate-Limit pro IP und Login-Modus.
_RATE_LIMIT_BUCKETS = {}
_RATE_LIMIT_WINDOW = 300  # Sekunden
_RATE_LIMIT_MAX = 10
_DEVICE_COOKIE_NAME = "device_id"
_EVENT_PASSWORD_KEY = "event_password"


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
    return {
        "id": d.id,
        "name": d.name,
        "format": d.format,
        "num_rounds": d.num_rounds,
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
    pw = db.get_setting(_EVENT_PASSWORD_KEY, None)
    if pw:
        return pw
    return current_app.config.get("EVENT_PASSWORD")


def _seed_default_pin():
    """Stellt sicher, dass beim Start ein Standard-PIN fuer eine Station existiert."""
    seeded_flag = "_DEFAULT_PIN_SEEDED"
    if current_app.config.get(seeded_flag):
        return
    db = get_db()
    if db is None:
        # Ohne aktive Datenbank kann noch kein Standard-PIN erzeugt werden.
        return
    station_name = current_app.config.get("STATION_DEFAULT_NAME", "Station")
    desired_pin = current_app.config.get("STATION_DEFAULT_PIN")
    max_logins = current_app.config.get("STATION_DEFAULT_MAX_LOGINS", 1)
    length = current_app.config.get("STATION_DEFAULT_PIN_LENGTH", 6)

    if desired_pin:
        row = db.cursor.execute(
            "SELECT pin FROM Station_Pin WHERE pin = ? AND active = 1", (desired_pin,)
        ).fetchone()
        if not row:
            try:
                db._execute_tx(
                    """
                    INSERT OR IGNORE INTO Station_Pin (station, discipline, pin, max_logins, active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (station_name, station_name, desired_pin, max_logins),
                )
            except Exception:
                pass
    else:
        db.ensure_default_station_pin(
            station=station_name,
            max_logins=max_logins,
            length=length,
            discipline=station_name,
        )
    current_app.config[seeded_flag] = True


@auth_bp.before_app_request
def _before_request_seed_pin():
    """Fuehrt vor jeder Anfrage die Initialisierung des Standard-PIN aus."""
    _seed_default_pin()


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
    active_db = registry.get_active_db_path()
    dbs = registry.list_dbs()

    db = get_db()

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
        event_pin = db.get_setting(_EVENT_PASSWORD_KEY, None)

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
        "no_database": db is None,
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
    new_pin = "".join(secrets.choice("0123456789") for _ in range(6))

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
    active_db = registry.get_active_db_path()
    dbs = registry.list_dbs()

    db = get_db()

    # Ohne aktive Datenbank bleibt die Seite bedienbar, zeigt aber leere Kennzahlen.
    if db is None:
        riegen = []
        stats = {
            "students_total": 0,
            "students_assigned": 0,
            "students_unassigned": 0,
            "riegen_total": 0,
            "profil_total": 0,
            "profil_assigned": 0,
        }
        classes = []
    else:
        try:
            riegen = db.get_all_riegen_with_progress()
        except Exception:
            riegen = []

        try:
            stats = db.get_riegen_stats()
            classes = db.get_present_classes()
        except Exception:
            stats = {
                "students_total": 0,
                "students_assigned": 0,
                "students_unassigned": 0,
                "riegen_total": 0,
                "profil_total": 0,
                "profil_assigned": 0,
            }
            classes = []

    return render_template(
        "admin_riegeneinteilung.html",
        dbs=dbs,
        active_db_path=active_db,
        riegen=riegen,
        stats=stats,
        classes=classes,
        no_database=db is None,
    )


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

    # Entfernt den Registry-Eintrag und optional die eigentliche Datei.
    delete_file = request.form.get("delete_file", "true").lower() == "true"
    success = registry.delete_db(name, delete_file=delete_file)

    if not success:
        flash("Löschen fehlgeschlagen.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    # Bei geloeschter aktiver DB darf keine alte Verbindung im Request-Kontext haengen bleiben.
    if was_active:
        try:
            db = get_db()
            db.close()
        except Exception:
            pass

    action = "gelöscht" if delete_file else "aus Registry entfernt"
    flash(f"Datenbank '{name}' wurde {action}.", "success")
    return redirect(url_for("auth.admin_dashboard"))


@auth_bp.route("/admin/riegeneinteilung/import_csv", methods=["POST"])
def admin_import_csv_to_new_db():
    """Importiert eine Schueler-CSV in eine neue Event-Datenbank."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    file = request.files.get("csv_file")
    if not file or not (file.filename or "").strip():
        flash("Keine CSV-Datei ausgewählt.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    filename = secure_filename(file.filename or "")
    if not filename.lower().endswith(".csv"):
        flash("Nur .csv Dateien erlaubt.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    target_dir = Path(current_app.root_path).parent / "database"

    # Upload wird als Text gelesen; das Projekt erwartet hier immer Semikolon-Trennung.
    try:
        text = file.stream.read().decode("utf-8-sig", errors="replace")
        result = import_students_csv_to_new_db(
            csv_text=io.StringIO(text),
            target_dir=target_dir,
            delimiter=";",
        )
    except Exception as exc:
        logger.exception("CSV-Import fehlgeschlagen: %s", exc)
        flash(f"CSV Import fehlgeschlagen: {exc}", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    registry = _get_registry()
    registry.register_db(path=result.db_path, name=result.db_name, label="")

    # Nach dem Import wird die neue Event-Datenbank sofort aktiv gesetzt.
    registry.set_active_db_path(result.db_path)

    # So wird im selben Request keine veraltete Verbindung weiterverwendet.
    g.pop("db", None)

    # Direkt nach dem Import werden Platzhalter-Riegen erzeugt, damit die App startklar ist.
    riegen_result = None
    try:
        db = get_db()
        riegen_result = auto_create_riegen_and_assign(
            db=db,
            leader_names=[],  # Leere Liste erzwingt Platzhalternamen.
            keep_existing_riegen=False,
        )
    except Exception as exc:
        flash(f"Import OK, aber Riegen-Einteilung fehlgeschlagen: {exc}", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    flash(
        f"{result.imported} Schüler importiert, {riegen_result.created_riegen} Riegen erstellt.",
        "success" if result.errors == 0 else "info",
    )
    logger.info(
        "CSV importiert: db=%s imported=%s errors=%s",
        result.db_name,
        result.imported,
        result.errors,
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
        flash("Keine CSV-Datei ausgewählt.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    try:
        raw = leader_file.stream.read().decode("utf-8-sig", errors="replace")
        leader_names = parse_leader_names_csv(csv_text=raw)
    except Exception as exc:
        logger.exception("Leiter-CSV konnte nicht gelesen werden: %s", exc)
        flash(f"Leiter-CSV konnte nicht gelesen werden: {exc}", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    if not leader_names:
        flash("Keine Namen in der CSV gefunden.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    db = get_db()
    if db is None:
        flash("Keine Datenbank vorhanden. Bitte zuerst CSV importieren.", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))
    try:
        result = replace_placeholder_names(db=db, leader_names=leader_names)
    except Exception as exc:
        flash(f"Namen ersetzen fehlgeschlagen: {exc}", "error")
        return redirect(url_for("auth.admin_riegeneinteilung"))

    flash(
        f"Namen ersetzt: {result.replaced} von {result.total_riegen} Riegen aktualisiert.",
        "success",
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
                    db.add_riegenfuehrer_to_schueler(
                        rf_id=riegen_id,
                        klassenbuchstabe=kl_end.strip().lower(),
                        stufe=stufe,
                        geschlecht=geschlecht or "mw",
                        profil=bool(profil),
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
    """Zeigt die Administrationsseite fuer globale Disziplinen an."""
    if not _require_admin():
        return redirect(url_for("auth.login"))

    registry = _get_registry()
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]

    return render_template("admin_disziplinen.html", disziplinen=disziplinen)


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
    """Legt eine neue globale Disziplin an."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name erforderlich"}), 400

    registry = _get_registry()

    existing = registry.get_disziplin_by_name(name)
    if existing:
        return jsonify({"error": f"Disziplin '{name}' existiert bereits"}), 400

    try:
        disziplin_id = registry.create_disziplin(
            name=name,
            format=payload.get("format", "distance"),
            num_rounds=int(payload.get("num_rounds", 3)),
        )
        return jsonify({"id": disziplin_id, "message": "Disziplin erstellt"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Fehler: {e}"}), 500


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
    """Aktualisiert eine vorhandene globale Disziplin."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    registry = _get_registry()

    try:
        ok = registry.update_disziplin(
            disziplin_id,
            name=payload.get("name"),
            format=payload.get("format"),
            num_rounds=int(payload["num_rounds"]) if "num_rounds" in payload else None,
        )
        if not ok:
            return jsonify({"error": "Nicht gefunden"}), 404
        return jsonify({"message": "Aktualisiert"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Fehler: {e}"}), 500


@auth_bp.route("/admin/disziplinen/<int:disziplin_id>", methods=["DELETE"])
def admin_disziplinen_delete(disziplin_id: int):
    """Loescht eine globale Disziplin."""
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    registry = _get_registry()
    ok = registry.delete_disziplin(disziplin_id)
    if not ok:
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify({"deleted": True})


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
    riegen = db.get_all_riegen_with_progress(disziplin=disziplin_filter) if db else []
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

    riegen = db.get_all_riegen_with_progress(disziplin=disziplin_filter) if db else []
    stats = db.get_stats() if db else {}

    return jsonify({"riegen": riegen, "stats": stats})


@auth_bp.route("/event/overview", methods=["GET"])
def event_overview():
    """Zeigt die Event-Uebersicht mit Bestenliste und Disziplinfilter."""
    if not _require_event_access():
        return redirect(url_for("auth.login"))

    db = get_db()
    registry = _get_registry()
    disziplin_filter = request.args.get("disziplin")
    geschlecht_filter = request.args.get("geschlecht")
    disziplinen = [_disziplin_to_dict(d) for d in registry.get_disziplinen()]
    if not disziplin_filter and disziplinen:
        disziplin_filter = disziplinen[0]["name"]

    selected_meta = next(
        (d for d in disziplinen if d["name"] == disziplin_filter), None
    )
    riegen = db.get_all_riegen_with_progress(disziplin=disziplin_filter) if db else []
    stats = db.get_stats() if db else {}
    bestenliste = []
    if disziplin_filter and db:
        bestenliste = db.get_bestenliste(
            disziplin_filter,
            limit=20,
            geschlecht=geschlecht_filter,
            result_format_override=selected_meta["format"] if selected_meta else None,
        )

    return render_template(
        "dashboard.html",
        riegen=riegen,
        disziplinen=disziplinen,
        stats=stats,
        selected_disziplin=disziplin_filter,
        selected_geschlecht=geschlecht_filter,
        selected_disziplin_meta=selected_meta,
        bestenliste=bestenliste,
        is_event_overview=True,
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

    return render_template(
        "stats.html",
        disziplinen=disziplinen,
        stats=stats,
        bestenliste=bestenliste,
        selected_disziplin=selected_disziplin,
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
