from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Iterable, Optional, TextIO

from app.database.database import Database


@dataclass(frozen=True)
class CsvImportResult:
    db_path: str
    db_name: str
    imported: int
    errors: int


_REQUIRED_HEADERS = {
    "geschlecht",
    "klasse",
    "name",
    "vorname",
    "geburtsjahr",
}


def _normalize_header(key: str) -> str:
    return re.sub(r"\s+", "", str(key or "").strip().lower())


def _to_bool(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    return raw in {"1", "true", "yes", "ja", "y"}


def _parse_klasse(value: str) -> tuple[int, str]:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Klasse fehlt")

    digits = "".join(ch for ch in raw if ch.isdigit())
    letters = "".join(ch for ch in raw if ch.isalpha())

    if not digits:
        raise ValueError(f"Ungültige Klasse: {raw}")

    stufe = int(digits)
    buchstabe = (letters[:1] or "").lower()
    return stufe, buchstabe


def _slugify(label: str) -> str:
    text = (label or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "upload"


def build_db_filename(*, year: int, label: str, created_at: Optional[datetime] = None) -> str:
    ts = (created_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
    slug = _slugify(label)
    return f"bjs_{year}_{slug}_{ts}.db"


def import_students_csv_to_new_db(
    *,
    csv_text: TextIO,
    target_dir: str | Path,
    label: str,
    delimiter: str = ";",
    year: Optional[int] = None,
) -> CsvImportResult:
    """Create a new SQLite DB from a header-based CSV.

    Expected headers (case-insensitive):
    - Geschlecht
    - Klasse
    - Name
    - Vorname
    - Geburtsjahr
    Optional:
    - Profil
    """

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    resolved_year = int(year or datetime.now().year)
    db_name = build_db_filename(year=resolved_year, label=label)
    db_path = target_dir / db_name

    reader = csv.DictReader(csv_text, delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV hat keine Kopfzeile")

    headers = {_normalize_header(h) for h in reader.fieldnames}
    missing = _REQUIRED_HEADERS - headers
    if missing:
        raise ValueError(f"CSV Kopfzeile fehlt: {', '.join(sorted(missing))}")

    imported = 0
    errors = 0

    db = Database(path=str(db_path))
    try:
        for row in reader:
            try:
                norm_row = {_normalize_header(k): v for k, v in row.items()}

                geschlecht = str(norm_row.get("geschlecht", "")).strip().lower()
                stufe, buchstabe = _parse_klasse(str(norm_row.get("klasse", "")))
                name = str(norm_row.get("name", "")).strip()
                vorname = str(norm_row.get("vorname", "")).strip()
                geburtsjahr = int(str(norm_row.get("geburtsjahr", "")).strip())
                profil = _to_bool(norm_row.get("profil"))

                if geschlecht not in {"m", "w"}:
                    raise ValueError("Geschlecht muss m oder w sein")
                if not name or not vorname:
                    raise ValueError("Name/Vorname fehlt")

                db.add_schueler(
                    name=name,
                    vorname=vorname,
                    geschlecht=geschlecht,
                    klasse=stufe,
                    klassenbuchstabe=buchstabe,
                    geburtsjahr=geburtsjahr,
                    profil=profil,
                )
                imported += 1
            except Exception:
                errors += 1
        db.connection.commit()
    finally:
        db.connection.close()

    return CsvImportResult(
        db_path=str(db_path),
        db_name=db_name,
        imported=imported,
        errors=errors,
    )
