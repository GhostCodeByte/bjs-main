from __future__ import annotations

from dataclasses import dataclass

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

    g = geschlecht.strip().lower()
    if g in {"beide", "mw", "m+w", "m/w", "both"}:
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
        for g_val in geschlechter:
            db.add_riegenfuehrer_to_schueler(
                rf_id=rf_id,
                klassenbuchstabe=kl_end,
                stufe=int(stufe),
                geschlecht=g_val,
                profil=bool(profil),
            )

    db.cursor.execute(
        "SELECT COUNT(*) FROM Schueler WHERE RiegenfuehrerID = ?",
        (rf_id,),
    )
    assigned = int(db.cursor.fetchone()[0] or 0)
    db.connection.commit()

    return RiegeCreateResult(rf_id=rf_id, assigned=assigned)
