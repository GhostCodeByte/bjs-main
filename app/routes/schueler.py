from flask import Blueprint, session, request, jsonify, g
import backend.backend as backend
from app import get_db_path

schueler_bp = Blueprint('schueler', __name__)

@schueler_bp.route("/next", methods=["POST"])
def next():
    """Speichert das Ergebnis einer Runde für den aktuellen Schüler und liefert aktualisierte Zähler zurück."""
    # Prüfen, ob Riege/Disziplin gesetzt ist
    if not session.get('riegenfuehrer') or not session.get('disziplin'):
        return jsonify({"status": "error", "message": "Bitte zuerst eine Riege und eine Disziplin auswählen (oben rechts).", "show_popup": True})

    schueler_daten = session.get('schueler_daten', [])
    schueler_gesamt = session.get('schueler_gesamt', 0)
    aktueller_schueler_id = request.form.get("selectedSchueler")
    selected_student_name = request.form.get("selectedStudentName")
    session['aktueller_schueler'] = aktueller_schueler_id

    # Schüler-ID ableiten, falls leer
    if aktueller_schueler_id in ['false', 'null', 'undefined', ''] or aktueller_schueler_id is None:
        if selected_student_name:
            for student in schueler_daten:
                if f"{student[3]} {student[4]}" == selected_student_name:
                    aktueller_schueler_id = str(student[5])
                    session['aktueller_schueler'] = aktueller_schueler_id
                    break
        else:
            if schueler_daten:
                aktueller_schueler_id = str(schueler_daten[0][5])
                selected_student_name = f"{schueler_daten[0][3]} {schueler_daten[0][4]}"
                session['aktueller_schueler'] = aktueller_schueler_id
        if aktueller_schueler_id in ['false', 'null', 'undefined', ''] or aktueller_schueler_id is None:
            return jsonify({"status": "error", "message": f"Ungültige Schüler-ID: '{aktueller_schueler_id}'. Bitte einen Schüler aus der Liste auswählen.", "show_popup": True})

    # Ergebnis parsen
    ergebnis = request.form.get("ergebnis")
    ergebnis_value = None
    if ergebnis and ergebnis.strip():
        # Zeitdisziplinen (mm:ss) serverseitig parsen
        disziplin_name = session.get('disziplin', '')
        is_time = isinstance(disziplin_name, str) and ('laufen' in disziplin_name.lower() or 'sprint' in disziplin_name.lower())
        if is_time:
            try:
                text = ergebnis.strip()
                if ':' in text:
                    parts = text.split(':')
                    if len(parts) != 2:
                        raise ValueError("mm:ss erwartet")
                    mm = int(parts[0])
                    ss = int(parts[1])
                    if ss < 0:
                        ss = 0
                    # Keine Kappung auf 59 Sekunden – Nutzerverantwortung
                    total_seconds = mm * 60 + ss
                    ergebnis_value = float(total_seconds)
                else:
                    # Fallback: Sekunden als Zahl erlauben (Komma oder Punkt)
                    ergebnis_value = float(text.replace(',', '.'))
            except ValueError:
                return jsonify({"status": "error", "message": f"Ungültiges Ergebnis: '{ergebnis}'. Bitte mm:ss oder eine Zahl eingeben.", "show_popup": True})
        else:
            try:
                ergebnis_value = float(ergebnis.replace(',', '.'))
            except ValueError:
                return jsonify({"status": "error", "message": f"Ungültiges Ergebnis: '{ergebnis}'. Bitte eine Zahl eingeben.", "show_popup": True})

    # Runde prüfen
    selected_round_str = str(request.form.get("selected_round"))
    if selected_round_str is None:
        return jsonify({"status": "error", "message": "Fehler: Keine Runde ausgewählt. Bitte Runde 1, 2 oder 3 wählen.", "show_popup": True})
    try:
        selected_round_int = int(selected_round_str)
        if not (1 <= selected_round_int <= 3):
            raise ValueError("Rundennummer außerhalb des Bereichs 1-3")
    except ValueError:
        return jsonify({"status": "error", "message": f"Fehler: Ungültige Rundennummer '{selected_round_str}'. Muss 1, 2 oder 3 sein.", "show_popup": True})
    selected_round_0_indexed = selected_round_int - 1

    # Speichern und Anzeige aktualisieren
    student_found_and_updated = False
    for i, schueler_record in enumerate(schueler_daten):
        if str(schueler_record[5]) == str(aktueller_schueler_id):
            db = g.get('db', backend.Backend(get_db_path()))
            schueler_id = schueler_record[5]
            disziplin = session.get('disziplin')

            if ergebnis_value is not None:
                success_result = db.insert_result_entry(
                    schueler_id,
                    disziplin,
                    selected_round_int,
                    ergebnis_value,
                    'OK',
                    session.get('ipad_stations_nummer'),
                    session.get('station')
                )
                if success_result:
                    if 0 <= selected_round_0_indexed <= 2:
                        schueler_record[6 + selected_round_0_indexed] = True
                        schueler_record[10 + selected_round_0_indexed] = ergebnis_value
                        schueler_record[9] = False
                    session['schueler_daten'] = schueler_daten
                    student_found_and_updated = True
                else:
                    return jsonify({"status": "error", "message": "Fehler beim Speichern in der Datenbank. Bitte erneut versuchen.", "show_popup": True})
            else:
                student_found_and_updated = True

            # Nächsten nicht-abwesenden Schüler ermitteln
            next_student_index = i + 1
            while next_student_index < len(schueler_daten):
                next_student = schueler_daten[next_student_index]
                if not next_student[9]:
                    session["naechster_schueler"] = f"{next_student[3]} {next_student[4]}"
                    break
                next_student_index += 1
            if next_student_index >= len(schueler_daten):
                session["naechster_schueler"] = None
            break

    # Fallback: veraltete Methode (Kompatibilität)
    if not student_found_and_updated:
        try:
            db = g.get('db', backend.Backend(get_db_path()))
            disziplin = session.get('disziplin')
            schueler_id_int = int(aktueller_schueler_id)
            success = db.update_student_round_status(schueler_id_int, disziplin, selected_round_int, True)
            if success:
                student_found_and_updated = True
            else:
                return jsonify({"status": "error", "message": f"Fehler beim Speichern für Schüler-ID {schueler_id_int}.", "show_popup": True})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Fehler: Schüler mit ID '{aktueller_schueler_id}' konnte nicht verarbeitet werden: {str(e)}", "show_popup": True})

    if not student_found_and_updated:
        return jsonify({"status": "error", "message": f"Fehler: Schüler mit der ID '{aktueller_schueler_id}' nicht gefunden.", "show_popup": True})

    # Zähler aktualisieren
    schueler_fertig_updated = sum(1 for student in schueler_daten if student[6] == True and student[7] == True and student[8] == True)
    session['schueler_fertig'] = schueler_fertig_updated
    runde1_fertig = sum(1 for student in schueler_daten if student[6] == True)
    runde2_fertig = sum(1 for student in schueler_daten if student[7] == True)
    runde3_fertig = sum(1 for student in schueler_daten if student[8] == True)
    schueler_abwesend = sum(1 for student in schueler_daten if student[9] == True)
    session['runde1_fertig'] = runde1_fertig
    session['runde2_fertig'] = runde2_fertig
    session['runde3_fertig'] = runde3_fertig
    session['schueler_abwesend'] = schueler_abwesend

    return jsonify({
        "status": "success",
        "schueler_fertig": schueler_fertig_updated,
        "schueler_gesamt": schueler_gesamt,
        "schueler_abwesend": schueler_abwesend,
        "runde1_fertig": runde1_fertig,
        "runde2_fertig": runde2_fertig,
        "runde3_fertig": runde3_fertig,
        "selected_round": selected_round_int
    })

