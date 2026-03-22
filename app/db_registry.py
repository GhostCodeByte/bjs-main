"""Verwaltet die Registry für Event-Datenbanken und globale Disziplinen."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class RegisteredDb:
    """Beschreibt eine in der Meta-Datenbank registrierte Event-Datenbank."""

    name: str
    path: str
    label: str
    year: Optional[int]
    created_at: str
    file_size: int


@dataclass(frozen=True)
class Disziplin:
    """Beschreibt eine global verwaltete Disziplin."""

    id: int
    name: str
    format: str
    num_rounds: int


class DbRegistry:
    """Kapselt die Meta-Datenbank für Datenbankauswahl und Disziplinverwaltung."""

    def __init__(self, meta_db_path: str | Path):
        """Initialisiert die Registry und stellt das Schema sicher."""
        self.meta_db_path = Path(meta_db_path)
        self.meta_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Öffnet eine SQLite-Verbindung zur Meta-Datenbank."""
        verbindung = sqlite3.connect(str(self.meta_db_path))
        verbindung.execute("PRAGMA foreign_keys = ON;")
        return verbindung

    def _ensure_schema(self) -> None:
        """Legt alle benötigten Tabellen der Meta-Datenbank an."""
        with self._connect() as verbindung:
            verbindung.execute(
                """
                CREATE TABLE IF NOT EXISTS Db_Registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    path TEXT NOT NULL UNIQUE,
                    label TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL,
                    file_size INTEGER NOT NULL DEFAULT 0,
                    extra_json TEXT
                );
                """
            )
            verbindung.execute(
                """
                CREATE TABLE IF NOT EXISTS App_Config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            verbindung.execute(
                """
                CREATE TABLE IF NOT EXISTS Disziplinen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    format TEXT NOT NULL CHECK (format IN ('time', 'distance')) DEFAULT 'distance',
                    num_rounds INTEGER NOT NULL CHECK (num_rounds BETWEEN 1 AND 5) DEFAULT 3,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            vorhandene_spalten = [
                zeile[1]
                for zeile in verbindung.execute(
                    "PRAGMA table_info(Disziplinen)"
                ).fetchall()
            ]
            if "unit" in vorhandene_spalten:
                # Alte Datenbanken enthielten noch eine `unit`-Spalte, die heute nicht mehr genutzt wird.
                verbindung.execute("PRAGMA foreign_keys = OFF;")
                verbindung.execute("ALTER TABLE Disziplinen RENAME TO Disziplinen_old;")
                verbindung.execute(
                    """
                    CREATE TABLE Disziplinen (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        format TEXT NOT NULL CHECK (format IN ('time', 'distance')) DEFAULT 'distance',
                        num_rounds INTEGER NOT NULL CHECK (num_rounds BETWEEN 1 AND 5) DEFAULT 3,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                verbindung.execute(
                    """
                    INSERT INTO Disziplinen (id, name, format, num_rounds, created_at)
                    SELECT id, name, format, num_rounds, created_at
                    FROM Disziplinen_old;
                    """
                )
                verbindung.execute("DROP TABLE Disziplinen_old;")
                verbindung.execute("PRAGMA foreign_keys = ON;")

    def get_active_db_path(self) -> Optional[str]:
        """Liest den Pfad der aktuell ausgewählten Event-Datenbank aus."""
        with self._connect() as verbindung:
            zeile = verbindung.execute(
                "SELECT value FROM App_Config WHERE key = 'active_db_path'"
            ).fetchone()
            if not zeile:
                return None

            gespeicherter_wert = zeile[0]
            try:
                dekodierter_wert = json.loads(gespeicherter_wert)
            except Exception:
                dekodierter_wert = gespeicherter_wert

            if not dekodierter_wert:
                return None
            return str(dekodierter_wert)

    def set_active_db_path(self, path: str | Path) -> None:
        """Speichert den Pfad der aktuell aktiven Event-Datenbank."""
        datenbankpfad = str(Path(path))
        with self._connect() as verbindung:
            verbindung.execute(
                "INSERT OR REPLACE INTO App_Config (key, value) VALUES (?, ?)",
                ("active_db_path", json.dumps(datenbankpfad)),
            )

    def register_db(
        self,
        *,
        path: str | Path,
        name: str,
        label: str = "",
        year: Optional[int] = None,
        created_at: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """Registriert eine Event-Datenbank oder aktualisiert einen vorhandenen Eintrag."""
        datenbankpfad = Path(path)
        erstellt_am = created_at or datetime.now().isoformat(timespec="seconds")
        dateigroesse = datenbankpfad.stat().st_size if datenbankpfad.exists() else 0

        with self._connect() as verbindung:
            verbindung.execute(
                """
                INSERT OR REPLACE INTO Db_Registry (name, path, label, year, created_at, file_size, extra_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    str(datenbankpfad),
                    label,
                    year,
                    erstellt_am,
                    dateigroesse,
                    json.dumps(extra or {}),
                ),
            )

    def list_dbs(self) -> list[RegisteredDb]:
        """Liefert alle registrierten Event-Datenbanken in absteigender Zeitreihenfolge."""
        with self._connect() as verbindung:
            zeilen = verbindung.execute(
                """
                SELECT name, path, COALESCE(label, ''), year, created_at, file_size
                FROM Db_Registry
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [
            RegisteredDb(
                name=zeile[0],
                path=zeile[1],
                label=zeile[2] or "",
                year=zeile[3],
                created_at=zeile[4],
                file_size=int(zeile[5] or 0),
            )
            for zeile in zeilen
        ]

    def get_by_name(self, name: str) -> Optional[RegisteredDb]:
        """Lädt genau einen Registry-Eintrag über seinen Dateinamen."""
        with self._connect() as verbindung:
            zeile = verbindung.execute(
                """
                SELECT name, path, COALESCE(label, ''), year, created_at, file_size
                FROM Db_Registry
                WHERE name = ?
                """,
                (name,),
            ).fetchone()

        if not zeile:
            return None

        return RegisteredDb(
            name=zeile[0],
            path=zeile[1],
            label=zeile[2] or "",
            year=zeile[3],
            created_at=zeile[4],
            file_size=int(zeile[5] or 0),
        )

    def ensure_registered(
        self, db_path: str | Path, *, default_label: str = ""
    ) -> None:
        """Registriert eine Datenbank nur dann, wenn sie noch nicht bekannt ist."""
        datenbankpfad = Path(db_path)
        if self.get_by_name(datenbankpfad.name):
            return
        self.register_db(
            path=datenbankpfad,
            name=datenbankpfad.name,
            label=default_label,
        )

    def delete_db(self, name: str, *, delete_file: bool = True) -> bool:
        """Entfernt einen Registry-Eintrag und optional die eigentliche Datenbankdatei."""
        eintrag = self.get_by_name(name)
        if not eintrag:
            return False

        aktiver_pfad = self.get_active_db_path()
        if aktiver_pfad and Path(aktiver_pfad) == Path(eintrag.path):
            with self._connect() as verbindung:
                verbindung.execute("DELETE FROM App_Config WHERE key = 'active_db_path'")

        with self._connect() as verbindung:
            verbindung.execute("DELETE FROM Db_Registry WHERE name = ?", (name,))

        if delete_file:
            datenbankpfad = Path(eintrag.path)
            if datenbankpfad.exists():
                datenbankpfad.unlink()

        return True

    def get_disziplinen(self) -> list[Disziplin]:
        """Liefert alle globalen Disziplinen alphabetisch sortiert."""
        with self._connect() as verbindung:
            zeilen = verbindung.execute(
                """
                SELECT id, name, format, num_rounds
                FROM Disziplinen
                ORDER BY name
                """
            ).fetchall()

        return [
            Disziplin(
                id=zeile[0],
                name=zeile[1],
                format=zeile[2],
                num_rounds=zeile[3],
            )
            for zeile in zeilen
        ]

    def get_disziplin(self, disziplin_id: int) -> Optional[Disziplin]:
        """Lädt eine Disziplin anhand ihrer ID."""
        with self._connect() as verbindung:
            zeile = verbindung.execute(
                """
                SELECT id, name, format, num_rounds
                FROM Disziplinen WHERE id = ?
                """,
                (disziplin_id,),
            ).fetchone()

        if not zeile:
            return None

        return Disziplin(
            id=zeile[0],
            name=zeile[1],
            format=zeile[2],
            num_rounds=zeile[3],
        )

    def get_disziplin_by_name(self, name: str) -> Optional[Disziplin]:
        """Lädt eine Disziplin anhand ihres eindeutigen Namens."""
        with self._connect() as verbindung:
            zeile = verbindung.execute(
                """
                SELECT id, name, format, num_rounds
                FROM Disziplinen WHERE name = ?
                """,
                (name,),
            ).fetchone()

        if not zeile:
            return None

        return Disziplin(
            id=zeile[0],
            name=zeile[1],
            format=zeile[2],
            num_rounds=zeile[3],
        )

    def create_disziplin(
        self,
        name: str,
        format: str = "distance",
        num_rounds: int = 3,
    ) -> int:
        """Legt eine neue Disziplin in der Meta-Datenbank an."""
        with self._connect() as verbindung:
            cursor = verbindung.execute(
                """
                INSERT INTO Disziplinen (name, format, num_rounds)
                VALUES (?, ?, ?)
                """,
                (name, format, num_rounds),
            )
            return cursor.lastrowid or 0

    def update_disziplin(
        self,
        disziplin_id: int,
        name: Optional[str] = None,
        format: Optional[str] = None,
        num_rounds: Optional[int] = None,
    ) -> bool:
        """Aktualisiert einzelne Felder einer vorhandenen Disziplin."""
        aktualisierungen: list[str] = []
        parameter: list[object] = []

        if name is not None:
            aktualisierungen.append("name = ?")
            parameter.append(name)
        if format is not None:
            aktualisierungen.append("format = ?")
            parameter.append(format)
        if num_rounds is not None:
            aktualisierungen.append("num_rounds = ?")
            parameter.append(num_rounds)

        if not aktualisierungen:
            return True

        parameter.append(disziplin_id)
        with self._connect() as verbindung:
            cursor = verbindung.execute(
                f"UPDATE Disziplinen SET {', '.join(aktualisierungen)} WHERE id = ?",
                parameter,
            )
            return cursor.rowcount > 0

    def delete_disziplin(self, disziplin_id: int) -> bool:
        """Löscht eine Disziplin anhand ihrer ID."""
        with self._connect() as verbindung:
            cursor = verbindung.execute(
                "DELETE FROM Disziplinen WHERE id = ?",
                (disziplin_id,),
            )
            return cursor.rowcount > 0


def default_meta_db_path(project_root: str | Path) -> Path:
    """Liefert den Standardpfad zur Meta-Datenbank des Projekts."""
    projektwurzel = Path(project_root)
    return projektwurzel / "database" / "bjs_meta.db"
