"""Routen für die Ergebnis-Erfassung an den Stationen."""

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
from app.core.registry import DbRegistry, default_meta_db_path

input_bp = Blueprint("input", __name__, template_folder="../templates")


def _get_registry() -> DbRegistry:
    """Erzeugt eine Registry-Instanz für die globale Meta-Datenbank."""
    projektwurzel = Path(current_app.root_path).parent
    return DbRegistry(default_meta_db_path(projektwurzel))


def update_schueler_liste(schueler_liste, num_rounds=3):
    """Aktualisiert die in der Session gehaltene Schülerliste mit Rundenergebnissen."""
    datenbank = get_db()
    if datenbank is None:
        return schueler_liste

    disziplin = session.get("discipline")
    for schueler in schueler_liste:
        schueler_id = schueler["SchuelerID"]
        vorhandene_runden = datenbank.get_rounds_done(schueler_id, disziplin)

        for ergebnis_nummer, statuswert in vorhandene_runden:
            if 1 <= ergebnis_nummer <= num_rounds:
                schueler[f"Round{ergebnis_nummer}"] = statuswert

    return schueler_liste


def update_status_liste(schueler_liste, num_rounds=3):
    """Erzeugt eine frontendfreundliche Statusliste für die aktuelle Riege."""

    def status_zu_symbol(statuswert):
        """Wandelt interne Statuswerte in gut erkennbare UI-Symbole um."""
        if statuswert is None:
            return "⬜"
        if statuswert == "ABWESEND":
            return "❌"
        return "✅"

    status_liste = []
    for schueler in schueler_liste:
        schueler_id = schueler["SchuelerID"]
        vollstaendiger_name = f"{schueler['Vorname']} {schueler['Name']}"
        rohrunden = [schueler.get(f"Round{i}") for i in range(1, num_rounds + 1)]
        runden_symbole = [status_zu_symbol(statuswert) for statuswert in rohrunden]
        ist_abwesend = any(statuswert == "ABWESEND" for statuswert in rohrunden)
        ist_abgeschlossen = all(
            statuswert not in (None, "ABWESEND") for statuswert in rohrunden
        )
        status_liste.append(
            {
                "id": schueler_id,
                "name": vollstaendiger_name,
                "rounds": runden_symbole,
                "round_values": rohrunden,
                "absent": ist_abwesend,
                "completed": ist_abgeschlossen,
            }
        )
    return status_liste


def _validate_and_normalize_result(ergebnis: str, discipline: str):
    """Validiert Nutzereingaben und normalisiert sie in speicherbare Werte."""
    if ergebnis is None:
        return False, None, "Ergebnis erforderlich"

    bereinigter_wert = str(ergebnis).strip()
    if not bereinigter_wert:
        return False, None, "Ergebnis erforderlich"

    result_format = _get_result_format_for_discipline(discipline)

    if ":" in bereinigter_wert:
        if result_format != "time":
            return False, None, "Zeitformat nur fuer Zeitdisziplinen erlaubt"

        zeitteile = bereinigter_wert.split(":")
        if len(zeitteile) != 2:
            return False, None, "Zeitformat mm:ss erforderlich"

        minuten, sekunden = zeitteile
        if not minuten.isdigit() or not sekunden.isdigit():
            return False, None, "Zeitformat nur Ziffern erlaubt"

        sekunden_int = int(sekunden)
        if sekunden_int >= 60:
            return False, None, "Sekunden muessen < 60 sein"

        return True, float((int(minuten) * 60) + sekunden_int), ""

    try:
        numerischer_wert = float(bereinigter_wert.replace(",", "."))
    except ValueError:
        return False, None, "Ungueltiges Ergebnisformat"

    if numerischer_wert < 0:
        return False, None, "Ergebnis darf nicht negativ sein"

    return True, numerischer_wert, ""


def _require_round_number(rundennummer, max_rounds=5):
    """Prüft, ob eine Rundennummer im erlaubten Bereich liegt."""
    try:
        rundenwert = int(rundennummer)
    except (TypeError, ValueError):
        return None

    if rundenwert < 1 or rundenwert > max_rounds:
        return None
    return rundenwert


