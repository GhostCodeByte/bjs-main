import json
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

auth_bp = Blueprint("auth", __name__, template_folder="../templates")

# simple in-memory rate limiting (per IP + mode)
_RATE_LIMIT_BUCKETS = {}
_RATE_LIMIT_WINDOW = 300  # seconds
_RATE_LIMIT_MAX = 10
_DEVICE_COOKIE_NAME = "device_id"
_EVENT_PASSWORD_KEY = "event_password"
_DEFAULT_EVENT_PASSWORD = "event123"


def _check_rate_limit(key: str, limit: int = _RATE_LIMIT_MAX, window: int = _RATE_LIMIT_WINDOW):
    now = time.time()
    bucket = _RATE_LIMIT_BUCKETS.setdefault(key, [])
    _RATE_LIMIT_BUCKETS[key] = [ts for ts in bucket if ts > now - window]
    if len(_RATE_LIMIT_BUCKETS[key]) >= limit:
        return False
    _RATE_LIMIT_BUCKETS[key].append(now)
    return True


def _require_admin():
    return session.get("role") == "admin"


def _require_admin_or_event():
    return session.get("role") in ("admin", "event")


def _get_device_id() -> str:
    return (
        request.cookies.get(_DEVICE_COOKIE_NAME)
        or request.headers.get("X-Device-Id")
        or session.get("device_id")
        or f"device-{uuid.uuid4()}"
    )


def _get_event_password():
    db = get_db()
    pw = db.get_setting(_EVENT_PASSWORD_KEY, None)
    if pw:
        return pw
    return current_app.config.get("EVENT_PASSWORD", _DEFAULT_EVENT_PASSWORD)


def _seed_default_pin():
    seeded_flag = "_DEFAULT_PIN_SEEDED"
    if current_app.config.get(seeded_flag):
        return
    db = get_db()
    station_name = current_app.config.get("STATION_DEFAULT_NAME", "Station")
    desired_pin = current_app.config.get("STATION_DEFAULT_PIN")
    max_logins = 1  # hardcoded requirement
    length = 6

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
            station=station_name, max_logins=max_logins, length=length, discipline=station_name
        )
    current_app.config[seeded_flag] = True


@auth_bp.before_app_request
def _before_request_seed_pin():
    _seed_default_pin()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
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
            flash("Admin-Login erfolgreich.", "success")
            return redirect(url_for("auth.admin_dashboard"))

        if login_mode == "event":
            if not password:
                flash("Event-Passwort erforderlich.", "error")
                resp = make_response(render_template("auth.html"))
                resp.status_code = 401
                return resp
            if password != _get_event_password():
                flash("Ungültiges Event-Passwort.", "error")
                resp = make_response(render_template("auth.html"))
                resp.status_code = 401
                return resp
            session.clear()
            session["is_logged_in"] = True
            session["role"] = "event"
            session["event_login_at"] = time.time()
            flash("Event-Login erfolgreich.", "success")
            return redirect(url_for("auth.event_overview"))

        # station login
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
        ok, msg = db.claim_station_pin(pin=pin, device_id=device_id, discipline=discipline)
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

        resp = redirect(url_for("input.input_page"))
        if not request.cookies.get(_DEVICE_COOKIE_NAME):
            resp = make_response(resp)
            resp.set_cookie(
                _DEVICE_COOKIE_NAME,
                device_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
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

    db = get_db()
    disziplinen = db.get_disziplinen()

    resp = make_response(render_template("auth.html", disziplinen=disziplinen))
    if not request.cookies.get(_DEVICE_COOKIE_NAME):
        device_id = _get_device_id()
        resp.set_cookie(
            _DEVICE_COOKIE_NAME,
            device_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
        )
    return resp


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
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
    resp.set_cookie(_DEVICE_COOKIE_NAME, "", expires=0)
    flash("Abgemeldet.", "info")
    return resp


# ============================================
# Admin Dashboard
# ============================================


@auth_bp.route("/admin", methods=["GET"])
def admin_dashboard():
    if not _require_admin():
        return redirect(url_for("auth.login"))

    db = get_db()
    pins = db.cursor.execute(
        "SELECT id, station, discipline, pin, max_logins, active, created_at FROM Station_Pin"
    ).fetchall()
    sessions_rows = db.cursor.execute(
        "SELECT id, pin, device_id, discipline, active, created_at FROM Station_Session"
    ).fetchall()

    stats = db.get_stats()
    backup_config = db.get_backup_config()
    backup_history = db.get_backup_history(limit=5)
    disziplinen = db.get_disziplinen()

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
        "sessions": [
            {
                "id": row[0],
                "pin": row[1],
                "device_id": row[2],
                "discipline": row[3],
                "active": bool(row[4]),
                "created_at": row[5],
            }
            for row in sessions_rows
        ],
        "stats": stats,
        "backup_config": backup_config,
        "backup_history": backup_history,
        "event_password_set": bool(db.get_setting(_EVENT_PASSWORD_KEY, None)),
        "disziplinen": disziplinen,
    }
    return render_template("admin_dashboard.html", **data)


