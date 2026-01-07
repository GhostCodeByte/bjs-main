from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from app.database.database import Database


@dataclass(frozen=True)
class RiegeCreateResult:
    rf_id: int
    assigned: int


def _normalize_klassenendungen(value: str) -> str:
    raw = (value or "").replace(" ", "")
    raw = raw.replace(",", "")
    return raw.lower()


def create_riege_and_assign(
    *,
    db: Database,
    name: str,
    stufe: int,
    klassenendungen: str,
    geschlecht: str,
    profil: bool,
) -> RiegeCreateResult:
    klassen = _normalize_klassenendungen(klassenendungen)
    if not name.strip():
        raise ValueError("Name erforderlich")
    if stufe not in range(5, 11):
        raise ValueError("Stufe muss 5-10 sein")
    if not klassen:
        raise ValueError("Klassenendungen erforderlich")

    if bool(profil):
        # Profil-Riegen werden nur nach Klasse + Profil zugewiesen (ohne Geschlecht-Filter)
        gespeichertes_geschlecht = "mw"
        geschlechter = ["mw"]
    else:
        g_raw = (geschlecht or "").strip()
        g = g_raw.lower()
        if g in {"beide", "mw", "m+w", "m/w", "both", "m w", "m,w"}:
            geschlechter = ["m", "w"]
            gespeichertes_geschlecht = "mw"
        elif g in {"m", "jungen", "male"}:
            geschlechter = ["m"]
            gespeichertes_geschlecht = "m"
        elif g in {"w", "maedchen", "mädchen", "female"}:
            geschlechter = ["w"]
            gespeichertes_geschlecht = "w"
        else:
            raise ValueError("Geschlecht ungültig (m/w/beide)")

    rf_id = db.add_riegenfuehrer(
        name=name.strip(),
        geschlecht=gespeichertes_geschlecht,
        profil=bool(profil),
        stufe=int(stufe),
        klassenendung=klassen,
    )

    for kl_end in klassen:
        if bool(profil):
            db.add_riegenfuehrer_to_schueler(
                rf_id=rf_id,
                klassenbuchstabe=kl_end,
                stufe=int(stufe),
                geschlecht="mw",
                profil=True,
            )
        else:
            for g_val in geschlechter:
                db.add_riegenfuehrer_to_schueler(
                    rf_id=rf_id,
                    klassenbuchstabe=kl_end,
                    stufe=int(stufe),
                    geschlecht=g_val,
                    profil=False,
                )

    db.cursor.execute(
        "SELECT COUNT(*) FROM Schueler WHERE RiegenfuehrerID = ?",
        (rf_id,),
    )
    assigned = int(db.cursor.fetchone()[0] or 0)
    db.connection.commit()

    return RiegeCreateResult(rf_id=rf_id, assigned=assigned)


def parse_riegenfuehrer_names_csv(
    *,
    csv_text: str,
    delimiter: str = ";",
) -> list[str]:
    """Parse 1-column CSV with leader names.

    Accepts optional header row. Empty lines are ignored.
    """

    text = (csv_text or "").strip("\ufeff\n\r\t ")
    if not text:
        return []

    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    names: list[str] = []
    for row in reader:
        if not row:
            continue
        raw = str(row[0] or "").strip()
        if not raw:
            continue
        if raw.lower() in {"name", "namen", "riegenführer", "riegenfuehrer"}:
            # treat as header
            continue
        names.append(raw)
    return names


@dataclass(frozen=True)
class AutoRiegeResult:
    created_riegen: int
    assigned_students: int
    used_leader_names: int


