from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class RegisteredDb:
    name: str
    path: str
    label: str
    year: Optional[int]
    created_at: str
    file_size: int


@dataclass(frozen=True)
class Disziplin:
    id: int
    name: str
    format: str  # 'time' or 'distance'
    num_rounds: int
    unit: str


class DbRegistry:
    def __init__(self, meta_db_path: str | Path):
        self.meta_db_path = Path(meta_db_path)
        self.meta_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.meta_db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS App_Config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Disziplinen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    format TEXT NOT NULL CHECK (format IN ('time', 'distance')) DEFAULT 'distance',
                    num_rounds INTEGER NOT NULL CHECK (num_rounds BETWEEN 1 AND 5) DEFAULT 3,
                    unit TEXT DEFAULT 'm',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def get_active_db_path(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM App_Config WHERE key = 'active_db_path'"
            ).fetchone()
            if not row:
                return None
            value = row[0]
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = value
            if not parsed:
                return None
            return str(parsed)

    def set_active_db_path(self, path: str | Path) -> None:
        path_str = str(Path(path))
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO App_Config (key, value) VALUES (?, ?)",
                ("active_db_path", json.dumps(path_str)),
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
        db_path = Path(path)
        created = created_at or datetime.now().isoformat(timespec="seconds")
        file_size = db_path.stat().st_size if db_path.exists() else 0
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO Db_Registry (name, path, label, year, created_at, file_size, extra_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    str(db_path),
                    label,
                    year,
                    created,
                    file_size,
                    json.dumps(extra or {}),
                ),
            )

    def list_dbs(self) -> list[RegisteredDb]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name, path, COALESCE(label, ''), year, created_at, file_size
                FROM Db_Registry
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [
            RegisteredDb(
                name=row[0],
                path=row[1],
                label=row[2] or "",
                year=row[3],
                created_at=row[4],
                file_size=int(row[5] or 0),
            )
            for row in rows
        ]

    def get_by_name(self, name: str) -> Optional[RegisteredDb]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT name, path, COALESCE(label, ''), year, created_at, file_size
                FROM Db_Registry
                WHERE name = ?
                """,
                (name,),
            ).fetchone()

        if not row:
            return None
        return RegisteredDb(
            name=row[0],
            path=row[1],
            label=row[2] or "",
            year=row[3],
            created_at=row[4],
            file_size=int(row[5] or 0),
        )

    def ensure_registered(self, db_path: str | Path, *, default_label: str = "") -> None:
        db_path = Path(db_path)
        name = db_path.name
        if self.get_by_name(name):
            return
        self.register_db(path=db_path, name=name, label=default_label)

    def delete_db(self, name: str, *, delete_file: bool = True) -> bool:
        """Löscht eine Datenbank aus der Registry und optional die Datei.

        Args:
            name: Der Name der Datenbank in der Registry.
            delete_file: Wenn True, wird auch die Datenbankdatei gelöscht.

        Returns:
            True wenn erfolgreich gelöscht, False wenn nicht gefunden.
        """
        entry = self.get_by_name(name)
        if not entry:
            return False

        # Prüfen ob dies die aktive DB ist
        active_path = self.get_active_db_path()
        if active_path and Path(active_path) == Path(entry.path):
            # Aktive DB zurücksetzen
            with self._connect() as conn:
                conn.execute("DELETE FROM App_Config WHERE key = 'active_db_path'")

        # Aus Registry entfernen
        with self._connect() as conn:
            conn.execute("DELETE FROM Db_Registry WHERE name = ?", (name,))

        # Datei löschen wenn gewünscht
        if delete_file:
            db_path = Path(entry.path)
            if db_path.exists():
                db_path.unlink()

        return True

    # ========================================
    # Disziplinen Management (global, not per-DB)
    # ========================================

    def get_disziplinen(self) -> list[Disziplin]:
        """Holt alle Disziplinen."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, format, num_rounds, unit
                FROM Disziplinen
                ORDER BY name
                """
            ).fetchall()

        return [
            Disziplin(
                id=row[0],
                name=row[1],
                format=row[2],
                num_rounds=row[3],
                unit=row[4] or "m",
            )
            for row in rows
        ]

    def get_disziplin(self, disziplin_id: int) -> Optional[Disziplin]:
        """Holt eine einzelne Disziplin nach ID."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, format, num_rounds, unit
                FROM Disziplinen WHERE id = ?
                """,
                (disziplin_id,),
            ).fetchone()

        if not row:
            return None
        return Disziplin(
            id=row[0],
            name=row[1],
            format=row[2],
            num_rounds=row[3],
            unit=row[4] or "m",
        )

    def get_disziplin_by_name(self, name: str) -> Optional[Disziplin]:
        """Holt Disziplin nach Name."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, format, num_rounds, unit
                FROM Disziplinen WHERE name = ?
                """,
                (name,),
            ).fetchone()

        if not row:
            return None
        return Disziplin(
            id=row[0],
            name=row[1],
            format=row[2],
            num_rounds=row[3],
            unit=row[4] or "m",
        )

    def create_disziplin(
        self,
        name: str,
        format: str = "distance",
        num_rounds: int = 3,
        unit: str = "m",
    ) -> int:
        """Erstellt eine neue Disziplin. Gibt die ID zurück."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO Disziplinen (name, format, num_rounds, unit)
                VALUES (?, ?, ?, ?)
                """,
                (name, format, num_rounds, unit),
            )
            return cur.lastrowid or 0

    def update_disziplin(
        self,
        disziplin_id: int,
        name: Optional[str] = None,
        format: Optional[str] = None,
        num_rounds: Optional[int] = None,
        unit: Optional[str] = None,
    ) -> bool:
        """Aktualisiert eine Disziplin. Gibt True zurück wenn gefunden."""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if format is not None:
            updates.append("format = ?")
            params.append(format)
        if num_rounds is not None:
            updates.append("num_rounds = ?")
            params.append(num_rounds)
        if unit is not None:
            updates.append("unit = ?")
            params.append(unit)

        if not updates:
            return True

        params.append(disziplin_id)
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE Disziplinen SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            return cur.rowcount > 0

    def delete_disziplin(self, disziplin_id: int) -> bool:
        """Löscht eine Disziplin. Gibt True zurück wenn gefunden."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM Disziplinen WHERE id = ?",
                (disziplin_id,),
            )
            return cur.rowcount > 0


def default_meta_db_path(project_root: str | Path) -> Path:
    root = Path(project_root)
    return root / "alles_neu" / "app" / "database" / "bjs_meta.db"
