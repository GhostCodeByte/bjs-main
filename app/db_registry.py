from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class RegisteredDb:
    name: str
    path: str
    label: str
    year: Optional[int]
    created_at: str
    file_size: int


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


def default_meta_db_path(project_root: str | Path) -> Path:
    root = Path(project_root)
    return root / "app" / "database" / "bjs_meta.db"