def _update_round_cache_in_session(schueler_id, round_nr, value):
    """Aktualisiert den Session-Cache nach einem gespeicherten Ergebnis."""
    schueler_liste = session.get("schueler", [])
    rundenfeld = f"Round{round_nr}"
    wurde_aktualisiert = False

    for schueler in schueler_liste:
        if schueler.get("SchuelerID") == schueler_id:
            schueler[rundenfeld] = value
            wurde_aktualisiert = True
            break

    if wurde_aktualisiert:
        session["schueler"] = schueler_liste


def _compute_progress(schueler_liste, num_rounds=3):
    """Berechnet den Fortschritt der aktuellen Riege über alle Runden."""
    fortschritt = {
        "total": len(schueler_liste),
        "absent": 0,
        "rounds_done": {runde: 0 for runde in range(1, num_rounds + 1)},
    }

    for schueler in schueler_liste:
        schueler_ist_abwesend = False
        for rundennummer in range(1, num_rounds + 1):
            statuswert = schueler.get(f"Round{rundennummer}")
            if statuswert == "ABWESEND":
                schueler_ist_abwesend = True
            if statuswert not in (None, "ABWESEND"):
                fortschritt["rounds_done"][rundennummer] += 1
        if schueler_ist_abwesend:
            fortschritt["absent"] += 1

    return fortschritt


def _collect_meta_data(schueler_liste):
    """Sammelt Zusatzinformationen für Hinweise und Statistiken im Frontend."""
    geschlechter = {}
    altersgruppen = {}
    klassen = {}
    profil_zaehler = {"profil": 0, "kein_profil": 0, "unbekannt": 0}

    for schueler in schueler_liste:
        geschlecht = (schueler.get("Geschlecht") or "unbekannt").strip()
        geschlechter[geschlecht] = geschlechter.get(geschlecht, 0) + 1

        alter = schueler.get("Bundesjugendspielalter")
        if alter is not None:
            altersgruppen[alter] = altersgruppen.get(alter, 0) + 1

        klasse = schueler.get("Klasse")
        if klasse is not None:
            klassen[klasse] = klassen.get(klasse, 0) + 1

        profil_flag = schueler.get("Profil")
        if profil_flag is True:
            profil_zaehler["profil"] += 1
        elif profil_flag is False:
            profil_zaehler["kein_profil"] += 1
        else:
            profil_zaehler["unbekannt"] += 1

    return {
        "gender_counts": geschlechter,
        "age_buckets": altersgruppen,
        "class_buckets": klassen,
        "profile_counts": profil_zaehler,
    }


def _get_num_rounds_for_discipline(discipline):
    """Liest die konfigurierte Rundenzahl für eine Disziplin aus der Registry."""
    if not discipline:
        return 3
    registry = _get_registry()
    disziplin = registry.get_disziplin_by_name(discipline)
    if disziplin:
        return disziplin.num_rounds
    return 3


def _get_result_format_for_discipline(discipline):
    """Liest das konfigurierte Ergebnisformat für eine Disziplin aus der Registry."""
    if not discipline:
        return "distance"
    registry = _get_registry()
    disziplin = registry.get_disziplin_by_name(discipline)
    if disziplin:
        return disziplin.format
    return "distance"


