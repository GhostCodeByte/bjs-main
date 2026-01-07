from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import get_db
from app.db_registry import DbRegistry, default_meta_db_path

input_bp = Blueprint("input", __name__, template_folder="../templates")


def _get_registry() -> DbRegistry:
    return DbRegistry(default_meta_db_path(Path(current_app.root_path).parent.parent))


def update_schueler_liste(schueler_liste, num_rounds=3):
    db = get_db()
    if db is None:
        return schueler_liste
    discipline = session.get("discipline")

    for schueler in schueler_liste:
        schueler_id = schueler["SchuelerID"]
        rounds_done = db.get_rounds_done(schueler_id, discipline)

        for ergebnis_nr, status in rounds_done:
            if 1 <= ergebnis_nr <= num_rounds:
                schueler[f"Round{ergebnis_nr}"] = status

    return schueler_liste


def update_status_liste(schueler_liste, num_rounds=3):
    def to_symbol(val):
        if val is None:
            return "⬜"
        if val == "ABWESEND":
            return "❌"
        return "✅"

    status_list = []
    for schueler in schueler_liste:
        schueler_id = schueler["SchuelerID"]
        name = f"{schueler['Vorname']} {schueler['Name']}"
        rounds_raw = [schueler.get(f"Round{i}") for i in range(1, num_rounds + 1)]
        rounds = [to_symbol(val) for val in rounds_raw]
        absent = any(val == "ABWESEND" for val in rounds_raw)
        completed = all(val not in (None, "ABWESEND") for val in rounds_raw)
        status_list.append(
            {
                "id": schueler_id,
                "name": name,
                "rounds": rounds,
                "round_values": rounds_raw,
                "absent": absent,
                "completed": completed,
            }
        )
    return status_list


def _validate_and_normalize_result(ergebnis: str, discipline: str):
    if ergebnis is None:
        return False, None, "Ergebnis erforderlich"
    value = str(ergebnis).strip()
    if not value:
        return False, None, "Ergebnis erforderlich"
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            return False, None, "Zeitformat mm:ss erforderlich"
        minutes, seconds = parts
        if not minutes.isdigit() or not seconds.isdigit():
            return False, None, "Zeitformat nur Ziffern erlaubt"
        seconds_int = int(seconds)
        if seconds_int >= 60:
            return False, None, "Sekunden müssen < 60 sein"
        # Speichere als String mm:ss
        return True, f"{int(minutes):02d}:{seconds_int:02d}", ""
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return False, None, "Ungültiges Ergebnisformat"
    if number < 0:
        return False, None, "Ergebnis darf nicht negativ sein"
    return True, number, ""


def _require_round_number(round_nr, max_rounds=5):
    try:
        round_int = int(round_nr)
    except (TypeError, ValueError):
        return None
    if round_int < 1 or round_int > max_rounds:
        return None
    return round_int


def _update_round_cache_in_session(schueler_id, round_nr, value):
    schueler_liste = session.get("schueler", [])
    key = f"Round{round_nr}"
    updated = False
    for schueler in schueler_liste:
        if schueler.get("SchuelerID") == schueler_id:
            schueler[key] = value
            updated = True
            break
    if updated:
        session["schueler"] = schueler_liste


def _compute_progress(schueler_liste, num_rounds=3):
    progress = {
        "total": len(schueler_liste),
        "absent": 0,
        "rounds_done": {i: 0 for i in range(1, num_rounds + 1)},
    }
    for schueler in schueler_liste:
        absent_for_student = False
        for round_nr in range(1, num_rounds + 1):
            val = schueler.get(f"Round{round_nr}")
            if val == "ABWESEND":
                absent_for_student = True
            if val not in (None, "ABWESEND"):
                progress["rounds_done"][round_nr] += 1
        if absent_for_student:
            progress["absent"] += 1
    return progress


def _collect_meta_data(schueler_liste):
    gender_counts = {}
    age_buckets = {}
    class_buckets = {}
    profile_counts = {"profil": 0, "kein_profil": 0, "unbekannt": 0}
    for schueler in schueler_liste:
        gender = (schueler.get("Geschlecht") or "unbekannt").strip()
        gender_counts[gender] = gender_counts.get(gender, 0) + 1

        age = schueler.get("Bundesjugendspielalter")
        if age is not None:
            age_buckets[age] = age_buckets.get(age, 0) + 1

        klasse = schueler.get("Klasse")
        if klasse is not None:
            class_buckets[klasse] = class_buckets.get(klasse, 0) + 1

        profil_flag = schueler.get("Profil")
        if profil_flag is True:
            profile_counts["profil"] += 1
        elif profil_flag is False:
            profile_counts["kein_profil"] += 1
        else:
            profile_counts["unbekannt"] += 1

    return {
        "gender_counts": gender_counts,
        "age_buckets": age_buckets,
        "class_buckets": class_buckets,
        "profile_counts": profile_counts,
    }


