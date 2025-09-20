from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
import backend.backend as backend
from backend.backend import RiegenManager
from app import get_db_path

# Blueprint für Authentifizierung und Admin-Bereich
auth_bp = Blueprint('auth', __name__)

# Einfache Passwörter für Demo/Tests (in Produktion durch sichere Prüfung ersetzen)
PASSWORD_LOGIN = "login"   # normales Stations-Login
PASSWORD_ADMIN = "admin"   # Admin-Login für Riegenverwaltung

def get_template_data():
    """Stellt Basis-Daten für Templates bereit (Riegenführer, Disziplinen, Fortschrittszähler aus der Session)."""
    db = backend.Backend(get_db_path())
    riegen_liste = [r for r in db.get_riegenfuehrer_liste() if r is not None and str(r).strip().lower() != 'none' and str(r).strip() != '']
    disziplinen = ["Laufen", "Sprung", "Wurf", "Ausdauer"]  # Standard-Disziplinen

    return {
        'riegenfuehrer': riegen_liste,
        'disziplin': disziplinen,
        'runde1_fertig': session.get('runde1_fertig', 0),
        'runde2_fertig': session.get('runde2_fertig', 0),
        'runde3_fertig': session.get('runde3_fertig', 0),
        'schueler_gesamt': session.get('schueler_gesamt', 0),
        'schueler_abwesend': session.get('schueler_abwesend', 0),
        'ipad_stations_nummer': session.get('ipad_stations_nummer'),
        'station': session.get('station')
    }

@auth_bp.route("/")
def index():
    """Startseite: zeigt Hauptansicht oder leitet zum Login um."""
    # Startseite - prüft ob Nutzer eingeloggt ist
    if session.get('logged_in'):
        return render_template("index.html", **get_template_data())
    else:
        return redirect(url_for('auth.login'))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login-Route: unterscheidet zwischen Stations-Login und Admin-Login."""
    # Hier meldet sich der Nutzer an
    if request.method == "POST":
        password = request.form.get("password")
        if password == PASSWORD_LOGIN:
            # Stations-Login: iPad-Nummer und Station erforderlich
            station_num = request.form.get("ipad_stations_nummer")
            station = request.form.get("station")
            if not station_num or not station:
                return render_template("login.html", error="Bitte iPad-Nummer und Station angeben (Stations-Login).")
            session['logged_in'] = True
            session['ipad_stations_nummer'] = station_num
            session['station'] = station
            session['disziplin'] = station
            return render_template("index.html", **get_template_data())
        elif password == PASSWORD_ADMIN:
            session['logged_in'] = True
            session['is_admin'] = True
            # Admin-Ansicht anzeigen mit Riegen-Daten
            riegen_manager = RiegenManager(get_db_path())
            riegenfuehrer_list = riegen_manager.get_all_riegenfuehrer()
            statistics = riegen_manager.get_riegen_statistics()
            riegen_manager.close()

            return render_template("admin.html",
                                 riegenfuehrer=riegenfuehrer_list,
                                 statistics=statistics)
        else:
            # Falsches Passwort
            return render_template("login.html", error="Falsches Passwort!")
    # Login-Seite anzeigen
    return render_template("login.html")

@auth_bp.route("/logout", methods=["GET"])
def logout():
    """Beendet die Sitzung und zeigt die Login-Seite an."""
    # Nutzer abmelden
    session.clear()
    return render_template("login.html")

@auth_bp.route("/admin/add_riegenfuehrer", methods=["POST"])
def add_riegenfuehrer():
    """Fügt einen neuen Riegenführer hinzu"""
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    name = request.form.get('name')
    geschlecht = request.form.get('geschlecht')
    profil = request.form.get('profil') == 'true'
    stufe = int(request.form.get('stufe'))
    klassenendungen = request.form.get('klassenendungen').split(',')
    klassenendungen = [k.strip() for k in klassenendungen if k.strip()]

    riegen_manager = RiegenManager(get_db_path())
    success = riegen_manager.add_riegenfuehrer(name, geschlecht, profil, stufe, klassenendungen)
    riegen_manager.close()

    if success:
        flash(f'Riegenführer {name} wurde erfolgreich hinzugefügt!', 'success')
    else:
        flash(f'Fehler: Riegenführer {name} existiert bereits!', 'error')

    return redirect(url_for('auth.admin_panel'))

@auth_bp.route("/admin/delete_riegenfuehrer/<int:riegenfuehrer_id>", methods=["POST"])
def delete_riegenfuehrer(riegenfuehrer_id):
    """Löscht einen Riegenführer"""
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    riegen_manager = RiegenManager(get_db_path())
    riegen_manager.delete_riegenfuehrer(riegenfuehrer_id)
    riegen_manager.close()

    flash('Riegenführer wurde erfolgreich gelöscht!', 'success')
    return redirect(url_for('auth.admin_panel'))

@auth_bp.route("/admin/assign_riegen", methods=["POST"])
def assign_riegen():
    """Teilt alle Schüler automatisch in Riegen ein"""
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    riegen_manager = RiegenManager(get_db_path())
    success = riegen_manager.assign_riegen_automatically()
    riegen_manager.close()

    if success:
        flash('Riegen wurden erfolgreich automatisch eingeteilt!', 'success')
    else:
        flash('Fehler bei der automatischen Riegen-Einteilung!', 'error')

    return redirect(url_for('auth.admin_panel'))

@auth_bp.route("/admin/import_csv", methods=["POST"])
def import_csv():
    """Importiert Daten aus der CSV-Datei und erstellt eine neue Datenbank"""
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    try:
        # CSV-Import durchführen
        success = backend.initialize_database_from_csv('backend/Mappe1.csv', get_db_path())

        if success:
            flash('Datenbank wurde erfolgreich aus der CSV-Datei erstellt!', 'success')
        else:
            flash('Fehler beim Import der CSV-Datei!', 'error')
    except Exception as e:
        flash(f'Fehler beim CSV-Import: {str(e)}', 'error')

    return redirect(url_for('auth.admin_panel'))

@auth_bp.route("/admin")
def admin_panel():
    """Admin-Panel mit Riegen-Verwaltung"""
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    riegen_manager = RiegenManager(get_db_path())
    riegenfuehrer_list = riegen_manager.get_all_riegenfuehrer()
    statistics = riegen_manager.get_riegen_statistics()
    riegen_manager.close()

    return render_template("admin.html",
                         riegenfuehrer=riegenfuehrer_list,
                         statistics=statistics)
