from app import get_db
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

input_bp = Blueprint("input", __name__, template_folder="../templates")


def update_schueler_liste(schueler_liste):
    db = get_db()
    discipline = session.get("discipline")

    for schueler in schueler_liste:
        schueler_id = schueler["SchuelerID"]
        rounds_done = db.get_rounds_done(schueler_id, discipline)

        for ergebnis_nr, status in rounds_done:
            if ergebnis_nr == 1:
                schueler["Round1"] = status
            elif ergebnis_nr == 2:
                schueler["Round2"] = status
            elif ergebnis_nr == 3:
                schueler["Round3"] = status

    return schueler_liste


def update_status_liste(schueler_liste):
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
        rounds_raw = [
            schueler.get("Round1"),
            schueler.get("Round2"),
            schueler.get("Round3"),
        ]
        rounds = [to_symbol(val) for val in rounds_raw]
        absent = any(val == "ABWESEND" for val in rounds_raw)
        completed = all(val not in (None, "ABWESEND") for val in rounds_raw)
        status_list.append(
            {
                "id": schueler_id,
                "label": f"{schueler_id}: {name} {''.join(rounds)}",
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
        total_seconds = int(minutes) * 60 + seconds_int
        return True, float(total_seconds), ""
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return False, None, "Ungültiges Ergebnisformat"
    if number < 0:
        return False, None, "Ergebnis darf nicht negativ sein"
    return True, number, ""


def _require_round_number(round_nr):
    try:
        round_int = int(round_nr)
    except (TypeError, ValueError):
        return None
    if round_int not in (1, 2, 3):
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


def _compute_progress(schueler_liste):
    progress = {
        "total": len(schueler_liste),
        "absent": 0,
        "rounds_done": {1: 0, 2: 0, 3: 0},
    }
    for schueler in schueler_liste:
        absent_for_student = False
        for round_nr in (1, 2, 3):
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


def build_status_payload(last_saved=None):
    """
    Aktualisiert die in der Session gespeicherte Schülerliste aus der DB
    und gibt eine strukturierte Payload mit Statusliste und Fortschritt zurück.
    """
    progress_empty = {"total": 0, "absent": 0, "rounds_done": {1: 0, 2: 0, 3: 0}}
    discipline = session.get("discipline")
    if not (schueler_liste := session.get("schueler", [])):
        return {
            "status_list": [],
            "progress": progress_empty,
            "last_saved": last_saved,
            "meta": {
                "discipline": discipline,
                "total": 0,
                "active_total": 0,
                "all_completed": False,
            },
        }
    schueler_liste = update_schueler_liste(schueler_liste)
    session["schueler"] = schueler_liste
    status_list = update_status_liste(schueler_liste)
    progress = _compute_progress(schueler_liste)
    active_total = max(progress["total"] - progress["absent"], 0)
    all_completed = active_total > 0 and progress["rounds_done"][3] >= active_total
    remaining_active = max(active_total - progress["rounds_done"][3], 0)
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

    return render_template(
        "input.html",
        riegenfuehrer=db.get_riegenfuehrer(),
        station="Laufen",
        ipad_stations_nummer="1",
        runde1_fertig=0,
        runde2_fertig=0,
        runde3_fertig=0,
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
    payload = build_status_payload(
        last_saved={
            "schueler_id": schueler_id,
            "round": round_nr,
            "status": "OK",
            "value": normalized_value,
        }
    )

    return jsonify(payload)


@input_bp.route("/mark_absent", methods=["POST"])
def mark_absent():
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    schueler_id = data.get("schueler_id")
    round_nr = _require_round_number(data.get("round"))
    discipline = session.get("discipline")

    if not schueler_id or round_nr is None:
        return jsonify({"error": "schueler_id und round erforderlich"}), 400
    if not discipline:
        return jsonify({"error": "disziplin nicht gesetzt"}), 400

    db = get_db()
    try:
        db.add_entry(
            schueler_id=schueler_id,
            disziplin=discipline,
            ergebnis_nr=round_nr,
            result_value=None,
            status="ABWESEND",
            source_ipad_number=1,
            source_station=1,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    _update_round_cache_in_session(schueler_id, round_nr, "ABWESEND")
    payload = build_status_payload(
        last_saved={
            "schueler_id": schueler_id,
            "round": round_nr,
            "status": "ABWESEND",
            "value": None,
        }
    )

    return jsonify(payload)