def build_status_payload(last_saved=None):
    """Baut die vollständige Antwort für die Statusansicht der Erfassung."""
    disziplin = session.get("discipline")
    anzahl_runden = _get_num_rounds_for_discipline(disziplin)
    leerer_fortschritt = {
        "total": 0,
        "absent": 0,
        "rounds_done": {runde: 0 for runde in range(1, anzahl_runden + 1)},
    }

    schueler_liste = session.get("schueler", [])
    if not schueler_liste:
        return {
            "status_list": [],
            "progress": leerer_fortschritt,
            "last_saved": last_saved,
            "meta": {
                "discipline": disziplin,
                "result_format": _get_result_format_for_discipline(disziplin),
                "num_rounds": anzahl_runden,
                "total": 0,
                "active_total": 0,
                "all_completed": False,
            },
        }

    schueler_liste = update_schueler_liste(schueler_liste, anzahl_runden)
    session["schueler"] = schueler_liste
    status_liste = update_status_liste(schueler_liste, anzahl_runden)
    fortschritt = _compute_progress(schueler_liste, anzahl_runden)
    aktive_schueler = max(fortschritt["total"] - fortschritt["absent"], 0)
    letzte_runde_erfasst = fortschritt["rounds_done"].get(anzahl_runden, 0)
    alle_fertig = aktive_schueler > 0 and letzte_runde_erfasst >= aktive_schueler
    offene_aktive = max(aktive_schueler - letzte_runde_erfasst, 0)
    metadaten = _collect_meta_data(schueler_liste)

    erster_schueler = schueler_liste[0] if schueler_liste else {}
    erste_klasse = None
    if erster_schueler:
        klassenstufe = erster_schueler.get("Klasse")
        klassenbuchstabe = erster_schueler.get("Klassenbuchstabe") or ""
        if klassenstufe is not None:
            erste_klasse = f"{klassenstufe}{klassenbuchstabe}"

    meta_informationen = {
        "discipline": disziplin,
        "result_format": _get_result_format_for_discipline(disziplin),
        "num_rounds": anzahl_runden,
        "total": fortschritt["total"],
        "active_total": aktive_schueler,
        "remaining_active": offene_aktive,
        "all_completed": alle_fertig,
        "completion_message": "Alle Ergebnisse erfasst."
        if alle_fertig
        else f"Noch {offene_aktive} Ergebnisse offen.",
        "gender_counts": metadaten.get("gender_counts"),
        "age_buckets": metadaten.get("age_buckets"),
        "class_buckets": metadaten.get("class_buckets"),
        "profile_counts": metadaten.get("profile_counts"),
        "first_gender": erster_schueler.get("Geschlecht") if erster_schueler else None,
        "first_class": erste_klasse,
        "first_profile": erster_schueler.get("Profil") if erster_schueler else None,
    }

    return {
        "status_list": status_liste,
        "progress": fortschritt,
        "last_saved": last_saved,
        "meta": meta_informationen,
    }


@input_bp.route("/input")
def input_page():
    """Zeigt die Haupterfassungsseite für eine eingeloggte Station an."""
    if not session.get("is_logged_in") or session.get("role") != "station":
        return redirect(url_for("auth.login"))

    datenbank = get_db()
    if datenbank is None:
        session.clear()
        return redirect(url_for("auth.login"))

    disziplin = session.get("discipline")
    anzahl_runden = _get_num_rounds_for_discipline(disziplin)
    registry = _get_registry()
    disziplin_info = registry.get_disziplin_by_name(disziplin) if disziplin else None
    result_format = disziplin_info.format if disziplin_info else "distance"

    return render_template(
        "input.html",
        riegenfuehrer=datenbank.get_riegenfuehrer(),
        station=disziplin_info.name if disziplin_info else disziplin or "Station",
        discipline=disziplin,
        result_format=result_format,
        num_rounds=anzahl_runden,
        ipad_stations_nummer="1",
        schueler_gesamt=0,
        schueler_abwesend=0,
    )


@input_bp.route("/get_riege", methods=["POST"])
def get_riege():
    """Lädt die ausgewählte Riege und speichert sie im Session-Kontext."""
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    anfrage_daten = request.get_json() or {}
    riegenfuehrer_id = anfrage_daten.get("riegenfuehrer_id")
    if not riegenfuehrer_id:
        return jsonify({"error": "riegenfuehrer_id fehlt"}), 400

    datenbank = get_db()
    if datenbank is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503

    schueler_liste = datenbank.get_riege(riegenfuehrer_id)
    session["schueler"] = schueler_liste
    return jsonify(build_status_payload())


@input_bp.route("/next_student", methods=["POST"])
def next_student():
    """Speichert ein Ergebnis für eine Runde und liefert den aktualisierten Status zurück."""
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    anfrage_daten = request.get_json() or {}
    schueler_id = anfrage_daten.get("schueler_id")
    ergebnis = anfrage_daten.get("ergebnis")
    rundennummer = _require_round_number(anfrage_daten.get("round"))
    disziplin = session.get("discipline")

    if not schueler_id or rundennummer is None:
        return jsonify({"error": "schueler_id und round erforderlich"}), 400
    if not disziplin:
        return jsonify({"error": "disziplin nicht gesetzt"}), 400

    ist_gueltig, normalisierter_wert, fehlermeldung = _validate_and_normalize_result(
        ergebnis,
        disziplin,
    )
    if not ist_gueltig:
        return jsonify({"error": fehlermeldung}), 400

    datenbank = get_db()
    if datenbank is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503

    try:
        datenbank.add_entry(
            schueler_id=schueler_id,
            disziplin=disziplin,
            ergebnis_nr=rundennummer,
            result_value=normalisierter_wert,
            status="OK",
            source_ipad_number=1,
            source_station=1,
        )
    except Exception as fehler:
        return jsonify({"error": str(fehler)}), 500

    _update_round_cache_in_session(schueler_id, rundennummer, normalisierter_wert)

    anzeigewert = normalisierter_wert
    if isinstance(normalisierter_wert, float):
        anzeigewert = f"{normalisierter_wert:.2f}".replace(".", ",")

    return jsonify(
        build_status_payload(
            last_saved={
                "schueler_id": schueler_id,
                "round": rundennummer,
                "status": "OK",
                "value": anzeigewert,
            }
        )
    )


