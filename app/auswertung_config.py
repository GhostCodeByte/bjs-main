"""Standardkonfiguration und Validierung fuer die bearbeitbare BJS-Auswertung."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Von Enno
# Standardwerte fuer Formeln, Altersprofile und Urkundengrenzen stammen fachlich aus dem externen Auswertungs-Repo.
DEFAULT_AUSWERTUNG_CONFIG: dict[str, Any] = {
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
    return deepcopy(DEFAULT_AUSWERTUNG_CONFIG)


def deep_merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge_config(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def validate_auswertung_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = deep_merge_config(get_default_auswertung_config(), config or {})

    sprint_offset = float(merged["formula_config"]["sprint"]["offset"])
    if sprint_offset < 0:
        raise ValueError("Sprint-Offset darf nicht negativ sein")

    for geschlecht in ("male", "female"):
        for strecke in ("50", "75", "100"):
            _validate_positive_formula_pair(
                merged["formula_config"]["sprint"][geschlecht][strecke],
                label=f"Sprint {geschlecht} {strecke}m",
            )
        _validate_positive_formula_triple(
            merged["formula_config"]["lauf"][geschlecht],
            label=f"Lauf {geschlecht}",
            include_distance=True,
        )
        _validate_positive_formula_pair(
            merged["formula_config"]["sprung"]["weit"][geschlecht],
            label=f"Sprung {geschlecht}",
        )
        for wurf_key in ("stoss", "wurf_80g", "wurf_ball"):
            _validate_positive_formula_pair(
                merged["formula_config"]["wurf"][wurf_key][geschlecht],
                label=f"Wurf {wurf_key} {geschlecht}",
            )

    for geschlecht in ("male", "female"):
        for alter, values in merged["age_config"][geschlecht].items():
            int(alter)
            sprint_distance = int(values["sprint_distance"])
            wurf_weight = int(values["wurf_weight"])
            if sprint_distance not in {50, 75, 100}:
                raise ValueError(f"Ungueltige Sprintdistanz fuer Alter {alter}")
            if wurf_weight not in {3, 4, 5, 6, 80, 200}:
                raise ValueError(f"Ungueltiges Wurfgewicht fuer Alter {alter}")

    for alter, values in merged["urkunde_config"].items():
        int(alter)
        for key in ("M", "W"):
            grenzen = values.get(key)
            if not isinstance(grenzen, list) or len(grenzen) != 2:
                raise ValueError(f"Urkundengrenzen fuer Alter {alter} / {key} sind ungueltig")
            sieger = int(grenzen[0])
            ehre = int(grenzen[1])
            if sieger < 0 or ehre < 0 or sieger > ehre:
                raise ValueError(f"Urkundengrenzen fuer Alter {alter} / {key} sind ungueltig")

    return merged


def _validate_positive_formula_pair(data: dict[str, Any], *, label: str) -> None:
    float(data["base"])
    divisor = float(data["divisor"])
    if divisor <= 0:
        raise ValueError(f"{label}: divisor muss > 0 sein")


def _validate_positive_formula_triple(
    data: dict[str, Any],
    *,
    label: str,
    include_distance: bool = False,
) -> None:
    if include_distance and float(data["distance"]) <= 0:
        raise ValueError(f"{label}: distance muss > 0 sein")
    _validate_positive_formula_pair(data, label=label)