@schueler_bp.route("/mark_absent", methods=["POST"])
def mark_absent():
    """Markiert den aktuell ausgewählten Schüler als abwesend und aktualisiert die Zähler."""
    if not session.get('riegenfuehrer') or not session.get('disziplin'):
        return jsonify({"status": "error", "message": "Bitte zuerst eine Riege und eine Disziplin auswählen (oben rechts).", "show_popup": True})

    schueler_daten = session.get('schueler_daten', [])
    schueler_gesamt = session.get('schueler_gesamt', 0)
    aktueller_schueler_id = request.form.get("selectedSchueler")
    selected_student_name = request.form.get("selectedStudentName")
    disziplin = session.get('disziplin')

    # Aktuelle Runde (vom Client) optional auswerten, Default: 1
    selected_round_str = request.form.get("selected_round")
    try:
        selected_round_int = int(selected_round_str) if selected_round_str else 1
    except (TypeError, ValueError):
        selected_round_int = 1

    # Schüler-ID ableiten, falls leer
    if aktueller_schueler_id in ['false', 'null', 'undefined', ''] or aktueller_schueler_id is None:
        if selected_student_name:
            for student in schueler_daten:
                if f"{student[3]} {student[4]}" == selected_student_name:
                    aktueller_schueler_id = str(student[5])
                    break
        else:
            if schueler_daten:
                aktueller_schueler_id = str(schueler_daten[0][5])
                selected_student_name = f"{schueler_daten[0][3]} {schueler_daten[0][4]}"

    if not aktueller_schueler_id or aktueller_schueler_id in ['false', 'null', 'undefined']:
        return jsonify({"status": "error", "message": "Kein Schüler ausgewählt oder ungültige Schüler-ID.", "show_popup": True})

    # Abwesenheit speichern und UI-Daten aktualisieren
    student_found = False
    for i, schueler_record in enumerate(schueler_daten):
        if str(schueler_record[5]) == str(aktueller_schueler_id):
            student_found = True
            db = g.get('db', backend.Backend(get_db_path()))
            schueler_id = schueler_record[5]
            student_already_absent = schueler_record[9]

            # Ergebniseintrag für Abwesenheit (runde-bezogen) erfassen
            db.insert_result_entry(
                schueler_id,
                disziplin,
                selected_round_int,
                None,
                'ABWESEND',
                session.get('ipad_stations_nummer'),
                session.get('station')
            )

            # Disziplin-weit Abwesend-Flag (Kompatibilität)
            if not student_already_absent:
                success = db.mark_student_absent(schueler_id, disziplin, True)
                if success:
                    schueler_record[9] = True
                    session['schueler_daten'] = schueler_daten
                else:
                    return jsonify({"status": "error", "message": "Fehler beim Speichern der Abwesenheit in der Datenbank.", "show_popup": True})

            # Nächsten nicht-abwesenden Schüler wählen
            next_student_index = i + 1
            while next_student_index < len(schueler_daten):
                next_student = schueler_daten[next_student_index]
                if not next_student[9]:
                    session["naechster_schueler"] = f"{next_student[3]} {next_student[4]}"
                    break
                next_student_index += 1
            if next_student_index >= len(schueler_daten):
                session["naechster_schueler"] = None
            break

    if not student_found:
        return jsonify({"status": "error", "message": f"Schüler mit der ID '{aktueller_schueler_id}' nicht gefunden.", "show_popup": True})

    # Zähler aktualisieren
    schueler_abwesend = sum(1 for student in schueler_daten if student[9] == True)
    runde1_fertig = sum(1 for student in schueler_daten if student[6] == True)
    runde2_fertig = sum(1 for student in schueler_daten if student[7] == True)
    runde3_fertig = sum(1 for student in schueler_daten if student[8] == True)
    komplett_fertig = sum(1 for student in schueler_daten if student[6] == True and student[7] == True and student[8] == True)
    session['schueler_fertig'] = komplett_fertig
    session['schueler_abwesend'] = schueler_abwesend
    session['runde1_fertig'] = runde1_fertig
    session['runde2_fertig'] = runde2_fertig
    session['runde3_fertig'] = runde3_fertig

    return jsonify({
        "status": "success",
        "message": f"Schüler mit ID '{aktueller_schueler_id}' als abwesend markiert",
        "schueler_fertig": komplett_fertig,
        "schueler_gesamt": schueler_gesamt,
        "schueler_abwesend": schueler_abwesend,
        "runde1_fertig": runde1_fertig,
        "runde2_fertig": runde2_fertig,
        "runde3_fertig": runde3_fertig,
        "naechster_schueler": session.get("naechster_schueler")
    })

