"""Auswertung der BJS-Gesamtpunkte auf Basis der Event-Datenbank."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.auswertung_config import get_default_auswertung_config


def _auswertung_sprint(ergebnis: float, maennlich: bool, strecke: int) -> float:
    # Von Enno
    # Bewertungsformel für Sprint aus dem externen Auswertungs-Repo übernommen.
    if ergebnis <= 0:
        return 0.0

    if strecke == 100:
        return (
            ((100 / (ergebnis + 0.24)) - 4.341) / 0.00676
            if maennlich
            else ((100 / (ergebnis + 0.24)) - 4.0062) / 0.00656
        )
    if strecke == 75:
        return (
            (75 / (ergebnis + 0.24) - 4.1) / 0.00664
            if maennlich
            else (75 / (ergebnis + 0.24) - 3.998) / 0.0066
        )
    if strecke == 50:
        return (
            (50 / (ergebnis + 0.24) - 3.79) / 0.0069
            if maennlich
            else (50 / (ergebnis + 0.24) - 3.648) / 0.0066
        )
    raise ValueError(f"Ungültige Sprintstrecke: {strecke}")


def _auswertung_sprung(ergebnis: float, maennlich: bool, weit: bool) -> float:
    # Von Enno
    # Bewertungsformel für Sprung aus dem externen Auswertungs-Repo übernommen.
    if ergebnis <= 0:
        return 0.0

    wurzel = math.sqrt(ergebnis)
    if weit:
        return (
            (wurzel - 1.15028) / 0.00219
            if maennlich
            else (wurzel - 1.0935) / 0.00208
        )
    return (
        (wurzel - 0.84) / 0.0008
        if maennlich
        else (wurzel - 0.8807) / 0.00068
    )


def _auswertung_wurf(
    ergebnis: float,
    maennlich: bool,
    ist_stoss: bool,
    ist_80_gramm: bool,
) -> float:
    # Von Enno
    # Bewertungsformel für Wurf/Stoß aus dem externen Auswertungs-Repo übernommen.
    if ergebnis <= 0:
        return 0.0

    wurzel = math.sqrt(ergebnis)
    if ist_stoss:
        return (
            (wurzel - 1.425) / 0.0037
            if maennlich
            else (wurzel - 1.279) / 0.00398
        )
    if ist_80_gramm:
        return (
            (wurzel - 2.8) / 0.011
            if maennlich
            else (wurzel - 2.0232) / 0.00874
        )
    return (
        (wurzel - 1.936) / 0.0124
        if maennlich
        else (wurzel - 1.4149) / 0.01039
    )


def _auswertung_lauf(ergebnis: float, maennlich: bool) -> float:
    # Von Enno
    # Bewertungsformel für Lauf aus dem externen Auswertungs-Repo übernommen.
    if ergebnis <= 0:
        return 0.0
    return (
        ((1000 / ergebnis) - 2.158) / 0.006
        if maennlich
        else ((800 / ergebnis) - 2.0232) / 0.00647
    )


@dataclass(frozen=True)
class AuswertungResult:
    total_students: int
    evaluated_students: int
    skipped_students: int


class AuswertungService:
    """Berechnet Gesamtpunktzahl und Urkunden für die aktive Event-Datenbank."""

    def __init__(self, config: Optional[dict] = None):
        # Von Enno
        # Die Bewertungs- und Urkundengrenzen stammen fachlich aus dem externen Auswertungs-Repo.
        self._config = config or get_default_auswertung_config()

    @classmethod
    def from_registry(cls, registry) -> "AuswertungService":
        return cls(registry.get_auswertung_config())

    def evaluate_database(self, db, *, year: Optional[int] = None) -> AuswertungResult:
        referenzjahr = int(year or datetime.now().year)
        kandidaten = db.get_auswertung_candidates()
        bewertet = 0
        uebersprungen = 0

        for schueler in kandidaten:
            punkte = self._calculate_points_for_student(schueler, referenzjahr=referenzjahr)
            if punkte is None:
                db.update_auswertung_result(
                    schueler_id=schueler["schueler_id"],
                    gesamtpunktzahl=None,
                    urkunde=None,
                )
                uebersprungen += 1
                continue

            alter = referenzjahr - int(schueler["geburtsjahr"])
            urkunde = self._punkte_zu_urkunde(
                punkte=punkte,
                alter=alter,
                geschlecht=str(schueler["geschlecht"] or "").strip().lower(),
            )
            db.update_auswertung_result(
                schueler_id=schueler["schueler_id"],
                gesamtpunktzahl=punkte,
                urkunde=urkunde,
            )
            bewertet += 1

        return AuswertungResult(
            total_students=len(kandidaten),
            evaluated_students=bewertet,
            skipped_students=uebersprungen,
        )

    def build_student_breakdown(
        self,
        schueler: dict,
        *,
        referenzjahr: int,
    ) -> Optional[dict]:
        """Berechnet Punkte je Disziplin sowie Gesamtpunktzahl fuer einen Schueler."""
        geschlecht = str(schueler["geschlecht"] or "").strip().lower()
        if geschlecht not in {"m", "w"}:
            return None

        alter = referenzjahr - int(schueler["geburtsjahr"])
        geschlecht_key = "male" if geschlecht == "m" else "female"
        alter_config = self._config["age_config"].get(geschlecht_key, {}).get(str(alter))
        if not alter_config:
            return None

        sprint = self._coerce_float(schueler.get("sprint"))
        wurf = self._coerce_float(schueler.get("wurf"))
        lauf = self._coerce_float(schueler.get("lauf"))
        sprung = self._coerce_float(schueler.get("sprung"))

        sprint_cfg = self._config["formula_config"]["sprint"]
        sprint_distanz = str(int(alter_config["sprint_distance"]))
        sprint_detail = sprint_cfg[geschlecht_key][sprint_distanz]
        lauf_detail = self._config["formula_config"]["lauf"][geschlecht_key]
        sprung_detail = self._config["formula_config"]["sprung"]["weit"][geschlecht_key]
        wurf_cfg_key = self._wurf_variant_key(int(alter_config["wurf_weight"]))
        wurf_detail = self._config["formula_config"]["wurf"][wurf_cfg_key][geschlecht_key]

        disziplinen = {
            "sprint": {
                "best_value": sprint if sprint > 0 else None,
                "points": int(
                    round(
                        self._score_sprint(
                            sprint,
                            int(sprint_distanz),
                            float(sprint_cfg["offset"]),
                            float(sprint_detail["base"]),
                            float(sprint_detail["divisor"]),
                        )
                    )
                )
                if sprint > 0
                else None,
            },
            "lauf": {
                "best_value": lauf if lauf > 0 else None,
                "points": int(
                    round(
                        self._score_lauf(
                            lauf,
                            float(lauf_detail["distance"]),
                            float(lauf_detail["base"]),
                            float(lauf_detail["divisor"]),
                        )
                    )
                )
                if lauf > 0
                else None,
            },
            "sprung": {
                "best_value": sprung if sprung > 0 else None,
                "points": int(
                    round(
                        self._score_sprung(
                            sprung,
                            float(sprung_detail["base"]),
                            float(sprung_detail["divisor"]),
                        )
                    )
                )
                if sprung > 0
                else None,
            },
            "wurf": {
                "best_value": wurf if wurf > 0 else None,
                "points": int(
                    round(
                        self._score_wurf(
                            wurf,
                            False,
                            False,
                            float(wurf_detail["base"]),
                            float(wurf_detail["divisor"]),
                        )
                    )
                )
                if wurf > 0
                else None,
                "variant": wurf_cfg_key,
                "weight": int(alter_config["wurf_weight"]),
            },
        }

        vorhandene_punkte = [
            wert["points"]
            for wert in disziplinen.values()
            if wert.get("points") is not None
        ]
        gesamtpunktzahl = None
        if len(vorhandene_punkte) >= 3:
            gesamtpunkte_liste = list(vorhandene_punkte)
            gesamtpunkte_liste.remove(min(gesamtpunkte_liste))
            gesamtpunktzahl = int(round(sum(gesamtpunkte_liste)))

        urkunde = None
        if gesamtpunktzahl is not None:
            urkunde = self._punkte_zu_urkunde(
                punkte=gesamtpunktzahl,
                alter=alter,
                geschlecht=geschlecht,
            )

        return {
            "alter": alter,
            "geschlecht_key": geschlecht_key,
            "disziplinen": disziplinen,
            "gesamtpunktzahl": gesamtpunktzahl,
            "urkunde": urkunde,
        }

    def _calculate_points_for_student(
        self,
        schueler: dict,
        *,
        referenzjahr: int,
    ) -> Optional[int]:
        breakdown = self.build_student_breakdown(
            schueler,
            referenzjahr=referenzjahr,
        )
        if not breakdown:
            return None
        return breakdown["gesamtpunktzahl"]

    def _punkte_zu_urkunde(self, *, punkte: int, alter: int, geschlecht: str) -> Optional[str]:
        schwellen = self._config["urkunde_config"].get(str(alter))
        if not schwellen:
            return None

        key = "M" if geschlecht == "m" else "W"
        grenzen = schwellen.get(key)
        if not grenzen:
            return None

        if punkte >= int(grenzen[1]):
            return "Ehrenurkunde"
        if punkte >= int(grenzen[0]):
            return "Siegerurkunde"
        return None

    @staticmethod
    def _wurf_gewicht_zu_bools(gewicht: int) -> tuple[bool, bool]:
        # Von Enno
        # Abbildung der Wurfgeräte-/Gewichtsklassen aus dem externen Auswertungs-Repo.
        if gewicht in {3, 4, 5, 6}:
            return True, True
        if gewicht == 80:
            return False, True
        if gewicht == 200:
            return False, False
        raise ValueError(f"Nicht unterstütztes Wurfgewicht: {gewicht}")

    @staticmethod
    def _coerce_float(value: object) -> float:
        if value in (None, "", "ABWESEND"):
            return 0.0
        return float(value)

    @staticmethod
    def _wurf_variant_key(gewicht: int) -> str:
        if gewicht in {3, 4, 5, 6}:
            return "stoss"
        if gewicht == 80:
            return "wurf_80g"
        return "wurf_ball"

    @staticmethod
    def _score_sprint(value: float, distance: int, offset: float, base: float, divisor: float) -> float:
        if value <= 0:
            return 0.0
        return ((distance / (value + offset)) - base) / divisor

    @staticmethod
    def _score_lauf(value: float, distance: float, base: float, divisor: float) -> float:
        if value <= 0:
            return 0.0
        return ((distance / value) - base) / divisor

    @staticmethod
    def _score_sprung(value: float, base: float, divisor: float) -> float:
        if value <= 0:
            return 0.0
        return (math.sqrt(value) - base) / divisor

    @staticmethod
    def _score_wurf(value: float, _ist_stoss: bool, _ist_80_gramm: bool, base: float, divisor: float) -> float:
        if value <= 0:
            return 0.0
        return (math.sqrt(value) - base) / divisor
