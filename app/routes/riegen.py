from flask import Blueprint, session, jsonify, g, request
import backend.backend as backend
from app import get_db_path

riegen_bp = Blueprint('riegen', __name__)

@riegen_bp.route("/get_riege", methods=["GET"])
def get_riege():
    """Lädt die Riege/Disziplin, setzt Session-Zustand zurück und liefert Schüler- und Statusdaten als JSON für das Frontend."""
    # Holt die Schülerdaten für die gewählte Riege und Disziplin
    session['riegenfuehrer'] = request.args.get("riegenfuehrer")
    if session["station"]:
        session["disziplin"] = session.get('station')
    else:
        return jsonify({"status": "error", "message": "Keine Station gesetzt. Bitte auf der Login-Seite Station wählen.", "show_popup": True})

    # Zähler und Session-Cache zurücksetzen (für Fortschritts- und Abwesenheitsanzeigen)
    session['schueler_daten'] = []
    session['schueler_gesamt'] = 0
    session['schueler_fertig'] = 0
    session['schueler_abwesend'] = 0
    session['runde1_fertig'] = 0
    session['runde2_fertig'] = 0
    session['runde3_fertig'] = 0

    db = g.get('db', backend.Backend(get_db_path()))
    schueler_daten = db.get_schueler_from_riege(session.get('riegenfuehrer'), session.get('disziplin'))
    schueler_namen = [f"{row[3]} {row[4]}" for row in schueler_daten]
    # Struktur der schueler_status-Zeilen:
    # [0]=Klasse, [1]=Klassenbuchstabe, [2]=Geschlecht, [3]=Name, [4]=Vorname, [5]=SchuelerID,
    # [6]=Runde1 fertig, [7]=Runde2 fertig, [8]=Runde3 fertig, [9]=Abwesend, [10]=Ergebnis1, [11]=Ergebnis2, [12]=Ergebnis3
    # Runde-Status und Werte aus den neuesten Einträgen je Runde berechnen
    latest_rows = db.get_latest_results_for_riege(session.get('riegenfuehrer'), session.get('disziplin'))
    latest_map = {
        r[0]: {
            "r1_value": r[3], "r1_status": r[4],
            "r2_value": r[5], "r2_status": r[6],
            "r3_value": r[7], "r3_status": r[8],
        }
        for r in latest_rows
    }

    schueler_status = []
    for row in schueler_daten:
        sid = row[5]
        meta = latest_map.get(sid, {})
        r1_ok = meta.get("r1_status") == "OK"
        r2_ok = meta.get("r2_status") == "OK"
        r3_ok = meta.get("r3_status") == "OK"
        v1 = meta.get("r1_value") if meta.get("r1_value") is not None else 0
        v2 = meta.get("r2_value") if meta.get("r2_value") is not None else 0
        v3 = meta.get("r3_value") if meta.get("r3_value") is not None else 0

        schueler_status.append([
            row[0], row[1], row[2], row[3], row[4], sid,
            r1_ok, r2_ok, r3_ok,
            row[9],
            v1, v2, v3
        ])

    runde1_count = sum(1 for student in schueler_status if student[6])
    runde2_count = sum(1 for student in schueler_status if student[7])
    runde3_count = sum(1 for student in schueler_status if student[8])
    komplett_fertig = sum(1 for student in schueler_status if student[6] and student[7] and student[8])
    schueler_gesamt = len(schueler_status)
    schueler_abwesend = sum(1 for student in schueler_status if student[9])

    # Speichert die Daten für spätere Nutzung
    session['schueler_daten'] = schueler_status
    session['schueler_gesamt'] = schueler_gesamt
    session['schueler_abwesend'] = schueler_abwesend
    session['schueler_fertig'] = komplett_fertig
    session['runde1_fertig'] = runde1_count
    session['runde2_fertig'] = runde2_count
    session['runde3_fertig'] = runde3_count

    # Antwortpayload für das Frontend (wird von JavaScript ausgewertet)
    response = {
        "status": "success",
        "runde1_fertig": runde1_count,
        "runde2_fertig": runde2_count,
        "runde3_fertig": runde3_count,
        "schueler_gesamt": schueler_gesamt,
        "schueler_abwesend": schueler_abwesend,
        "riegenfuehrer": session.get('riegenfuehrer'),
        "disziplin": session.get('disziplin'),
        "schueler": schueler_namen,
        "schueler_daten": schueler_status,
        "klassen": sorted(set(f"{row[0]}{row[1]}" for row in schueler_daten)),
        "geschlechter": sorted(set(row[2] for row in schueler_daten)),
        "auto_select_first": schueler_namen[0] if schueler_namen else None,
        "auto_select_first_id": schueler_status[0][5] if schueler_status else None,
        "schueler_ids": {student[3] + " " + student[4]: student[5] for student in schueler_status},
        "rundenstatus": {student[3] + " " + student[4]: {
            "runde1_fertig": bool(student[6]),
            "runde2_fertig": bool(student[7]),
            "runde3_fertig": bool(student[8])
        } for student in schueler_status},
        "ergebnisse": {student[3] + " " + student[4]: {
            "runde1": student[10] if student[10] != 0 else "",
            "runde2": student[11] if student[11] != 0 else "",
            "runde3": student[12] if student[12] != 0 else ""
        } for student in schueler_status},
        "abwesenheit": {student[3] + " " + student[4]: student[9] for student in schueler_status},
        "debug": {
            "first_student": schueler_status[0] if schueler_status else None,
            "second_student": schueler_status[1] if len(schueler_status) > 1 else None,
            "index_mapping": {
                "runde1_fertig": 6,
                "runde2_fertig": 7,
                "runde3_fertig": 8,
                "abwesend": 9,
                "ergebnis1": 10,
                "ergebnis2": 11,
                "ergebnis3": 12
            }
        },
    }
    return jsonify(response)