@schueler_bp.route("/get_student_status", methods=["GET"])
def get_student_status():
    """Liefert den aktuellen Status (Runden, Ergebnisse, Abwesenheit) aller Schüler der geladenen Riege."""
    # Gibt den Status aller Schüler zurück
    if not session.get('riegenfuehrer') or not session.get('disziplin'):
        return jsonify({"status": "error", "message": "Keine Riege/Disziplin geladen. Bitte zuerst Riege und Disziplin auswählen."})
    schueler_daten = session.get('schueler_daten', [])
    student_status = {}
    for student in schueler_daten:
        name = f"{student[3]} {student[4]}"
        student_status[name] = {
            "schueler_id": student[5],
            "runde1_fertig": bool(student[6]),
            "runde2_fertig": bool(student[7]),
            "runde3_fertig": bool(student[8]),
            "abwesend": bool(student[9]),
            "ergebnisse": {
                "runde1": student[10] if student[10] != 0 else "",
                "runde2": student[11] if student[11] != 0 else "",
                "runde3": student[12] if student[12] != 0 else ""
            }
        }
    return jsonify({"status": "success", "student_status": student_status, "debug": {"total_students": len(schueler_daten), "first_student": schueler_daten[0] if schueler_daten else None}})

@schueler_bp.route("/get_student_id", methods=["GET"])
def get_student_id():
    """Ermittelt die Schüler-ID zu einem vollständigen Namen innerhalb der geladenen Riege."""
    # Gibt die SchuelerID für einen Namen zurück
    student_name = request.args.get("student_name")
    if not student_name:
        return jsonify({"status": "error", "message": "Kein Schülername angegeben"})
    schueler_daten = session.get('schueler_daten', [])
    for student in schueler_daten:
        if f"{student[3]} {student[4]}" == student_name:
            return jsonify({"status": "success", "schueler_id": student[5], "name": student_name, "abwesend": student[9]})
    return jsonify({"status": "error", "message": f"Schüler '{student_name}' nicht gefunden"})