def auto_create_riegen_and_assign(
    *,
    db: Database,
    leader_names: Optional[Iterable[str]] = None,
    keep_existing_riegen: bool = False,
) -> AutoRiegeResult:
    """Erstellt Riegen automatisch und weist Schüler zu.

    Regeln:
    - Für jede Klasse: m/w Riegen für Nicht-Profil.
    - Profil-Schüler: 1 Profil-Riege pro Klasse (ohne Geschlecht).
    - Riegenführer Namen werden (falls vorhanden) nacheinander vergeben, Rest: "Riegenführer N".

    Wenn `keep_existing_riegen` False ist, werden vorhandene Riegen + Zuweisungen vorher gelöscht.
    """

    names = [n.strip() for n in (leader_names or []) if str(n or "").strip()]
    name_idx = 0

    if not keep_existing_riegen:
        db.clear_all_riegen()

    classes = db.get_present_classes()

    created = 0
    assigned_total = 0

    for cls in classes:
        stufe = int(cls["stufe"])
        buchstabe = str(cls["buchstabe"] or "").strip().lower()
        if not buchstabe:
            continue

        # Profil Riege (falls nötig)
        if bool(cls.get("has_profil")):
            riege_name = names[name_idx] if name_idx < len(names) else f"Riegenführer {created + 1}"
            if name_idx < len(names):
                name_idx += 1
            res = create_riege_and_assign(
                db=db,
                name=riege_name,
                stufe=stufe,
                klassenendungen=buchstabe,
                geschlecht="mw",
                profil=True,
            )
            created += 1
            assigned_total += res.assigned

        # Nicht-Profil: m und w
        for g in ("m", "w"):
            riege_name = names[name_idx] if name_idx < len(names) else f"Riegenführer {created + 1}"
            if name_idx < len(names):
                name_idx += 1
            res = create_riege_and_assign(
                db=db,
                name=riege_name,
                stufe=stufe,
                klassenendungen=buchstabe,
                geschlecht=g,
                profil=False,
            )
            created += 1
            assigned_total += res.assigned

    return AutoRiegeResult(
        created_riegen=created,
        assigned_students=assigned_total,
        used_leader_names=min(len(names), name_idx),
    )


@dataclass(frozen=True)
class ReplaceNamesResult:
    replaced: int
    total_riegen: int


def parse_leader_names_csv(
    *,
    csv_text: str,
) -> list[str]:
    """Parse CSV with leader names. Auto-detects delimiter (;, comma, tab).

    Accepts optional header row. Empty lines are ignored.
    """
    text = (csv_text or "").strip("\ufeff\n\r\t ")
    if not text:
        return []

    # Auto-detect delimiter
    first_line = text.split("\n")[0] if "\n" in text else text
    if "\t" in first_line:
        delimiter = "\t"
    elif "," in first_line and ";" not in first_line:
        delimiter = ","
    else:
        delimiter = ";"

    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    names: list[str] = []
    for row in reader:
        if not row:
            continue
        raw = str(row[0] or "").strip()
        if not raw:
            continue
        if raw.lower() in {"name", "namen", "riegenführer", "riegenfuehrer", "leiter"}:
            # treat as header
            continue
        names.append(raw)
    return names


def replace_placeholder_names(
    *,
    db: Database,
    leader_names: list[str],
) -> ReplaceNamesResult:
    """Replace placeholder names (Riegenführer N) with real names from list.

    Names are matched in order: first placeholder gets first name, etc.
    Only riegen with names matching 'Riegenführer <number>' are replaced.
    """
    if not leader_names:
        return ReplaceNamesResult(replaced=0, total_riegen=0)

    # Get all riegen sorted by ID (creation order)
    riegen = db.get_all_riegen_with_progress()
    total = len(riegen)

    # Find placeholder riegen (pattern: "Riegenführer N" where N is a number)
    placeholder_pattern = re.compile(r"^Riegenführer\s*\d+$", re.IGNORECASE)

    placeholder_riegen = [
        r for r in riegen if placeholder_pattern.match(str(r.get("name", "") or "").strip())
    ]

    # Sort by ID to maintain creation order
    placeholder_riegen.sort(key=lambda r: r.get("id", 0))

    replaced = 0
    for i, riege in enumerate(placeholder_riegen):
        if i >= len(leader_names):
            break

        new_name = leader_names[i].strip()
        if not new_name:
            continue

        riege_id = riege.get("id")
        if riege_id:
            db.cursor.execute(
                "UPDATE Riegenfuehrer SET Name = ? WHERE RiegenfuehrerID = ?",
                (new_name, riege_id),
            )
            replaced += 1

    db.connection.commit()
    return ReplaceNamesResult(replaced=replaced, total_riegen=total)
