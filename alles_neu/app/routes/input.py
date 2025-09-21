from flask import Blueprint, render_template, session

input_bp = Blueprint('input', __name__, template_folder='../templates')

@input_bp.route('/input')
def input_page():
    session["is_logged_in"] = False
    return render_template(
        'input.html',
        riegenfuehrer=['Beispiel Riege 1', 'Beispiel Riege 2'],
        station='Laufen',
        ipad_stations_nummer='1',
        runde1_fertig=0,
        runde2_fertig=0,
        runde3_fertig=0,
        schueler_gesamt=0,
        schueler_abwesend=0
    )