@auth_bp.route("/admin/generate_pin", methods=["POST"])
def admin_generate_pin():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    discipline = payload.get("discipline") or payload.get("station")
    if not discipline:
        return jsonify({"error": "discipline erforderlich"}), 400

    db = get_db()
    pin = db.generate_station_pin(
        station=discipline,
        discipline=discipline,
        max_logins=1,
        length=6,
    )
    return jsonify({"pin": pin, "discipline": discipline, "station": discipline, "max_logins": 1})


@auth_bp.route("/admin/revoke_pin", methods=["POST"])
def admin_revoke_pin():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    pin = payload.get("pin")
    if not pin:
        return jsonify({"error": "pin erforderlich"}), 400
    db = get_db()
    revoked = db.deactivate_pin(pin)
    return jsonify({"revoked": revoked})


@auth_bp.route("/admin/pins/delete", methods=["POST"])
def admin_delete_pin():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    pin = payload.get("pin")
    if not pin:
        return jsonify({"error": "pin erforderlich"}), 400
    db = get_db()
    deleted = db.delete_pin(pin)
    return jsonify({"deleted": deleted})


@auth_bp.route("/admin/pins/deactivate", methods=["POST"])
def admin_deactivate_pin():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    pin = payload.get("pin")
    if not pin:
        return jsonify({"error": "pin erforderlich"}), 400
    db = get_db()
    count = db.deactivate_pin(pin)
    return jsonify({"deactivated": count})


@auth_bp.route("/admin/sessions/deactivate", methods=["POST"])
def admin_deactivate_session():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    db = get_db()
    count = db.deactivate_session(
        session_id=payload.get("session_id"),
        pin=payload.get("pin"),
        device_id=payload.get("device_id"),
    )
    return jsonify({"deactivated": count})


@auth_bp.route("/admin/sessions/delete", methods=["POST"])
def admin_delete_session():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    db = get_db()
    count = db.delete_session(
        session_id=payload.get("session_id"),
        pin=payload.get("pin"),
        device_id=payload.get("device_id"),
    )
    return jsonify({"deleted": count})


@auth_bp.route("/admin/event_password", methods=["POST"])
def admin_set_event_password():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    password = (payload.get("password") or "").strip()
    if len(password) < 4:
        return jsonify({"error": "Passwort zu kurz"}), 400
    db = get_db()
    db.set_setting(_EVENT_PASSWORD_KEY, password)
    return jsonify({"status": "ok"})


@auth_bp.route("/admin/backup", methods=["POST"])
def admin_backup():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    label = payload.get("label") or "manual"
    db = get_db()
    path = db.backup_to_file(label=label, backup_type="manual")
    return jsonify({"backup_path": path})


