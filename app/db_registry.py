"""Verwaltet die Registry fuer Event-Datenbanken und globale Disziplinen."""

from __future__ import annotations

import re
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .auswertung_config import (
    get_default_auswertung_config,
)
from .disziplinen_config import get_hardcoded_disziplinen


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
    """Kapselt die Meta-Datenbank fuer Datenbankauswahl und Disziplinverwaltung."""

    def __init__(self, meta_db_path: str | Path):
        """Initialisiert die Registry und stellt das Schema sicher."""
        self.meta_db_path = Path(meta_db_path)
        self.meta_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Oeffnet eine SQLite-Verbindung zur Meta-Datenbank."""
        verbindung = sqlite3.connect(str(self.meta_db_path), timeout=5.0)
        verbindung.execute("PRAGMA foreign_keys = ON;")
        try:
            verbindung.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.OperationalError:
            # Manche Laufwerke/Syncthing-Verzeichnisse unterstuetzen WAL nicht
            # stabil. In dem Fall auf das Standard-Journal zurueckfallen.
            verbindung.execute("PRAGMA journal_mode = DELETE;")
        verbindung.execute("PRAGMA synchronous = NORMAL;")
        verbindung.execute("PRAGMA busy_timeout = 5000;")
        return verbindung

    def _ensure_schema(self) -> None:
        """Legt alle benoetigten Tabellen der Meta-Datenbank an."""
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
                for zeile in verbindung.execute("PRAGMA table_info(Disziplinen)").fetchall()
            ]
            if "unit" in vorhandene_spalten:
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
        """Liest den Pfad der aktuell ausgewaehlten Event-Datenbank aus."""
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

    def get_app_config(self, key: str, default: Any = None) -> Any:
        """Liest einen JSON-codierten App-Konfigurationswert aus der Meta-DB."""
        with self._connect() as verbindung:
            zeile = verbindung.execute(
                "SELECT value FROM App_Config WHERE key = ?",
                (key,),
            ).fetchone()
        if not zeile:
            return default
        raw = zeile[0]
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def set_app_config(self, key: str, value: Any) -> None:
        """Speichert einen JSON-codierten App-Konfigurationswert in der Meta-DB."""
        with self._connect() as verbindung:
            verbindung.execute(
                "INSERT OR REPLACE INTO App_Config (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )

    def get_auswertung_config(self) -> dict[str, Any]:
        """Liefert die fest im Code hinterlegte Auswertungskonfiguration."""
        return get_default_auswertung_config()

    def set_auswertung_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Blockiert Laufzeit-Aenderungen an der Auswertungskonfiguration."""
        raise ValueError("Die Auswertungskonfiguration ist fest im Code hinterlegt.")

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

    @staticmethod
    def _infer_year_from_name(name: str) -> Optional[int]:
        """Leitet das Event-Jahr aus dem Dateinamen ab, falls kein Registry-Jahr gesetzt ist."""
        treffer = re.match(r"^BJS_(\d{4})_\d+\.db$", str(name or ""), re.IGNORECASE)
        if not treffer:
            return None
        try:
            return int(treffer.group(1))
        except Exception:
            return None

    def find_latest_db_for_year(self, year: int) -> Optional[RegisteredDb]:
        """Liefert die neueste registrierte Datenbank fuer ein bestimmtes Jahr."""
        kandidaten = [
            db
            for db in self.list_dbs()
            if (db.year if db.year is not None else self._infer_year_from_name(db.name))
            == int(year)
        ]
        return kandidaten[0] if kandidaten else None

    def get_by_name(self, name: str) -> Optional[RegisteredDb]:
        """Laedt genau einen Registry-Eintrag ueber seinen Dateinamen."""
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

    def ensure_registered(self, db_path: str | Path, *, default_label: str = "") -> None:
        """Registriert eine Datenbank nur dann, wenn sie noch nicht bekannt ist."""
        datenbankpfad = Path(db_path)
        if self.get_by_name(datenbankpfad.name):
            return
        self.register_db(path=datenbankpfad, name=datenbankpfad.name, label=default_label)

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
            for pfad in (
                datenbankpfad,
                Path(f"{datenbankpfad}-wal"),
                Path(f"{datenbankpfad}-shm"),
            ):
                if pfad.exists():
                    pfad.unlink()

        return True

    def get_disziplinen(self) -> list[Disziplin]:
        """Liefert alle globalen Disziplinen aus der statischen Konfiguration."""
        return [
            Disziplin(
                id=definition.id,
                name=definition.name,
                format=definition.format,
                num_rounds=definition.num_rounds,
            )
            for definition in get_hardcoded_disziplinen()
        ]

    def get_disziplin(self, disziplin_id: int) -> Optional[Disziplin]:
        """Laedt eine statische Disziplin anhand ihrer ID."""
        return next((d for d in self.get_disziplinen() if d.id == disziplin_id), None)

    def get_disziplin_by_name(self, name: str) -> Optional[Disziplin]:
        """Laedt eine statische Disziplin anhand ihres technischen Namens."""
        return next((d for d in self.get_disziplinen() if d.name == name), None)

    def create_disziplin(self, name: str, format: str = "distance", num_rounds: int = 3) -> int:
        """Disziplinen sind statisch und koennen nicht angelegt werden."""
        raise ValueError("Disziplinen sind fest im Code hinterlegt.")

    def update_disziplin(
        self,
        disziplin_id: int,
        name: Optional[str] = None,
        format: Optional[str] = None,
        num_rounds: Optional[int] = None,
    ) -> bool:
        """Disziplinen sind statisch und koennen nicht aktualisiert werden."""
        raise ValueError("Disziplinen sind fest im Code hinterlegt.")

    def delete_disziplin(self, disziplin_id: int) -> bool:
        """Disziplinen sind statisch und koennen nicht geloescht werden."""
        raise ValueError("Disziplinen sind fest im Code hinterlegt.")


def default_meta_db_path(project_root: str | Path) -> Path:
    """Liefert den Standardpfad zur Meta-Datenbank des Projekts."""
    projektwurzel = Path(project_root)
    return projektwurzel / "database" / "bjs_meta.db"
