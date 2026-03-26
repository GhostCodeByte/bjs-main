"""Berechnet Gesamtpunkte und Urkunden inklusive statischer Bewertungsdaten."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

# Von Enno:
# Die fachlichen Standardwerte fuer Formeln, Altersprofile und Urkundengrenzen
# stammen aus dem externen Auswertungs-Stand und liegen jetzt direkt im
# Auswertungsmodul, damit keine separate `auswertung_config.py` mehr noetig ist.
STANDARD_AUSWERTUNGSKONFIGURATION: dict[str, Any] = {
    "formula_config": {
        "sprint": {
            "offset": 0.24,
            "male": {
                "50": {"base": 3.79, "divisor": 0.0069},
                "75": {"base": 4.1, "divisor": 0.00664},
                "100": {"base": 4.341, "divisor": 0.00676},
            },
            "female": {
                "50": {"base": 3.648, "divisor": 0.0066},
                "75": {"base": 3.998, "divisor": 0.0066},
                "100": {"base": 4.0062, "divisor": 0.00656},
            },
        },
        "lauf": {
            "male": {"distance": 1000.0, "base": 2.158, "divisor": 0.006},
            "female": {"distance": 800.0, "base": 2.0232, "divisor": 0.00647},
        },
        "sprung": {
            "weit": {
                "male": {"base": 1.15028, "divisor": 0.00219},
                "female": {"base": 1.0935, "divisor": 0.00208},
            }
        },
        "wurf": {
            "stoss": {
                "male": {"base": 1.425, "divisor": 0.0037},
                "female": {"base": 1.279, "divisor": 0.00398},
            },
            "wurf_80g": {
                "male": {"base": 2.8, "divisor": 0.011},
                "female": {"base": 2.0232, "divisor": 0.00874},
            },
            "wurf_ball": {
                "male": {"base": 1.936, "divisor": 0.0124},
                "female": {"base": 1.4149, "divisor": 0.01039},
            },
        },
    },
    "age_config": {
        "male": {
            "10": {"sprint_distance": 50, "wurf_weight": 80},
            "11": {"sprint_distance": 50, "wurf_weight": 80},
            "12": {"sprint_distance": 50, "wurf_weight": 200},
            "13": {"sprint_distance": 50, "wurf_weight": 200},
            "14": {"sprint_distance": 75, "wurf_weight": 200},
            "15": {"sprint_distance": 75, "wurf_weight": 4},
            "16": {"sprint_distance": 100, "wurf_weight": 5},
            "17": {"sprint_distance": 100, "wurf_weight": 5},
            "18": {"sprint_distance": 100, "wurf_weight": 6},
            "19": {"sprint_distance": 100, "wurf_weight": 6},
        },
        "female": {
            "10": {"sprint_distance": 50, "wurf_weight": 80},
            "11": {"sprint_distance": 50, "wurf_weight": 80},
            "12": {"sprint_distance": 50, "wurf_weight": 80},
            "13": {"sprint_distance": 50, "wurf_weight": 80},
            "14": {"sprint_distance": 75, "wurf_weight": 200},
            "15": {"sprint_distance": 75, "wurf_weight": 3},
            "16": {"sprint_distance": 100, "wurf_weight": 3},
            "17": {"sprint_distance": 100, "wurf_weight": 3},
            "18": {"sprint_distance": 100, "wurf_weight": 4},
            "19": {"sprint_distance": 100, "wurf_weight": 4},
        },
    },
    "urkunde_config": {
        "10": {"M": [600, 775], "W": [625, 825]},
        "11": {"M": [675, 875], "W": [700, 900]},
        "12": {"M": [750, 975], "W": [775, 975]},
        "13": {"M": [825, 1050], "W": [825, 1025]},
        "14": {"M": [900, 1125], "W": [850, 1050]},
        "15": {"M": [975, 1225], "W": [875, 1075]},
        "16": {"M": [1050, 1325], "W": [900, 1100]},
        "17": {"M": [1125, 1400], "W": [925, 1125]},
        "18": {"M": [1200, 1475], "W": [950, 1150]},
        "19": {"M": [1275, 1550], "W": [950, 1150]},
    },
}


def get_default_auswertung_config() -> dict[str, Any]:
    """Liefert eine tiefe Kopie der festen Auswertungskonfiguration."""
    return deepcopy(STANDARD_AUSWERTUNGSKONFIGURATION)


def deep_merge_config(
    basis_konfiguration: dict[str, Any],
    ueberschreibungen: dict[str, Any],
) -> dict[str, Any]:
    """Fuehrt zwei verschachtelte Konfigurationsdictionaries rekursiv zusammen."""
    zusammengefuehrte_konfiguration = deepcopy(basis_konfiguration)
    for schluessel, wert in (ueberschreibungen or {}).items():
        if isinstance(wert, dict) and isinstance(
            zusammengefuehrte_konfiguration.get(schluessel), dict
        ):
            zusammengefuehrte_konfiguration[schluessel] = deep_merge_config(
                zusammengefuehrte_konfiguration[schluessel],
                wert,
            )
        else:
            zusammengefuehrte_konfiguration[schluessel] = deepcopy(wert)
    return zusammengefuehrte_konfiguration


def validate_auswertung_config(konfiguration: dict[str, Any]) -> dict[str, Any]:
    """Validiert eine Auswertungskonfiguration gegen alle bekannten Fachgrenzen."""
    zusammengefuehrte_konfiguration = deep_merge_config(
        get_default_auswertung_config(),
        konfiguration or {},
    )

    sprint_offset = float(
        zusammengefuehrte_konfiguration["formula_config"]["sprint"]["offset"]
    )
    if sprint_offset < 0:
        raise ValueError("Sprint-Offset darf nicht negativ sein")

    for geschlecht in ("male", "female"):
        for strecke in ("50", "75", "100"):
            _validate_positive_formula_pair(
                zusammengefuehrte_konfiguration["formula_config"]["sprint"][
                    geschlecht
                ][strecke],
                label=f"Sprint {geschlecht} {strecke}m",
            )
        _validate_positive_formula_triple(
            zusammengefuehrte_konfiguration["formula_config"]["lauf"][geschlecht],
            label=f"Lauf {geschlecht}",
            include_distance=True,
        )
        _validate_positive_formula_pair(
            zusammengefuehrte_konfiguration["formula_config"]["sprung"]["weit"][
                geschlecht
            ],
            label=f"Sprung {geschlecht}",
        )
        for wurf_schluessel in ("stoss", "wurf_80g", "wurf_ball"):
            _validate_positive_formula_pair(
                zusammengefuehrte_konfiguration["formula_config"]["wurf"][
                    wurf_schluessel
                ][geschlecht],
                label=f"Wurf {wurf_schluessel} {geschlecht}",
            )

    for geschlecht in ("male", "female"):
        for alter, alterswerte in zusammengefuehrte_konfiguration["age_config"][
            geschlecht
        ].items():
            int(alter)
            sprint_distanz = int(alterswerte["sprint_distance"])
            wurf_gewicht = int(alterswerte["wurf_weight"])
            if sprint_distanz not in {50, 75, 100}:
                raise ValueError(f"Ungueltige Sprintdistanz fuer Alter {alter}")
            if wurf_gewicht not in {3, 4, 5, 6, 80, 200}:
                raise ValueError(f"Ungueltiges Wurfgewicht fuer Alter {alter}")

    for alter, urkundenwerte in zusammengefuehrte_konfiguration[
        "urkunde_config"
    ].items():
        int(alter)
        for geschlecht in ("M", "W"):
            grenzen = urkundenwerte.get(geschlecht)
            if not isinstance(grenzen, list) or len(grenzen) != 2:
                raise ValueError(
                    f"Urkundengrenzen fuer Alter {alter} / {geschlecht} sind ungueltig"
                )
            sieger_grenze = int(grenzen[0])
            ehren_grenze = int(grenzen[1])
            if sieger_grenze < 0 or ehren_grenze < 0 or sieger_grenze > ehren_grenze:
                raise ValueError(
                    f"Urkundengrenzen fuer Alter {alter} / {geschlecht} sind ungueltig"
                )

    return zusammengefuehrte_konfiguration


def _validate_positive_formula_pair(daten: dict[str, Any], *, label: str) -> None:
    """Prueft, dass ein Formelblock eine positive Divisor-Angabe besitzt."""
    float(daten["base"])
    divisor = float(daten["divisor"])
    if divisor <= 0:
        raise ValueError(f"{label}: divisor muss > 0 sein")


def _validate_positive_formula_triple(
    daten: dict[str, Any],
    *,
    label: str,
    include_distance: bool = False,
) -> None:
    """Prueft optional Distanz sowie die restlichen Werte eines Formelblocks."""
    if include_distance and float(daten["distance"]) <= 0:
        raise ValueError(f"{label}: distance muss > 0 sein")
    _validate_positive_formula_pair(daten, label=label)


@dataclass(frozen=True)
class AuswertungResult:
    """Fasst das Ergebnis eines kompletten Auswertungslaufs zusammen."""

    total_students: int
    evaluated_students: int
    skipped_students: int


class AuswertungService:
    """Berechnet Gesamtpunktzahl und Urkunden fuer die aktive Event-Datenbank."""

    def __init__(self, konfiguration: Optional[dict[str, Any]] = None):
        """Initialisiert den Service mit fester oder uebergebener Konfiguration."""
        self._konfiguration = konfiguration or get_default_auswertung_config()

    @classmethod
    def from_registry(cls, registry) -> "AuswertungService":
        """Erzeugt den Service direkt aus der aktuell verfuegbaren Registry."""
        return cls(registry.get_auswertung_config())

    def evaluate_database(self, db, *, year: Optional[int] = None) -> AuswertungResult:
        """Berechnet fuer alle Kandidaten Punkte und Urkunden in der Event-Datenbank."""
        referenzjahr = int(year or datetime.now().year)
        kandidaten = db.get_auswertung_candidates()
        bewertete_schueler = 0
        uebersprungene_schueler = 0

        for schueler in kandidaten:
            gesamtpunkte = self._calculate_points_for_student(
                schueler,
                referenzjahr=referenzjahr,
            )
            if gesamtpunkte is None:
                db.update_auswertung_result(
                    schueler_id=schueler["schueler_id"],
                    gesamtpunktzahl=None,
                    urkunde=None,
                )
                uebersprungene_schueler += 1
                continue

            alter = referenzjahr - int(schueler["geburtsjahr"])
            urkunde = self._punkte_zu_urkunde(
                punkte=gesamtpunkte,
                alter=alter,
                geschlecht=str(schueler["geschlecht"] or "").strip().lower(),
            )
            db.update_auswertung_result(
                schueler_id=schueler["schueler_id"],
                gesamtpunktzahl=gesamtpunkte,
                urkunde=urkunde,
            )
            bewertete_schueler += 1

        return AuswertungResult(
            total_students=len(kandidaten),
            evaluated_students=bewertete_schueler,
            skipped_students=uebersprungene_schueler,
        )

    def build_student_breakdown(
        self,
        schueler: dict[str, Any],
        *,
        referenzjahr: int,
    ) -> Optional[dict[str, Any]]:
        """Berechnet Punkte je Disziplin sowie Gesamtpunktzahl fuer einen Schueler."""
        geschlecht = str(schueler["geschlecht"] or "").strip().lower()
        if geschlecht not in {"m", "w"}:
            return None

        alter = referenzjahr - int(schueler["geburtsjahr"])
        geschlecht_schluessel = "male" if geschlecht == "m" else "female"
        altersprofil = self._konfiguration["age_config"].get(
            geschlecht_schluessel,
            {},
        ).get(str(alter))
        if not altersprofil:
            return None

        sprint_wert = self._coerce_float(schueler.get("sprint"))
        wurf_wert = self._coerce_float(schueler.get("wurf"))
        lauf_wert = self._coerce_float(schueler.get("lauf"))
        sprung_wert = self._coerce_float(schueler.get("sprung"))

        sprint_konfiguration = self._konfiguration["formula_config"]["sprint"]
        sprint_distanz = str(int(altersprofil["sprint_distance"]))
        sprint_details = sprint_konfiguration[geschlecht_schluessel][sprint_distanz]
        lauf_details = self._konfiguration["formula_config"]["lauf"][
            geschlecht_schluessel
        ]
        sprung_details = self._konfiguration["formula_config"]["sprung"]["weit"][
            geschlecht_schluessel
        ]
        wurf_schluessel = self._wurf_variant_key(int(altersprofil["wurf_weight"]))
        wurf_details = self._konfiguration["formula_config"]["wurf"][wurf_schluessel][
            geschlecht_schluessel
        ]

        disziplinen = {
            "sprint": {
                "best_value": sprint_wert if sprint_wert > 0 else None,
                "points": int(
                    round(
                        self._score_sprint(
                            sprint_wert,
                            int(sprint_distanz),
                            float(sprint_konfiguration["offset"]),
                            float(sprint_details["base"]),
                            float(sprint_details["divisor"]),
                        )
                    )
                )
                if sprint_wert > 0
                else None,
            },
            "lauf": {
                "best_value": lauf_wert if lauf_wert > 0 else None,
                "points": int(
                    round(
                        self._score_lauf(
                            lauf_wert,
                            float(lauf_details["distance"]),
                            float(lauf_details["base"]),
                            float(lauf_details["divisor"]),
                        )
                    )
                )
                if lauf_wert > 0
                else None,
            },
            "sprung": {
                "best_value": sprung_wert if sprung_wert > 0 else None,
                "points": int(
                    round(
                        self._score_sprung(
                            sprung_wert,
                            float(sprung_details["base"]),
                            float(sprung_details["divisor"]),
                        )
                    )
                )
                if sprung_wert > 0
                else None,
            },
            "wurf": {
                "best_value": wurf_wert if wurf_wert > 0 else None,
                "points": int(
                    round(
                        self._score_wurf(
                            wurf_wert,
                            float(wurf_details["base"]),
                            float(wurf_details["divisor"]),
                        )
                    )
                )
                if wurf_wert > 0
                else None,
                "variant": wurf_schluessel,
                "weight": int(altersprofil["wurf_weight"]),
            },
        }

        vorhandene_punkte = [
            werte["points"]
            for werte in disziplinen.values()
            if werte.get("points") is not None
        ]
        gesamtpunktzahl = None
        if len(vorhandene_punkte) >= 3:
            gewertete_punkte = list(vorhandene_punkte)
            if len(gewertete_punkte) > 3:
                gewertete_punkte.remove(min(gewertete_punkte))
            gesamtpunktzahl = int(round(sum(gewertete_punkte)))

        urkunde = None
        if gesamtpunktzahl is not None:
            urkunde = self._punkte_zu_urkunde(
                punkte=gesamtpunktzahl,
                alter=alter,
                geschlecht=geschlecht,
            )

        return {
            "alter": alter,
            "geschlecht_key": geschlecht_schluessel,
            "disziplinen": disziplinen,
            "gesamtpunktzahl": gesamtpunktzahl,
            "urkunde": urkunde,
        }

    def _calculate_points_for_student(
        self,
        schueler: dict[str, Any],
        *,
        referenzjahr: int,
    ) -> Optional[int]:
        """Leitet nur die Gesamtpunktzahl aus dem Schueler-Breakdown ab."""
        breakdown = self.build_student_breakdown(
            schueler,
            referenzjahr=referenzjahr,
        )
        if not breakdown:
            return None
        return breakdown["gesamtpunktzahl"]

    def _punkte_zu_urkunde(
        self,
        *,
        punkte: int,
        alter: int,
        geschlecht: str,
    ) -> Optional[str]:
        """Ordnet eine Gesamtpunktzahl den Urkundenstufen zu."""
        urkundenschwellen = self._konfiguration["urkunde_config"].get(str(alter))
        if not urkundenschwellen:
            return None

        geschlecht_schluessel = "M" if geschlecht == "m" else "W"
        grenzen = urkundenschwellen.get(geschlecht_schluessel)
        if not grenzen:
            return None

        if punkte >= int(grenzen[1]):
            return "Ehrenurkunde"
        if punkte >= int(grenzen[0]):
            return "Siegerurkunde"
        return None

    @staticmethod
    def _coerce_float(wert: object) -> float:
        """Normalisiert gespeicherte Werte auf Float inklusive Sonderfall ABWESEND."""
        if wert in (None, "", "ABWESEND"):
            return 0.0
        return float(wert)

    @staticmethod
    def _wurf_variant_key(gewicht: int) -> str:
        """Leitet aus dem Wurfgewicht den passenden Formelblock ab."""
        if gewicht in {3, 4, 5, 6}:
            return "stoss"
        if gewicht == 80:
            return "wurf_80g"
        return "wurf_ball"

    @staticmethod
    def _score_sprint(
        wert: float,
        distanz: int,
        offset: float,
        basiswert: float,
        divisor: float,
    ) -> float:
        """Berechnet die Sprintpunkte aus Strecke, Zeit und Formelparametern."""
        if wert <= 0:
            return 0.0
        return ((distanz / (wert + offset)) - basiswert) / divisor

    @staticmethod
    def _score_lauf(
        wert: float,
        distanz: float,
        basiswert: float,
        divisor: float,
    ) -> float:
        """Berechnet die Laufpunkte aus Distanz, Zeit und Formelparametern."""
        if wert <= 0:
            return 0.0
        return ((distanz / wert) - basiswert) / divisor

    @staticmethod
    def _score_sprung(wert: float, basiswert: float, divisor: float) -> float:
        """Berechnet die Sprungpunkte aus Weite und Formelparametern."""
        if wert <= 0:
            return 0.0
        return (math.sqrt(wert) - basiswert) / divisor

    @staticmethod
    def _score_wurf(wert: float, basiswert: float, divisor: float) -> float:
        """Berechnet die Wurfpunkte aus Weite und Formelparametern."""
        if wert <= 0:
            return 0.0
        return (math.sqrt(wert) - basiswert) / divisor
