"""Zentrale, statische Disziplin-Konfiguration für die Anwendung."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisziplinDefinition:
    id: int
    name: str
    format: str
    num_rounds: int
    label: str
    hinweis: str


HARDCODED_DISZIPLINEN: tuple[DisziplinDefinition, ...] = (
    DisziplinDefinition(
        id=1,
        name="lauf",
        format="time",
        num_rounds=3,
        label="Laufen",
        hinweis="Zeitdisziplin für die Auswertungskategorie Lauf.",
    ),
    DisziplinDefinition(
        id=2,
        name="sprint",
        format="time",
        num_rounds=3,
        label="Sprinten",
        hinweis="Zeitdisziplin mit altersabhängiger Distanz von 50 m, 75 m oder 100 m.",
    ),
    DisziplinDefinition(
        id=3,
        name="sprung",
        format="distance",
        num_rounds=3,
        label="Weitsprung",
        hinweis="Distanzdisziplin für die Auswertungskategorie Sprung.",
    ),
    DisziplinDefinition(
        id=4,
        name="wurf",
        format="distance",
        num_rounds=3,
        label="Stoßen / Weitwurf",
        hinweis="Die Auswertung unterscheidet hier je Alter zwischen Stoßen und Weitwurf.",
    ),
)


# Von Enno
DISZIPLINEN_TAB_KONSTANTEN: tuple[dict[str, str], ...] = (
    {
        "titel": "Laufen",
        "technik_key": "lauf",
        "format": "Zeit",
        "runden": "3",
        "hinweis": "1000 m für Jungen, 800 m für Mädchen.",
    },
    {
        "titel": "Sprinten",
        "technik_key": "sprint",
        "format": "Zeit",
        "runden": "3",
        "hinweis": "Sprintstrecke abhängig von Alter und Geschlecht: 50 m, 75 m oder 100 m.",
    },
    {
        "titel": "Weitsprung",
        "technik_key": "sprung",
        "format": "Distanz",
        "runden": "3",
        "hinweis": "Verwendet die Weitsprung-Formel aus der Enno-Auswertung.",
    },
    {
        "titel": "Stoßen",
        "technik_key": "wurf",
        "format": "Distanz",
        "runden": "3",
        "hinweis": "Altersabhängig mit Geräten von 3 kg bis 6 kg.",
    },
    {
        "titel": "Weitwurf",
        "technik_key": "wurf",
        "format": "Distanz",
        "runden": "3",
        "hinweis": "Altersabhängig mit 80 g oder 200 g Ball.",
    },
)


def get_hardcoded_disziplinen() -> list[DisziplinDefinition]:
    return list(HARDCODED_DISZIPLINEN)


def get_disziplinen_tab_konstanten() -> list[dict[str, str]]:
    return [dict(eintrag) for eintrag in DISZIPLINEN_TAB_KONSTANTEN]