@schueler_bp.route("/get_student_results", methods=["GET"])
def get_student_results():
    """Gibt gespeicherte Ergebnisse und Rundenstatus für einen spezifischen Schüler zurück."""
    # Gibt die Ergebnisse eines Schülers zurück
    student_name = request.args.get("student_name")
    disziplin = session.get('disziplin')
    if not student_name or not disziplin:
        return jsonify({"status": "error", "message": "Schüler oder Disziplin nicht gefunden. Bitte beide angeben/auswählen."})
    schueler_daten = session.get('schueler_daten', [])
    for student in schueler_daten:
        if f"{student[3]} {student[4]}" == student_name:
            return jsonify({"status": "success", "ergebnisse": {
                "runde1": student[10] if student[10] != 0 else "",
                "runde2": student[11] if student[11] != 0 else "",
                "runde3": student[12] if student[12] != 0 else "",
                "runde1_fertig": student[6],
                "runde2_fertig": student[7],
                "runde3_fertig": student[8]
            }})
    return jsonify({"status": "error", "message": "Schüler nicht gefunden"})

@schueler_bp.route("/get_current_result", methods=["GET"])
def get_current_result():
    """Lädt das gespeicherte Ergebnis (falls vorhanden) für einen Schüler und eine gewählte Runde."""
    # Aktuelle Parameter
    riegenfuehrer = request.args.get("riegenfuehrer")
    disziplin = request.args.get("disziplin")
    schueler_id = request.args.get("schueler_id")
    student_name = request.args.get("student_name")
    runde = request.args.get("runde", "1")

    if not riegenfuehrer or not disziplin:
        return jsonify({"has_result": False, "result": "NA", "message": "Fehlende Parameter: Riegenführer und Disziplin erforderlich."})

    # Schüler-ID aus der Session-Liste ableiten, falls nötig
    schueler_daten = session.get('schueler_daten', [])
    found_student = None
    if student_name:
        for student in schueler_daten:
            if f"{student[3]} {student[4]}" == student_name:
                found_student = student
                schueler_id = str(student[5])
                break
    if not found_student and schueler_id not in ['false', 'null', 'undefined', '', None]:
        for student in schueler_daten:
            if str(student[5]) == str(schueler_id):
                found_student = student
                student_name = f"{student[3]} {student[4]}"
                break
    if not found_student and schueler_daten:
        found_student = schueler_daten[0]
        schueler_id = str(found_student[5])
        student_name = f"{found_student[3]} {found_student[4]}"

    # Runde parsen
    try:
        runde_int = int(runde)
    except (TypeError, ValueError):
        return jsonify({"has_result": False, "result": "NA", "message": "Fehler beim Verarbeiten der Runde"})

    # Neueste Ergebniseintragung aus DB holen (eine Zeile pro Runde)
    result_value = None
    round_completed = False
    if schueler_id not in ['false', 'null', 'undefined', '', None]:
        try:
            db = g.get('db', backend.Backend(get_db_path()))
            latest = db.get_student_result(riegenfuehrer, disziplin, int(schueler_id), runde_int)
            if latest:
                result_value = latest.get('result')
                round_completed = bool(latest.get('round_completed'))
        except Exception:
            pass

    # Ergebnis formatieren
    if result_value is not None:
        # Zeitdisziplinen als mm:ss formatieren
        disziplin_name = request.args.get("disziplin") or session.get('disziplin', '')
        is_time = isinstance(disziplin_name, str) and ('laufen' in disziplin_name.lower() or 'sprint' in disziplin_name.lower())
        if is_time:
            try:
                secs = float(result_value)
                secs_int = int(round(secs))
                mm = secs_int // 60
                ss = secs_int % 60
                result_str = f"{mm}:{ss:02d}"
            except (TypeError, ValueError):
                result_str = "NA"
        else:
            result_str = str(result_value).replace('.', ',')
        return jsonify({"has_result": True, "result": result_str, "round_completed": round_completed})
    else:
        return jsonify({"has_result": False, "result": "NA", "round_completed": round_completed})
