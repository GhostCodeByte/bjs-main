from flask import Blueprint, redirect, render_template, session, url_for, request, jsonify
from app import get_db

input_bp = Blueprint('input', __name__, template_folder='../templates')


def update_schueler_liste(schueler_liste):
    db = get_db()
    discipline = session.get('discipline')

    for schueler in schueler_liste:
        schueler_id = schueler['SchuelerID']
        rounds_done = db.get_rounds_done(schueler_id, discipline)

        for ergebnis_nr, status in rounds_done:
            if ergebnis_nr == 1:
                schueler['Round1'] = status
            elif ergebnis_nr == 2:
                schueler['Round2'] = status
            elif ergebnis_nr == 3:
                schueler['Round3'] = status

    print(schueler_liste)
    return schueler_liste


def update_status_liste(schueler_liste):
    def to_symbol(val):
        if val is None:
            return "⬜"
        if val == "ABWESEND":
            return "❌"
        # bei jedem anderen String (OK-Fall mit Wert) -> Häkchen
        return "✅"

    status_list = []
    for schueler in schueler_liste:
        schueler_id = schueler['SchuelerID']
        name = f"{schueler['Vorname']} {schueler['Name']}"
        rounds = [
            to_symbol(schueler.get('Round1')),
            to_symbol(schueler.get('Round2')),
            to_symbol(schueler.get('Round3')),
        ]
        status_list.append(f"{schueler_id}: {name} {''.join(rounds)}")
    return status_list


def build_status_list_from_session():
    """
    Aktualisiert die in der Session gespeicherte Schülerliste aus der DB
    und gibt die formatierte Statusliste für das Dropdown zurück.
    """
    schueler_liste = session.get('schueler', [])
    if not schueler_liste:
        return []
    schueler_liste = update_schueler_liste(schueler_liste)
    session['schueler'] = schueler_liste
    return update_status_liste(schueler_liste)


@input_bp.route('/input')
def input_page():
    db = get_db()

    if not session.get("is_logged_in"):
        return redirect(url_for('auth.login'))

    session["is_logged_in"] = False

    return render_template(
        'input.html',
        riegenfuehrer=db.get_riegenfuehrer(),
        station='Laufen',
        ipad_stations_nummer='1',
        runde1_fertig=0,
        runde2_fertig=0,
        runde3_fertig=0,
        schueler_gesamt=0,
        schueler_abwesend=0
    )


@input_bp.route('/get_riege', methods=['POST'])
def get_riege():
    data = request.get_json()
    riegenfuehrer_id = data.get('riegenfuehrer_id')
    db = get_db()

    schueler_liste = db.get_riege(riegenfuehrer_id)

    session['schueler'] = schueler_liste

    status_list = build_status_list_from_session()
    return jsonify(status_list)


@input_bp.route('/next_student', methods=['POST'])
def next_student():
    data = request.get_json()
    schueler_id = data.get('schueler_id')
    ergebnis = data.get('ergebnis')
    round = data.get('round')

    db = get_db()

    db.add_entry(
        schueler_id=schueler_id,
        disziplin=session.get('discipline'),
        ergebnis_nr=round,
        result_value=ergebnis,
        status='OK',
        source_ipad_number=1,
        source_station=1
    )

    status_list = build_status_list_from_session()

    return jsonify(status_list)