def _get_num_rounds_for_discipline(discipline):
    """Holt die Anzahl der Runden für eine Disziplin aus der Registry."""
    if not discipline:
        return 3
    registry = _get_registry()
    disziplin = registry.get_disziplin_by_name(discipline)
    if disziplin:
        return disziplin.num_rounds
    return 3


def build_status_payload(last_saved=None):
    """
    Aktualisiert die in der Session gespeicherte Schülerliste aus der DB
    und gibt eine strukturierte Payload mit Statusliste und Fortschritt zurück.
    """
    discipline = session.get("discipline")
    num_rounds = _get_num_rounds_for_discipline(discipline)
    progress_empty = {
        "total": 0,
        "absent": 0,
        "rounds_done": {i: 0 for i in range(1, num_rounds + 1)},
    }

    if not (schueler_liste := session.get("schueler", [])):
        return {
            "status_list": [],
            "progress": progress_empty,
            "last_saved": last_saved,
            "meta": {
                "discipline": discipline,
                "num_rounds": num_rounds,
                "total": 0,
                "active_total": 0,
                "all_completed": False,
            },
        }
    schueler_liste = update_schueler_liste(schueler_liste, num_rounds)
    session["schueler"] = schueler_liste
    status_list = update_status_liste(schueler_liste, num_rounds)
    progress = _compute_progress(schueler_liste, num_rounds)
    active_total = max(progress["total"] - progress["absent"], 0)
    # all_completed wenn die letzte Runde für alle aktiven Schüler fertig ist
    all_completed = (
        active_total > 0 and progress["rounds_done"].get(num_rounds, 0) >= active_total
    )
    remaining_active = max(active_total - progress["rounds_done"].get(num_rounds, 0), 0)
    demographics = _collect_meta_data(schueler_liste)
    first_student = schueler_liste[0] if schueler_liste else {}
    first_class = None
    if first_student:
        klasse_val = first_student.get("Klasse")
        klassenbuchstabe = first_student.get("Klassenbuchstabe") or ""
        if klasse_val is not None:
            first_class = f"{klasse_val}{klassenbuchstabe}"
    first_profile = first_student.get("Profil") if first_student else None
    meta = {
        "discipline": discipline,
        "num_rounds": num_rounds,
        "total": progress["total"],
        "active_total": active_total,
        "remaining_active": remaining_active,
        "all_completed": all_completed,
        "completion_message": "Alle Ergebnisse erfasst."
        if all_completed
        else f"Noch {remaining_active} Ergebnisse offen.",
        "gender_counts": demographics.get("gender_counts"),
        "age_buckets": demographics.get("age_buckets"),
        "class_buckets": demographics.get("class_buckets"),
        "profile_counts": demographics.get("profile_counts"),
        "first_gender": first_student.get("Geschlecht") if first_student else None,
        "first_class": first_class,
        "first_profile": first_profile,
    }
    return {
        "status_list": status_list,
        "progress": progress,
        "last_saved": last_saved,
        "meta": meta,
    }


@input_bp.route("/input")
def input_page():
    if not session.get("is_logged_in") or session.get("role") != "station":
        return redirect(url_for("auth.login"))

    db = get_db()
    if db is None:
        session.clear()
        return redirect(url_for("auth.login"))

    discipline = session.get("discipline")
    num_rounds = _get_num_rounds_for_discipline(discipline)

    # Disziplin-Info aus Registry
    registry = _get_registry()
    disziplin_info = registry.get_disziplin_by_name(discipline) if discipline else None

    return render_template(
        "input.html",
        riegenfuehrer=db.get_riegenfuehrer(),
        station=disziplin_info.name if disziplin_info else discipline or "Station",
        discipline=discipline,
        num_rounds=num_rounds,
        ipad_stations_nummer="1",
        schueler_gesamt=0,
        schueler_abwesend=0,
    )


@input_bp.route("/get_riege", methods=["POST"])
def get_riege():
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    riegenfuehrer_id = data.get("riegenfuehrer_id")
    if not riegenfuehrer_id:
        return jsonify({"error": "riegenfuehrer_id fehlt"}), 400

    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    schueler_liste = db.get_riege(riegenfuehrer_id)
    session["schueler"] = schueler_liste

    payload = build_status_payload()
    return jsonify(payload)


