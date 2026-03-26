"""Statische Disziplindefinitionen und UI-Texte fuer die Anwendung."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisziplinDefinition:
    """Beschreibt eine im Code fest hinterlegte Disziplin."""

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
        hinweis="Zeitdisziplin fuer die Auswertungskategorie Lauf.",
    ),
    DisziplinDefinition(
        id=2,
        name="sprint",
        format="time",
        num_rounds=3,
        label="Sprinten",
        hinweis="Zeitdisziplin mit altersabhaengiger Distanz von 50 m, 75 m oder 100 m.",
    ),
    DisziplinDefinition(
        id=3,
        name="sprung",
        format="distance",
        num_rounds=3,
        label="Weitsprung",
        hinweis="Distanzdisziplin fuer die Auswertungskategorie Sprung.",
    ),
    DisziplinDefinition(
        id=4,
        name="wurf",
        format="distance",
        num_rounds=3,
        label="Stossen / Weitwurf",
        hinweis="Die Auswertung unterscheidet hier je Alter zwischen Stossen und Weitwurf.",
    ),
)


# Von Enno:
# Diese Texte spiegeln die fachlichen Hinweise fuer den Admin-Tab wider und
# bleiben statisch im Code, damit keine lose Konfigurationsdatei noetig ist.
DISZIPLINEN_TAB_KONSTANTEN: tuple[dict[str, str], ...] = (
    {
        "titel": "Laufen",
        "technik_key": "lauf",
        "format": "Zeit",
        "runden": "3",
        "hinweis": "1000 m fuer Jungen, 800 m fuer Maedchen.",
    },
    {
        "titel": "Sprinten",
        "technik_key": "sprint",
        "format": "Zeit",
        "runden": "3",
        "hinweis": "Sprintstrecke abhaengig von Alter und Geschlecht: 50 m, 75 m oder 100 m.",
    },
    {
        "titel": "Weitsprung",
        "technik_key": "sprung",
        "format": "Distanz",
        "runden": "3",
        "hinweis": "Verwendet die Weitsprung-Formel aus der Enno-Auswertung.",
    },
    {
        "titel": "Stossen",
        "technik_key": "wurf",
        "format": "Distanz",
        "runden": "3",
        "hinweis": "Altersabhaengig mit Geraeten von 3 kg bis 6 kg.",
    },
    {
        "titel": "Weitwurf",
        "technik_key": "wurf",
        "format": "Distanz",
        "runden": "3",
        "hinweis": "Altersabhaengig mit 80 g oder 200 g Ball.",
    },
)


def get_hardcoded_disziplinen() -> list[DisziplinDefinition]:
    """Liefert alle fest verdrahteten Disziplinen als neue Liste."""
    return list(HARDCODED_DISZIPLINEN)


def get_disziplinen_tab_konstanten() -> list[dict[str, str]]:
    """Liefert die festen Anzeigeinhalte fuer den Disziplinen-Tab."""
    return [dict(eintrag) for eintrag in DISZIPLINEN_TAB_KONSTANTEN]
