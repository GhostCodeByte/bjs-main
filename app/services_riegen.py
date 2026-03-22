"""Hilfsfunktionen für das Erzeugen und Verwalten von Riegen."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from app.database.database import Database


@dataclass(frozen=True)
class RiegeCreateResult:
    """Enthält Kennzahlen nach dem Anlegen einer einzelnen Riege."""

    rf_id: int
    assigned: int


def _normalize_klassenendungen(klassenendungen: str) -> str:
    """Bereinigt Klassensuffixe aus Freitext für die weitere Verarbeitung."""
    bereinigter_wert = (klassenendungen or "").replace(" ", "")
    bereinigter_wert = bereinigter_wert.replace(",", "")
    return bereinigter_wert.lower()


def create_riege_and_assign(
    *,
    db: Database,
    name: str,
    stufe: int,
    klassenendungen: str,
    geschlecht: str,
    profil: bool,
) -> RiegeCreateResult:
    """Legt eine Riege an und weist passende Schülerinnen und Schüler zu."""
    normalisierte_klassenendungen = _normalize_klassenendungen(klassenendungen)
    if not name.strip():
        raise ValueError("Name erforderlich")
    if stufe not in range(5, 11):
        raise ValueError("Stufe muss 5-10 sein")
    if not normalisierte_klassenendungen:
        raise ValueError("Klassenendungen erforderlich")

    if bool(profil):
        # Profil-Riegen werden nur nach Klasse und Profil zugewiesen, nicht nach Geschlecht.
        gespeichertes_geschlecht = "mw"
        zielgeschlechter = ["mw"]
    else:
        geschlecht_text = (geschlecht or "").strip().lower()
        if geschlecht_text in {"beide", "mw", "m+w", "m/w", "both", "m w", "m,w"}:
            zielgeschlechter = ["m", "w"]
            gespeichertes_geschlecht = "mw"
        elif geschlecht_text in {"m", "jungen", "male"}:
            zielgeschlechter = ["m"]
            gespeichertes_geschlecht = "m"
        elif geschlecht_text in {"w", "maedchen", "mädchen", "female"}:
            zielgeschlechter = ["w"]
            gespeichertes_geschlecht = "w"
        else:
            raise ValueError("Geschlecht ungueltig (m/w/beide)")

    riegenfuehrer_id = db.add_riegenfuehrer(
        name=name.strip(),
        geschlecht=gespeichertes_geschlecht,
        profil=bool(profil),
        stufe=int(stufe),
        klassenendung=normalisierte_klassenendungen,
    )

    for klassenbuchstabe in normalisierte_klassenendungen:
        if bool(profil):
            db.add_riegenfuehrer_to_schueler(
                rf_id=riegenfuehrer_id,
                klassenbuchstabe=klassenbuchstabe,
                stufe=int(stufe),
                geschlecht="mw",
                profil=True,
            )
            continue

        for zielgeschlecht in zielgeschlechter:
            db.add_riegenfuehrer_to_schueler(
                rf_id=riegenfuehrer_id,
                klassenbuchstabe=klassenbuchstabe,
                stufe=int(stufe),
                geschlecht=zielgeschlecht,
                profil=False,
            )

    db.cursor.execute(
        "SELECT COUNT(*) FROM Schueler WHERE RiegenfuehrerID = ?",
        (riegenfuehrer_id,),
    )
    zugewiesene_schueler = int(db.cursor.fetchone()[0] or 0)
    db.connection.commit()

    return RiegeCreateResult(
        rf_id=riegenfuehrer_id,
        assigned=zugewiesene_schueler,
    )


def parse_riegenfuehrer_names_csv(
    *,
    csv_text: str,
    delimiter: str = ";",
) -> list[str]:
    """Liest eine einspaltige CSV mit Riegenführer-Namen ein."""
    bereinigter_text = (csv_text or "").strip("\ufeff\n\r\t ")
    if not bereinigter_text:
        return []

    csv_leser = csv.reader(bereinigter_text.splitlines(), delimiter=delimiter)
    namenliste: list[str] = []
    for zeile in csv_leser:
        if not zeile:
            continue
        name = str(zeile[0] or "").strip()
        if not name:
            continue
        if name.lower() in {"name", "namen", "riegenführer", "riegenfuehrer"}:
            continue
        namenliste.append(name)
    return namenliste


@dataclass(frozen=True)
class AutoRiegeResult:
    """Fasst den automatischen Riegenlauf in Kennzahlen zusammen."""

    created_riegen: int
    assigned_students: int
    used_leader_names: int


def auto_create_riegen_and_assign(
    *,
    db: Database,
    leader_names: Optional[Iterable[str]] = None,
    keep_existing_riegen: bool = False,
) -> AutoRiegeResult:
    """Erstellt Riegen automatisch und weist passende Schülerinnen und Schüler zu."""
    verfuegbare_namen = [
        name.strip() for name in (leader_names or []) if str(name or "").strip()
    ]
    naechster_name_index = 0

    if not keep_existing_riegen:
        db.clear_all_riegen()

    vorhandene_klassen = db.get_present_classes()
    erstellte_riegen = 0
    zugewiesene_schueler_gesamt = 0

    for klasseninfo in vorhandene_klassen:
        stufe = int(klasseninfo["stufe"])
        klassenbuchstabe = str(klasseninfo["buchstabe"] or "").strip().lower()
        if not klassenbuchstabe:
            continue

        if bool(klasseninfo.get("has_profil")):
            riegenname = (
                verfuegbare_namen[naechster_name_index]
                if naechster_name_index < len(verfuegbare_namen)
                else f"Riegenfuehrer {erstellte_riegen + 1}"
            )
            if naechster_name_index < len(verfuegbare_namen):
                naechster_name_index += 1
            ergebnis = create_riege_and_assign(
                db=db,
                name=riegenname,
                stufe=stufe,
                klassenendungen=klassenbuchstabe,
                geschlecht="mw",
                profil=True,
            )
            erstellte_riegen += 1
            zugewiesene_schueler_gesamt += ergebnis.assigned

        for geschlecht in ("m", "w"):
            riegenname = (
                verfuegbare_namen[naechster_name_index]
                if naechster_name_index < len(verfuegbare_namen)
                else f"Riegenfuehrer {erstellte_riegen + 1}"
            )
            if naechster_name_index < len(verfuegbare_namen):
                naechster_name_index += 1
            ergebnis = create_riege_and_assign(
                db=db,
                name=riegenname,
                stufe=stufe,
                klassenendungen=klassenbuchstabe,
                geschlecht=geschlecht,
                profil=False,
            )
            erstellte_riegen += 1
            zugewiesene_schueler_gesamt += ergebnis.assigned

    return AutoRiegeResult(
        created_riegen=erstellte_riegen,
        assigned_students=zugewiesene_schueler_gesamt,
        used_leader_names=min(len(verfuegbare_namen), naechster_name_index),
    )


@dataclass(frozen=True)
class ReplaceNamesResult:
    """Beschreibt, wie viele Platzhalternamen ersetzt wurden."""

    replaced: int
    total_riegen: int


def parse_leader_names_csv(
    *,
    csv_text: str,
) -> list[str]:
    """Liest Leiter-Namen aus einer CSV mit automatischer Trennzeichenerkennung."""
    bereinigter_text = (csv_text or "").strip("\ufeff\n\r\t ")
    if not bereinigter_text:
        return []

    erste_zeile = (
        bereinigter_text.split("\n")[0] if "\n" in bereinigter_text else bereinigter_text
    )
    if "\t" in erste_zeile:
        trennzeichen = "\t"
    elif "," in erste_zeile and ";" not in erste_zeile:
        trennzeichen = ","
    else:
        trennzeichen = ";"

    csv_leser = csv.reader(bereinigter_text.splitlines(), delimiter=trennzeichen)
    namenliste: list[str] = []
    for zeile in csv_leser:
        if not zeile:
            continue
        name = str(zeile[0] or "").strip()
        if not name:
            continue
        if name.lower() in {
            "name",
            "namen",
            "riegenführer",
            "riegenfuehrer",
            "leiter",
        }:
            continue
        namenliste.append(name)
    return namenliste


def replace_placeholder_names(
    *,
    db: Database,
    leader_names: list[str],
) -> ReplaceNamesResult:
    """Ersetzt Platzhalter wie `Riegenfuehrer 1` durch echte Namen aus einer Liste."""
    if not leader_names:
        return ReplaceNamesResult(replaced=0, total_riegen=0)

    alle_riegen = db.get_all_riegen_with_progress()
    anzahl_riegen = len(alle_riegen)
    platzhalter_muster = re.compile(r"^Riegenfuehrer\s*\d+$", re.IGNORECASE)

    platzhalter_riegen = [
        riege
        for riege in alle_riegen
        if platzhalter_muster.match(str(riege.get("name", "") or "").strip())
    ]
    platzhalter_riegen.sort(key=lambda riege: riege.get("id", 0))

    ersetzte_namen = 0
    for index, riege in enumerate(platzhalter_riegen):
        if index >= len(leader_names):
            break

        neuer_name = leader_names[index].strip()
        if not neuer_name:
            continue

        riegen_id = riege.get("id")
        if not riegen_id:
            continue

        db.cursor.execute(
            "UPDATE Riegenfuehrer SET Name = ? WHERE RiegenfuehrerID = ?",
            (neuer_name, riegen_id),
        )
        ersetzte_namen += 1

    db.connection.commit()
    return ReplaceNamesResult(
        replaced=ersetzte_namen,
        total_riegen=anzahl_riegen,
    )