@input_bp.route("/next_student", methods=["POST"])
def next_student():
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    schueler_id = data.get("schueler_id")
    ergebnis = data.get("ergebnis")
    round_nr = _require_round_number(data.get("round"))
    discipline = session.get("discipline")

    if not schueler_id or round_nr is None:
        return jsonify({"error": "schueler_id und round erforderlich"}), 400
    if not discipline:
        return jsonify({"error": "disziplin nicht gesetzt"}), 400

    ok, normalized_value, err = _validate_and_normalize_result(ergebnis, discipline)
    if not ok:
        return jsonify({"error": err}), 400

    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    try:
        db.add_entry(
            schueler_id=schueler_id,
            disziplin=discipline,
            ergebnis_nr=round_nr,
            result_value=normalized_value,
            status="OK",
            source_ipad_number=1,
            source_station=1,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    _update_round_cache_in_session(schueler_id, round_nr, normalized_value)

    display_value = normalized_value
    if isinstance(normalized_value, float):
        display_value = f"{normalized_value:.2f}".replace(".", ",")

    payload = build_status_payload(
        last_saved={
            "schueler_id": schueler_id,
            "round": round_nr,
            "status": "OK",
            "value": display_value,
        }
    )

    return jsonify(payload)


@input_bp.route("/get_current_result", methods=["GET"])
def get_current_result():
    """Holt das aktuelle Ergebnis für einen Schüler und eine Runde."""
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    schueler_id = request.args.get("schueler_id")
    runde = request.args.get("runde")
    discipline = session.get("discipline")

    if not schueler_id or not runde:
        return jsonify({"has_result": False, "result": "NA"})

    try:
        runde_int = int(runde)
    except (TypeError, ValueError):
        return jsonify({"has_result": False, "result": "NA"})

    if not discipline:
        return jsonify({"has_result": False, "result": "NA"})

    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503

    # Hole alle Runden für diesen Schüler
    rounds_done = db.get_rounds_done(schueler_id, discipline)

    # Suche nach der gewünschten Runde
    for ergebnis_nr, value in rounds_done:
        if ergebnis_nr == runde_int:
            if value == "ABWESEND":
                return jsonify({"has_result": True, "result": "ABWESEND"})
            elif value is not None:
                # Formatiere das Ergebnis
                if isinstance(value, float):
                    return jsonify(
                        {"has_result": True, "result": f"{value:.2f}".replace(".", ",")}
                    )
                return jsonify({"has_result": True, "result": str(value)})
            break

    return jsonify({"has_result": False, "result": "NA"})


@input_bp.route("/mark_absent", methods=["POST"])
def mark_absent():
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    schueler_id = data.get("schueler_id")
    round_nr = data.get(
        "round"
    )  # Optional - wenn nicht angegeben, alle Runden als abwesend
    discipline = session.get("discipline")

    if not schueler_id:
        return jsonify({"error": "schueler_id erforderlich"}), 400
    if not discipline:
        return jsonify({"error": "disziplin nicht gesetzt"}), 400

    num_rounds = _get_num_rounds_for_discipline(discipline)

    db = get_db()
    if db is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503
    try:
        if round_nr is not None:
            # Nur eine bestimmte Runde als abwesend markieren
            round_int = _require_round_number(round_nr, num_rounds)
            if round_int is None:
                return jsonify({"error": "ungültige Rundennummer"}), 400
            db.add_entry(
                schueler_id=schueler_id,
                disziplin=discipline,
                ergebnis_nr=round_int,
                result_value=None,
                status="ABWESEND",
                source_ipad_number=1,
                source_station=1,
            )
            _update_round_cache_in_session(schueler_id, round_int, "ABWESEND")
        else:
            # Alle Runden als abwesend markieren
            for r in range(1, num_rounds + 1):
                db.add_entry(
                    schueler_id=schueler_id,
                    disziplin=discipline,
                    ergebnis_nr=r,
                    result_value=None,
                    status="ABWESEND",
                    source_ipad_number=1,
                    source_station=1,
                )
                _update_round_cache_in_session(schueler_id, r, "ABWESEND")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    payload = build_status_payload(
        last_saved={
            "schueler_id": schueler_id,
            "round": round_nr if round_nr else "all",
            "status": "ABWESEND",
            "value": None,
        }
    )

    return jsonify(payload)
