"""Hilfsfunktionen für den Import von Schülerdaten aus CSV-Dateien."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from app.database.database import Database


@dataclass(frozen=True)
class CsvImportResult:
    """Beschreibt das Ergebnis eines CSV-Imports in eine neue Datenbank."""

    db_path: str
    db_name: str
    imported: int
    errors: int


def _read_students_from_csv(
    *,
    csv_text: TextIO,
    delimiter: str = ";",
) -> tuple[list[dict[str, object]], int]:
    """Parst Schülerdaten aus CSV und liefert gültige Datensätze plus Fehleranzahl."""
    csv_leser = csv.DictReader(csv_text, delimiter=delimiter)
    if not csv_leser.fieldnames:
        raise ValueError("CSV hat keine Kopfzeile")

    normalisierte_spalten = {
        _normalize_header(spaltenname) for spaltenname in csv_leser.fieldnames
    }
    fehlende_spalten = _PFLICHTSPALTEN - normalisierte_spalten
    if fehlende_spalten:
        raise ValueError(
            f"CSV Kopfzeile fehlt: {', '.join(sorted(fehlende_spalten))}"
        )

    datensaetze: list[dict[str, object]] = []
    fehlerhafte_zeilen = 0
    for csv_zeile in csv_leser:
        try:
            normalisierte_zeile = {
                _normalize_header(spaltenname): wert
                for spaltenname, wert in csv_zeile.items()
            }

            geschlecht = str(normalisierte_zeile.get("geschlecht", "")).strip().lower()
            stufe, klassenbuchstabe = _parse_klasse(
                str(normalisierte_zeile.get("klasse", ""))
            )
            nachname = str(normalisierte_zeile.get("name", "")).strip()
            vorname = str(normalisierte_zeile.get("vorname", "")).strip()
            geburtsjahr = int(str(normalisierte_zeile.get("geburtsjahr", "")).strip())
            profil_flag = _to_bool(normalisierte_zeile.get("profil"))

            if geschlecht not in {"m", "w"}:
                raise ValueError("Geschlecht muss m oder w sein")
            if not nachname or not vorname:
                raise ValueError("Name/Vorname fehlt")

            datensaetze.append(
                {
                    "name": nachname,
                    "vorname": vorname,
                    "geschlecht": geschlecht,
                    "klasse": stufe,
                    "klassenbuchstabe": klassenbuchstabe,
                    "geburtsjahr": geburtsjahr,
                    "profil": profil_flag,
                }
            )
        except Exception:
            fehlerhafte_zeilen += 1

    return datensaetze, fehlerhafte_zeilen


def import_students_csv_into_db(
    *,
    db: Database,
    csv_text: TextIO,
    delimiter: str = ";",
    replace_existing: bool = False,
) -> tuple[int, int]:
    """Importiert Schülerdaten in eine bestehende DB, optional mit Komplett-Ersatz."""
    datensaetze, fehlerhafte_zeilen = _read_students_from_csv(
        csv_text=csv_text,
        delimiter=delimiter,
    )

    if replace_existing:
        db.clear_all_students_and_results()

    importierte_schueler = 0
    for datensatz in datensaetze:
        db.add_schueler(**datensatz)
        importierte_schueler += 1
    db.connection.commit()
    return importierte_schueler, fehlerhafte_zeilen


_PFLICHTSPALTEN = {
    "geschlecht",
    "klasse",
    "name",
    "vorname",
    "geburtsjahr",
}


def _normalize_header(spaltenname: str) -> str:
    """Normalisiert CSV-Überschriften für robuste Vergleiche."""
    return re.sub(r"\s+", "", str(spaltenname or "").strip().lower())


def _to_bool(wert: object) -> bool:
    """Interpretiert typische Wahrheitswerte aus CSV-Dateien."""
    if wert is None:
        return False
    if isinstance(wert, bool):
        return wert
    roher_wert = str(wert).strip().lower()
    return roher_wert in {"1", "true", "yes", "ja", "y"}


def _parse_klasse(klassenwert: str) -> tuple[int, str]:
    """Zerlegt eine Klassenangabe in Stufe und Buchstabenanteil."""
    roher_wert = str(klassenwert or "").strip()
    if not roher_wert:
        raise ValueError("Klasse fehlt")

    stufenziffern = "".join(zeichen for zeichen in roher_wert if zeichen.isdigit())
    klassenbuchstaben = "".join(
        zeichen for zeichen in roher_wert if zeichen.isalpha()
    )

    if not stufenziffern:
        raise ValueError(f"Ungueltige Klasse: {roher_wert}")

    stufe = int(stufenziffern)
    klassenbuchstabe = (klassenbuchstaben[:1] or "").lower()
    return stufe, klassenbuchstabe


def build_db_filename(*, year: int, target_dir: Path) -> str:
    """Erzeugt den nächsten freien Dateinamen im Format `BJS_JAHR_ID.db`."""
    vorhandene_ids: list[int] = []
    dateiname_muster = re.compile(rf"^BJS_{year}_(\d+)\.db$", re.IGNORECASE)

    if target_dir.exists():
        for datei in target_dir.iterdir():
            if not datei.is_file():
                continue
            treffer = dateiname_muster.match(datei.name)
            if treffer:
                vorhandene_ids.append(int(treffer.group(1)))

    naechste_id = max(vorhandene_ids, default=0) + 1
    return f"BJS_{year}_{naechste_id}.db"


def import_students_csv_to_new_db(
    *,
    csv_text: TextIO,
    target_dir: str | Path,
    delimiter: str = ";",
    year: Optional[int] = None,
) -> CsvImportResult:
    """Importiert eine Schüler-CSV in eine neue SQLite-Datenbank."""
    zielverzeichnis = Path(target_dir)
    zielverzeichnis.mkdir(parents=True, exist_ok=True)

    import_jahr = int(year or datetime.now().year)
    datenbankname = build_db_filename(year=import_jahr, target_dir=zielverzeichnis)
    datenbankpfad = zielverzeichnis / datenbankname

    datenbank = Database(path=str(datenbankpfad))

    try:
        importierte_schueler, fehlerhafte_zeilen = import_students_csv_into_db(
            db=datenbank,
            csv_text=csv_text,
            delimiter=delimiter,
            replace_existing=False,
        )
    finally:
        datenbank.connection.close()

    return CsvImportResult(
        db_path=str(datenbankpfad),
        db_name=datenbankname,
        imported=importierte_schueler,
        errors=fehlerhafte_zeilen,
    )
