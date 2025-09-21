from flask import Blueprint, redirect, render_template, session, url_for
from app import get_db
input_bp = Blueprint('input', __name__, template_folder='../templates')

@input_bp.route('/input')
def input_page():

    db = get_db()

    if session.get("is_logged_in") is False or session.get("is_logged_in") is None:
        return redirect(url_for('auth.login'))
    
    session["is_logged_in"] = False

    return render_template(
        'input.html',
        riegenfuehrer = db.get_riegenfuehrer(),
        station = 'Laufen',
        ipad_stations_nummer = '1',
        runde1_fertig = 0,
        runde2_fertig = 0,
        runde3_fertig = 0,
        schueler_gesamt = 0,
        schueler_abwesend = 0
    )