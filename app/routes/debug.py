from flask import Blueprint, session, jsonify, request, g
import backend.backend as backend
from app import get_db_path

# Blueprint für Debug-Endpunkte (nur in der Entwicklung nützlich)
debug_bp = Blueprint('debug', __name__)

@debug_bp.route("/debug_db", methods=["GET"])
def debug_db():
    """Debug-Endpoint: Zeigt eine Vorschau aus der Tabelle Schueler_Disziplin sowie die Spaltennamen."""
    # Zeigt Datenbank-Inhalte
    if not session.get('logged_in'):
        return jsonify({"error": "Nicht eingeloggt"})
    db = g.get('db', backend.Backend(get_db_path()))
    db.cursor.execute("SELECT * FROM Schueler_Disziplin WHERE Disziplin = ? LIMIT 10", (session.get('disziplin', 'Laufen'),))
    disziplin_data = db.cursor.fetchall()
    db.cursor.execute("PRAGMA table_info(Schueler_Disziplin)")
    columns = [row[1] for row in db.cursor.fetchall()]
    return jsonify({"disziplin": session.get('disziplin'), "columns": columns, "data": disziplin_data})

@debug_bp.route("/debug_post_data", methods=["POST"])
def debug_post_data():
    """Debug-Endpoint: Gibt gesendete POST-/Query-Daten sowie einige Session-Infos zurück."""
    # Zeigt alle gesendeten POST-Daten
    if not session.get('logged_in'):
        return jsonify({"error": "Nicht eingeloggt"})
    form_data = dict(request.form)
    args_data = dict(request.args)
    return jsonify({
        "form_data": form_data,
        "args_data": args_data,
        "method": request.method,
        "content_type": request.content_type,
        "session_schueler_daten_count": len(session.get('schueler_daten', [])),
        "first_student_info": {
            "name": f"{session.get('schueler_daten', [[]])[0][3]} {session.get('schueler_daten', [[]])[0][4]}" if session.get('schueler_daten') else None,
            "id": session.get('schueler_daten', [[]])[0][5] if session.get('schueler_daten') else None
        } if session.get('schueler_daten') else None
    })

@debug_bp.route("/debug_current_session", methods=["GET"])
def debug_current_session():
    """Debug-Endpoint: Liefert einen Überblick über den aktuellen Session-Zustand (Auszug)."""
    # Zeigt aktuelle Session-Daten
    if not session.get('logged_in'):
        return jsonify({"error": "Nicht eingeloggt"})
    schueler_daten = session.get('schueler_daten', [])
    first_3_students = schueler_daten[:3] if schueler_daten else []
    return jsonify({
        "session_keys": list(session.keys()),
        "riegenfuehrer": session.get('riegenfuehrer'),
        "disziplin": session.get('disziplin'),
        "schueler_gesamt": session.get('schueler_gesamt', 0),
        "first_3_students": first_3_students,
        "student_structure_example": {
            "index_0_klasse": first_3_students[0][0] if first_3_students else None,
            "index_5_schueler_id": first_3_students[0][5] if first_3_students else None,
            "index_9_abwesend": first_3_students[0][9] if first_3_students else None
        } if first_3_students else None
    })

@debug_bp.route("/debug_frontend_data", methods=["GET"])
def debug_frontend_data():
    """Debug-Endpoint: Zeigt Beispiel-Datensätze in der Struktur, wie sie ans Frontend geliefert werden."""
    # Zeigt die Daten, die ans Frontend gesendet werden
    if not session.get('logged_in'):
        return jsonify({"error": "Nicht eingeloggt"})
    if not session.get('riegenfuehrer') or not session.get('disziplin'):
        return jsonify({"error": "Keine Riege/Disziplin geladen"})
    db = g.get('db', backend.Backend(get_db_path()))
    schueler_daten = db.get_schueler_from_riege(session.get('riegenfuehrer'), session.get('disziplin'))
    debug_data = []
    for i, row in enumerate(schueler_daten[:3]):
        debug_data.append({
            "raw_db_data": row,
            "name": f"{row[3]} {row[4]}",
            "runde1_fertig": row[6],
            "runde2_fertig": row[7],
            "runde3_fertig": row[8],
            "ergebnis1": row[10],
            "ergebnis2": row[11],
            "ergebnis3": row[12],
            "indexes": {
                "runde1_index": 6,
                "runde2_index": 7,
                "runde3_index": 8,
                "ergebnis1_index": 10,
                "ergebnis2_index": 11,
                "ergebnis3_index": 12
            }
        })
    return jsonify({"riegenfuehrer": session.get('riegenfuehrer'), "disziplin": session.get('disziplin'), "debug_data": debug_data})
