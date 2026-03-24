"""Auswertung der BJS-Gesamtpunkte auf Basis der Event-Datenbank."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.auswertung_config import get_default_auswertung_config


def _auswertung_sprint(ergebnis: float, maennlich: bool, strecke: int) -> float:
    # Von Enno
    # Bewertungsformel fuer Sprint aus dem externen Auswertungs-Repo uebernommen.
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
    raise ValueError(f"Ungueltige Sprintstrecke: {strecke}")


def _auswertung_sprung(ergebnis: float, maennlich: bool, weit: bool) -> float:
    # Von Enno
    # Bewertungsformel fuer Sprung aus dem externen Auswertungs-Repo uebernommen.
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
    # Bewertungsformel fuer Wurf/Stoss aus dem externen Auswertungs-Repo uebernommen.
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
    # Bewertungsformel fuer Lauf aus dem externen Auswertungs-Repo uebernommen.
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
    """Berechnet Gesamtpunktzahl und Urkunden fuer die aktive Event-Datenbank."""

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

    def _calculate_points_for_student(
        self,
        schueler: dict,
        *,
        referenzjahr: int,
    ) -> Optional[int]:
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

        if sum(1 for wert in (sprint, wurf, lauf, sprung) if wert and wert > 0) < 3:
            return None

        maennlich = geschlecht == "m"
        wurf_stoss, wurf_80g = self._wurf_gewicht_zu_bools(alter_config["wurf_weight"])
        sprint_cfg = self._config["formula_config"]["sprint"]
        sprint_gender_key = "male" if maennlich else "female"
        sprint_distanz = str(int(alter_config["sprint_distance"]))
        sprint_base = float(sprint_cfg[sprint_gender_key][sprint_distanz]["base"])
        sprint_divisor = float(sprint_cfg[sprint_gender_key][sprint_distanz]["divisor"])
        sprint_offset = float(sprint_cfg["offset"])

        lauf_cfg = self._config["formula_config"]["lauf"][sprint_gender_key]
        sprung_cfg = self._config["formula_config"]["sprung"]["weit"][sprint_gender_key]
        wurf_cfg_key = self._wurf_variant_key(int(alter_config["wurf_weight"]))
        wurf_cfg = self._config["formula_config"]["wurf"][wurf_cfg_key][sprint_gender_key]
        punkte = [
            self._score_sprint(sprint, int(sprint_distanz), sprint_offset, sprint_base, sprint_divisor),
            self._score_wurf(wurf, wurf_stoss, wurf_80g, float(wurf_cfg["base"]), float(wurf_cfg["divisor"])),
            self._score_lauf(lauf, float(lauf_cfg["distance"]), float(lauf_cfg["base"]), float(lauf_cfg["divisor"])),
            self._score_sprung(sprung, float(sprung_cfg["base"]), float(sprung_cfg["divisor"])),
        ]

        punkte.remove(min(punkte))
        return int(round(sum(punkte)))

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
        # Abbildung der Wurfgeraete-/Gewichtsklassen aus dem externen Auswertungs-Repo.
        if gewicht in {3, 4, 5, 6}:
            return True, True
        if gewicht == 80:
            return False, True
        if gewicht == 200:
            return False, False
        raise ValueError(f"Nicht unterstuetztes Wurfgewicht: {gewicht}")

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