@auth_bp.route("/admin/backup/config", methods=["PUT"])
def admin_backup_config():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    interval = payload.get("interval_minutes")
    max_backups = payload.get("max_backups")
    enabled = payload.get("enabled")
    db = get_db()
    db.update_backup_config(interval_minutes=interval, max_backups=max_backups, enabled=enabled)
    return jsonify({"status": "ok"})


@auth_bp.route("/admin/upload_db", methods=["POST"])
def admin_upload_db():
    if not _require_admin():
        flash("Nicht berechtigt.", "error")
        return redirect(url_for("auth.login"))

    file = request.files.get("db_file")
    if not file or file.filename == "":
        flash("Keine Datei ausgewählt.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".db"):
        flash("Nur .db Dateien erlaubt.", "error")
        return redirect(url_for("auth.admin_dashboard"))

    db = get_db()
    backup_label = request.form.get("label") or "upload"
    backup_path = db.backup_to_file(label=backup_label, backup_type="upload")

    target_path = Path(current_app.config.get("DB_PATH"))
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file.save(tmp.name)
        temp_path = Path(tmp.name)

    try:
        db.close()
        shutil.move(str(temp_path), target_path)
        flash(f"DB hochgeladen. Backup: {backup_path}", "success")
    except Exception as exc:
        flash(f"Upload fehlgeschlagen: {exc}", "error")
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return redirect(url_for("auth.admin_dashboard"))


# ============================================
# Disziplin-CRUD
# ============================================


@auth_bp.route("/admin/disziplinen", methods=["GET"])
def admin_disziplinen():
    if not _require_admin():
        return redirect(url_for("auth.login"))

    db = get_db()
    disziplinen = db.get_disziplinen()

    return render_template("admin_disziplinen.html", disziplinen=disziplinen)


@auth_bp.route("/admin/disziplinen/list", methods=["GET"])
def admin_disziplinen_list():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    disziplinen = db.get_disziplinen()
    return jsonify({"disziplinen": disziplinen})


@auth_bp.route("/admin/disziplinen/create", methods=["POST"])
def admin_disziplinen_create():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"error": "Name erforderlich"}), 400

    db = get_db()

    existing = db.get_disziplin_by_name(name)
    if existing:
        return jsonify({"error": f"Disziplin '{name}' existiert bereits"}), 400

    try:
        disziplin_id = db.create_disziplin(
            name=name,
            display_name=payload.get("display_name"),
            result_format=payload.get("result_format", "distance"),
            num_rounds=int(payload.get("num_rounds", 3)),
            unit=payload.get("unit", "m"),
            description=payload.get("description"),
            sort_order=int(payload.get("sort_order", 0)),
        )
        return jsonify({"id": disziplin_id, "message": "Disziplin erstellt"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Fehler: {e}"}), 500


@auth_bp.route("/admin/disziplinen/<int:disziplin_id>", methods=["GET"])
def admin_disziplinen_get(disziplin_id: int):
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    disziplin = db.get_disziplin(disziplin_id)
    if not disziplin:
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify(disziplin)


@auth_bp.route("/admin/disziplinen/<int:disziplin_id>", methods=["PUT"])
def admin_disziplinen_update(disziplin_id: int):
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    db = get_db()

    try:
        ok = db.update_disziplin(
            disziplin_id,
            name=payload.get("name"),
            display_name=payload.get("display_name"),
            result_format=payload.get("result_format"),
            num_rounds=int(payload["num_rounds"]) if "num_rounds" in payload else None,
            unit=payload.get("unit"),
            description=payload.get("description"),
            sort_order=int(payload["sort_order"]) if "sort_order" in payload else None,
        )
        if not ok:
            return jsonify({"error": "Keine Änderungen"}), 400
        return jsonify({"message": "Aktualisiert"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Fehler: {e}"}), 500


@auth_bp.route("/admin/disziplinen/<int:disziplin_id>", methods=["DELETE"])
def admin_disziplinen_delete(disziplin_id: int):
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    ok = db.delete_disziplin(disziplin_id)
    if not ok:
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify({"deleted": True})


@auth_bp.route("/admin/disziplinen/export", methods=["GET"])
def admin_disziplinen_export():
    if not _require_admin():
        return redirect(url_for("auth.login"))
    db = get_db()
    data = db.export_disziplinen()
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/json"
    resp.headers["Content-Disposition"] = "attachment; filename=disziplinen.json"
    return resp


@auth_bp.route("/admin/disziplinen/import", methods=["POST"])
def admin_disziplinen_import():
    if not _require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    file = request.files.get("file")
    replace = request.form.get("replace", "false").lower() == "true"
    if not file:
        return jsonify({"error": "Datei erforderlich"}), 400
    content = file.read().decode("utf-8")
    db = get_db()
    try:
        count = db.import_disziplinen(content, replace=replace)
        return jsonify({"imported": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ============================================
# Dashboard & Stats (Event + Admin)
# ============================================


def _require_dashboard_access():
    return session.get("role") in ("admin", "event")


@auth_bp.route("/dashboard", methods=["GET"])
def dashboard():
    if not _require_dashboard_access():
        return redirect(url_for("auth.login"))

    db = get_db()
    disziplin_filter = request.args.get("disziplin")
    riegen = db.get_all_riegen_with_progress(disziplin=disziplin_filter)
    disziplinen = db.get_disziplinen()
    stats = db.get_stats()

    return render_template(
        "dashboard.html",
        riegen=riegen,
        disziplinen=disziplinen,
        stats=stats,
        selected_disziplin=disziplin_filter,
    )


@auth_bp.route("/dashboard/data", methods=["GET"])
def dashboard_data():
    if not _require_dashboard_access():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    disziplin_filter = request.args.get("disziplin")

    riegen = db.get_all_riegen_with_progress(disziplin=disziplin_filter)
    stats = db.get_stats()

    return jsonify({"riegen": riegen, "stats": stats})


@auth_bp.route("/event/overview", methods=["GET"])
def event_overview():
    if not _require_dashboard_access():
        return redirect(url_for("auth.login"))

    db = get_db()
    disziplin_filter = request.args.get("disziplin")
    geschlecht_filter = request.args.get("geschlecht")
    disziplinen = db.get_disziplinen()
    if not disziplin_filter and disziplinen:
        disziplin_filter = disziplinen[0]["name"]

    selected_meta = next((d for d in disziplinen if d["name"] == disziplin_filter), None)
    riegen = db.get_all_riegen_with_progress(disziplin=disziplin_filter)
    stats = db.get_stats()
    bestenliste = []
    if disziplin_filter:
        bestenliste = db.get_bestenliste(disziplin_filter, limit=20, geschlecht=geschlecht_filter)

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
    if not _require_dashboard_access():
        return redirect(url_for("auth.login"))

    db = get_db()
    disziplinen = db.get_disziplinen()
    stats = db.get_stats()

    selected_disziplin = request.args.get("disziplin")
    if not selected_disziplin and disziplinen:
        selected_disziplin = disziplinen[0]["name"]

    bestenliste = []
    if selected_disziplin:
        geschlecht_filter = request.args.get("geschlecht")
        bestenliste = db.get_bestenliste(selected_disziplin, limit=20, geschlecht=geschlecht_filter)

    return render_template(
        "stats.html",
        disziplinen=disziplinen,
        stats=stats,
        bestenliste=bestenliste,
        selected_disziplin=selected_disziplin,
    )


@auth_bp.route("/stats/bestenliste", methods=["GET"])
def stats_bestenliste():
    if not _require_dashboard_access():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    disziplin = request.args.get("disziplin")
    if not disziplin:
        return jsonify({"error": "disziplin Parameter erforderlich"}), 400

    geschlecht = request.args.get("geschlecht")
    limit = int(request.args.get("limit", 20))

    bestenliste = db.get_bestenliste(disziplin, limit=limit, geschlecht=geschlecht)
    return jsonify({"bestenliste": bestenliste, "disziplin": disziplin})