@input_bp.route("/get_current_result", methods=["GET"])
def get_current_result():
    """Liefert das bereits gespeicherte Ergebnis für eine bestimmte Runde zurück."""
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    schueler_id = request.args.get("schueler_id")
    rundennummer = request.args.get("runde")
    disziplin = session.get("discipline")

    if not schueler_id or not rundennummer or not disziplin:
        return jsonify({"has_result": False, "result": "NA"})

    try:
        rundennummer_int = int(rundennummer)
    except (TypeError, ValueError):
        return jsonify({"has_result": False, "result": "NA"})

    datenbank = get_db()
    if datenbank is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503

    vorhandene_runden = datenbank.get_rounds_done(schueler_id, disziplin)
    for ergebnis_nummer, statuswert in vorhandene_runden:
        if ergebnis_nummer != rundennummer_int:
            continue
        if statuswert == "ABWESEND":
            return jsonify({"has_result": True, "result": "ABWESEND"})
        if isinstance(statuswert, float):
            return jsonify(
                {"has_result": True, "result": f"{statuswert:.2f}".replace(".", ",")}
            )
        if statuswert is not None:
            return jsonify({"has_result": True, "result": str(statuswert)})

    return jsonify({"has_result": False, "result": "NA"})


@input_bp.route("/mark_absent", methods=["POST"])
def mark_absent():
    """Markiert eine einzelne Runde oder alle Runden eines Schülers als abwesend."""
    if not session.get("is_logged_in") or session.get("role") != "station":
        return jsonify({"error": "unauthorized"}), 401

    anfrage_daten = request.get_json() or {}
    schueler_id = anfrage_daten.get("schueler_id")
    rundennummer = anfrage_daten.get("round")
    disziplin = session.get("discipline")

    if not schueler_id:
        return jsonify({"error": "schueler_id erforderlich"}), 400
    if not disziplin:
        return jsonify({"error": "disziplin nicht gesetzt"}), 400

    anzahl_runden = _get_num_rounds_for_discipline(disziplin)
    datenbank = get_db()
    if datenbank is None:
        return jsonify({"error": "Keine Datenbank vorhanden"}), 503

    try:
        if rundennummer is not None:
            gepruefte_runde = _require_round_number(rundennummer, anzahl_runden)
            if gepruefte_runde is None:
                return jsonify({"error": "ungueltige Rundennummer"}), 400

            datenbank.add_entry(
                schueler_id=schueler_id,
                disziplin=disziplin,
                ergebnis_nr=gepruefte_runde,
                result_value=None,
                status="ABWESEND",
                source_ipad_number=1,
                source_station=1,
            )
            _update_round_cache_in_session(schueler_id, gepruefte_runde, "ABWESEND")
        else:
            # Ohne Rundennummer wird der Schüler als komplett abwesend behandelt.
            for laufende_runde in range(1, anzahl_runden + 1):
                datenbank.add_entry(
                    schueler_id=schueler_id,
                    disziplin=disziplin,
                    ergebnis_nr=laufende_runde,
                    result_value=None,
                    status="ABWESEND",
                    source_ipad_number=1,
                    source_station=1,
                )
                _update_round_cache_in_session(
                    schueler_id,
                    laufende_runde,
                    "ABWESEND",
                )
    except Exception as fehler:
        return jsonify({"error": str(fehler)}), 500

    return jsonify(
        build_status_payload(
            last_saved={
                "schueler_id": schueler_id,
                "round": rundennummer if rundennummer else "all",
                "status": "ABWESEND",
                "value": None,
            }
        )
    )
