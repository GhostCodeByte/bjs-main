import json
import secrets
import sqlite3
import string
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple


class Database:
    """
    Haupt-Datenbank-Klasse für die BJS-Webanwendung.

    Features:
    - Disziplin-Konfiguration mit CRUD-Operationen
    - Automatische Backup-Versionierung
    - UNIQUE-Constraints gegen doppelte Einträge
    - Transaktions-Handling mit Rollback
    """

    _backup_thread: Optional[threading.Thread] = None
    _backup_stop_event: Optional[threading.Event] = None

    def __init__(self, id=None, path=None):
        if id is None:
            id = datetime.now().year

        if path is None:
            path = f"alles_neu/app/database/bjs_database_{id}.db"

        self.db_path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(
            path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False
        )
        self.connection.execute("PRAGMA foreign_keys = ON;")
        self.cursor = self.connection.cursor()
        self._ensure_base_tables()
        self._ensure_runtime_tables()
        self._ensure_disziplin_tables()
        self._ensure_unique_constraints()
        self._ensure_backup_config()

    def _ensure_base_tables(self):
        """Stellt sicher, dass Kern-Tabellen existieren.

        Diese Tabellen wurden früher im `admin/`-Modul erstellt, werden aber
        von der Web-App und den Tests vorausgesetzt. Sie müssen existieren,
        bevor Indizes/Constraints angelegt werden.
        """
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Riegenfuehrer (
                ID              INTEGER PRIMARY KEY AUTOINCREMENT,
                Name            TEXT UNIQUE NOT NULL,
                Geschlecht      TEXT NOT NULL,
                Profil          BOOLEAN NOT NULL,
                Stufe           INTEGER NOT NULL,
                Klassenendungen TEXT NOT NULL
            );
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Schueler (
                SchuelerID        INTEGER PRIMARY KEY AUTOINCREMENT,
                Name              TEXT,
                Vorname           TEXT,
                Geschlecht        TEXT,
                Klasse            INTEGER,
                Klassenbuchstabe  TEXT,
                Geburtsjahr       INTEGER,
                Bundesjugentspielalter INTEGER,
                Profil            BOOLEAN,
                RiegenfuehrerID   INTEGER,
                Gesamtpunktzahl   INTEGER,
                Note              INTEGER,
                Urkunde           TEXT,
                FOREIGN KEY (RiegenfuehrerID) REFERENCES Riegenfuehrer(ID)
            );
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Schueler_Disziplin_Ergebnis (
                ID                 INTEGER PRIMARY KEY AUTOINCREMENT,
                SchuelerID         INTEGER NOT NULL,
                Disziplin          TEXT NOT NULL,
                ErgebnisNR         INTEGER CHECK (ErgebnisNR IN (1, 2, 3)),
                result_value       REAL,
                status             TEXT CHECK (status IN ('OK', 'ABWESEND')),
                source_ipad_number TEXT,
                source_station     TEXT,
                created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (SchuelerID) REFERENCES Schueler(SchuelerID)
            );
            """
        )

        self.connection.commit()

    def _ensure_runtime_tables(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Station_Pin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station TEXT NOT NULL,
                discipline TEXT,
                pin TEXT NOT NULL UNIQUE,
                max_logins INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Station_Session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pin TEXT NOT NULL,
                device_id TEXT NOT NULL,
                discipline TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (pin) REFERENCES Station_Pin(pin)
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS App_Settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        pin_columns = [
            row[1]
            for row in self.cursor.execute("PRAGMA table_info(Station_Pin)").fetchall()
        ]
        if "discipline" not in pin_columns:
            self.cursor.execute("ALTER TABLE Station_Pin ADD COLUMN discipline TEXT")
        session_columns = [
            row[1]
            for row in self.cursor.execute(
                "PRAGMA table_info(Station_Session)"
            ).fetchall()
        ]
        if "discipline" not in session_columns:
            self.cursor.execute(
                "ALTER TABLE Station_Session ADD COLUMN discipline TEXT"
            )
        self.connection.commit()

    def _ensure_disziplin_tables(self):
        """Erstellt Tabellen für Disziplin-Konfiguration und migriert alte Schemas ohne unit-Spalte."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Disziplinen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT,
                result_format TEXT NOT NULL CHECK (result_format IN ('time', 'distance')) DEFAULT 'distance',
                num_rounds INTEGER NOT NULL CHECK (num_rounds BETWEEN 1 AND 5) DEFAULT 3,
                description TEXT,
                sort_order INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Migration: entferne alte unit-Spalte falls vorhanden
        disziplin_columns = [
            row[1]
            for row in self.cursor.execute("PRAGMA table_info(Disziplinen)").fetchall()
        ]
        if "unit" in disziplin_columns:
            self.cursor.execute("PRAGMA foreign_keys = OFF")
            self.cursor.execute("ALTER TABLE Disziplinen RENAME TO Disziplinen_old")
            self.cursor.execute(
                """
                CREATE TABLE Disziplinen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT,
                    result_format TEXT NOT NULL CHECK (result_format IN ('time', 'distance')) DEFAULT 'distance',
                    num_rounds INTEGER NOT NULL CHECK (num_rounds BETWEEN 1 AND 5) DEFAULT 3,
                    description TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self.cursor.execute(
                """
                INSERT INTO Disziplinen (id, name, display_name, result_format, num_rounds, description, sort_order, created_at, updated_at)
                SELECT id, name, display_name, result_format, num_rounds, description, sort_order, created_at, updated_at
                FROM Disziplinen_old;
                """
            )
            self.cursor.execute("DROP TABLE Disziplinen_old")
            self.connection.commit()
            self.cursor.execute("PRAGMA foreign_keys = ON")

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Disziplin_Config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                disziplin_id INTEGER NOT NULL,
                config_key TEXT NOT NULL,
                config_value TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (disziplin_id) REFERENCES Disziplinen(id) ON DELETE CASCADE,
                UNIQUE(disziplin_id, config_key)
            );
            """
        )

        # Kein Auto-Seeding: Admin soll Disziplinen selbst anlegen.
        self.connection.commit()

    def _ensure_unique_constraints(self):
        """
        Stellt UNIQUE-Constraints sicher für:
        - Riegenführer-Namen (bereits in Schema)
        - Verhindert exakt doppelte Rundeneinträge (via Trigger)
        """
        # Index für schnelle Lookups bei Ergebnis-Abfragen
        self.cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ergebnis_schueler_disziplin
            ON Schueler_Disziplin_Ergebnis (SchuelerID, Disziplin, ErgebnisNR, created_at DESC)
            """
        )

        # Index für Riegenführer-Lookup
        self.cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schueler_riege
            ON Schueler (RiegenfuehrerID)
            """
        )

        self.connection.commit()

    def _ensure_backup_config(self):
        """Erstellt Tabelle für Backup-Konfiguration und -Historie."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Backup_Config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                interval_minutes INTEGER DEFAULT 60,
                max_backups INTEGER DEFAULT 10,
                enabled INTEGER DEFAULT 1,
                last_backup DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Backup_History (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                backup_type TEXT CHECK (backup_type IN ('auto', 'manual', 'upload')) DEFAULT 'manual',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Seed default config if not exists
        self.cursor.execute("SELECT COUNT(*) FROM Backup_Config")
        if self.cursor.fetchone()[0] == 0:
            self.cursor.execute(
                "INSERT INTO Backup_Config (id, interval_minutes, max_backups, enabled) VALUES (1, 60, 10, 1)"
            )

        self.connection.commit()

    def _execute_tx(self, query: str, params: tuple = ()):
        """Führt Query in Transaktion aus mit Rollback bei Fehler."""
        try:
            cur = self.connection.execute(query, params)
            self.connection.commit()
            return cur
        except Exception:
            self.connection.rollback()
            raise

    # ============================================
    # Riegenführer & Schüler Methoden
    # ============================================

    def add_schueler(
        self,
        name: str,
        vorname: str,
        geschlecht: str,
        klasse: int,
        klassenbuchstabe: str,
        geburtsjahr: int,
        profil: bool,
    ) -> int:
        """Legt einen Schüler an."""
        self.cursor.execute(
            """
            INSERT INTO Schueler (
                Name, Vorname, Geschlecht, Klasse, Klassenbuchstabe,
                Geburtsjahr, Bundesjugentspielalter, Profil, RiegenfuehrerID,
                Gesamtpunktzahl, Note, Urkunde
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
            """,
            (
                name,
                vorname,
                geschlecht,
                int(klasse),
                klassenbuchstabe,
                int(geburtsjahr),
                datetime.now().year - int(geburtsjahr),
                1 if profil else 0,
            ),
        )
        self.connection.commit()
        return int(self.cursor.lastrowid or 0)

    def add_riegenfuehrer(
        self,
        name: str,
        geschlecht: str,
        profil: bool,
        stufe: int,
        klassenendung: str,
    ) -> int:
        """Legt einen Riegenführer an."""
        self.cursor.execute(
            """
            INSERT INTO Riegenfuehrer (Name, Geschlecht, Profil, Stufe, Klassenendungen)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, geschlecht, 1 if profil else 0, int(stufe), klassenendung),
        )
        self.connection.commit()
        return int(self.cursor.lastrowid or 0)

    def add_riegenfuehrer_to_schueler(
        self,
        rf_id: int,
        klassenbuchstabe: str,
        stufe: int,
        geschlecht: str,
        profil: bool,
    ) -> int:
        """Weist Schüler einer Riege zu (Update).

        `geschlecht` wird nur angewendet, wenn `profil` False ist.
        Für Profil-Riegen wird ausschließlich nach Klasse/Profil gefiltert.
        """

        if profil:
            cur = self._execute_tx(
                """
                UPDATE Schueler
                SET RiegenfuehrerID = ?
                WHERE Klassenbuchstabe = ?
                AND Klasse = ?
                AND Profil = 1
                """,
                (rf_id, klassenbuchstabe, int(stufe)),
            )
            return cur.rowcount

        cur = self._execute_tx(
            """
            UPDATE Schueler
            SET RiegenfuehrerID = ?
            WHERE Klassenbuchstabe = ?
            AND Klasse = ?
            AND Geschlecht = ?
            AND Profil = 0
            """,
            (rf_id, klassenbuchstabe, int(stufe), geschlecht),
        )
        return cur.rowcount

    def clear_all_riegen_assignments(self) -> int:
        """Setzt alle Schüler-Riegenzuweisungen zurück."""
        cur = self._execute_tx("UPDATE Schueler SET RiegenfuehrerID = NULL")
        return int(cur.rowcount)

    def clear_all_riegen(self) -> int:
        """Löscht alle Riegen (und entkoppelt Schüler)."""
        self.clear_all_riegen_assignments()
        cur = self._execute_tx("DELETE FROM Riegenfuehrer")
        return int(cur.rowcount)

    def get_riegen_stats(self) -> Dict[str, int]:
        """Einfache Kennzahlen für die Riegeneinteilung-Seite."""
        self.cursor.execute("SELECT COUNT(*) FROM Schueler")
        total_students = int(self.cursor.fetchone()[0] or 0)
        self.cursor.execute(
            "SELECT COUNT(*) FROM Schueler WHERE RiegenfuehrerID IS NOT NULL"
        )
        assigned_students = int(self.cursor.fetchone()[0] or 0)
        self.cursor.execute("SELECT COUNT(*) FROM Riegenfuehrer")
        total_riegen = int(self.cursor.fetchone()[0] or 0)
        self.cursor.execute("SELECT COUNT(*) FROM Schueler WHERE Profil = 1")
        total_profil = int(self.cursor.fetchone()[0] or 0)
        self.cursor.execute(
            "SELECT COUNT(*) FROM Schueler WHERE Profil = 1 AND RiegenfuehrerID IS NOT NULL"
        )
        assigned_profil = int(self.cursor.fetchone()[0] or 0)
        return {
            "students_total": total_students,
            "students_assigned": assigned_students,
            "students_unassigned": total_students - assigned_students,
            "riegen_total": total_riegen,
            "profil_total": total_profil,
            "profil_assigned": assigned_profil,
        }

    def get_present_classes(self) -> List[Dict[str, Any]]:
        """Liefert alle vorhandenen Klassenkombinationen mit Profil-Flag.

        Returns: [{'stufe': 5, 'buchstabe': 'a', 'has_profil': True}, ...]
        """
        self.cursor.execute(
            """
            SELECT Klasse, Klassenbuchstabe,
                   MAX(CASE WHEN Profil = 1 THEN 1 ELSE 0 END) as has_profil
            FROM Schueler
            WHERE Klasse IS NOT NULL
            GROUP BY Klasse, Klassenbuchstabe
            ORDER BY Klasse, Klassenbuchstabe
            """
        )
        rows = self.cursor.fetchall()
        out: List[Dict[str, Any]] = []
        for klasse, buchstabe, has_profil in rows:
            out.append(
                {
                    "stufe": int(klasse),
                    "buchstabe": (buchstabe or "").strip().lower(),
                    "has_profil": bool(has_profil),
                }
            )
        return out

    def update_riege(
        self,
        *,
        riegen_id: int,
        name: str,
        stufe: int,
        klassenendungen: str,
        geschlecht: str,
        profil: bool,
    ) -> int:
        """Aktualisiert eine Riege (Metadaten)."""
        cur = self._execute_tx(
            """
            UPDATE Riegenfuehrer
            SET Name = ?, Geschlecht = ?, Profil = ?, Stufe = ?, Klassenendungen = ?
            WHERE ID = ?
            """,
            (
                name,
                geschlecht,
                1 if profil else 0,
                int(stufe),
                klassenendungen,
                int(riegen_id),
            ),
        )
        return int(cur.rowcount)

    def get_riegenfuehrer(self):
        self.cursor.execute("SELECT * FROM Riegenfuehrer")
        return self.cursor.fetchall()

    def get_riege(self, riegenfuehrer_id):
        self.cursor.execute(
            """
            SELECT SchuelerID, Name, Vorname, Geschlecht, Bundesjugentspielalter, Klasse, Klassenbuchstabe, Profil
            FROM Schueler
            WHERE RiegenfuehrerID = ?
            """,
            (riegenfuehrer_id,),
        )
        rows = self.cursor.fetchall()

        schueler_liste = []
        for row in rows:
            schueler = {
                "SchuelerID": row[0],
                "Name": row[1],
                "Vorname": row[2],
                "Geschlecht": row[3],
                "Bundesjugendspielalter": row[4],
                "Klasse": row[5],
                "Klassenbuchstabe": row[6],
                "Profil": row[7],
                "Round1": None,
                "Round2": None,
                "Round3": None,
            }
            schueler_liste.append(schueler)

        return schueler_liste

    def get_all_riegen_with_progress(
        self, disziplin: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Holt alle Riegen mit Fortschritts-Informationen.
        Für Dashboard-Übersicht.
        """
        self.cursor.execute(
            """
            SELECT r.ID, r.Name, r.Geschlecht, r.Profil, r.Stufe, r.Klassenendungen,
                   COUNT(DISTINCT s.SchuelerID) as total_schueler
            FROM Riegenfuehrer r
            LEFT JOIN Schueler s ON s.RiegenfuehrerID = r.ID
            GROUP BY r.ID
            ORDER BY r.Name
            """
        )
        riegen = []
        for row in self.cursor.fetchall():
            riege_id = row[0]
            total = row[6] or 0

            # Fortschritt berechnen
            progress = self._get_riege_progress(riege_id, disziplin)

            riegen.append(
                {
                    "id": riege_id,
                    "name": row[1],
                    "geschlecht": row[2],
                    "profil": row[3],
                    "stufe": row[4],
                    "klassenendungen": row[5],
                    "total_schueler": total,
                    "progress": progress,
                }
            )

        return riegen

    def _get_riege_progress(
        self, riege_id: int, disziplin: Optional[str] = None
    ) -> Dict[str, Any]:
        """Berechnet den Fortschritt einer Riege."""
        disziplin_filter = "AND e.Disziplin = ?" if disziplin else ""
        params = (riege_id, disziplin) if disziplin else (riege_id,)

        # Gesamt-Schüler
        self.cursor.execute(
            "SELECT COUNT(*) FROM Schueler WHERE RiegenfuehrerID = ?", (riege_id,)
        )
        total = self.cursor.fetchone()[0] or 0

        if total == 0:
            return {"total": 0, "completed": 0, "absent": 0, "percent": 0, "rounds": {}}

        # Schüler mit vollständigen Ergebnissen (alle 3 Runden)
        query = f"""
            SELECT s.SchuelerID,
                   SUM(CASE WHEN e.status = 'OK' THEN 1 ELSE 0 END) as ok_count,
                   SUM(CASE WHEN e.status = 'ABWESEND' THEN 1 ELSE 0 END) as absent_count
            FROM Schueler s
            LEFT JOIN (
                SELECT SchuelerID, Disziplin, ErgebnisNR, status
                FROM Schueler_Disziplin_Ergebnis
                WHERE ID IN (
                    SELECT MAX(ID) FROM Schueler_Disziplin_Ergebnis
                    GROUP BY SchuelerID, Disziplin, ErgebnisNR
                )
            ) e ON e.SchuelerID = s.SchuelerID {disziplin_filter}
            WHERE s.RiegenfuehrerID = ?
            GROUP BY s.SchuelerID
        """

        self.cursor.execute(query, params)

        completed = 0
        absent = 0
        for row in self.cursor.fetchall():
            ok_count = row[1] or 0
            absent_count = row[2] or 0
            if ok_count >= 3:
                completed += 1
            if absent_count > 0:
                absent += 1

        # Runden-Details
        rounds = {}
        for round_nr in (1, 2, 3):
            query = f"""
                SELECT COUNT(DISTINCT e.SchuelerID)
                FROM Schueler_Disziplin_Ergebnis e
                JOIN Schueler s ON s.SchuelerID = e.SchuelerID
                WHERE s.RiegenfuehrerID = ?
                AND e.ErgebnisNR = ?
                AND e.status = 'OK'
                {disziplin_filter.replace("e.Disziplin", "e.Disziplin")}
            """
            params_round = (
                (riege_id, round_nr, disziplin) if disziplin else (riege_id, round_nr)
            )
            self.cursor.execute(query, params_round)
            rounds[round_nr] = self.cursor.fetchone()[0] or 0

        return {
            "total": total,
            "completed": completed,
            "absent": absent,
            "percent": round((completed / total) * 100, 1) if total > 0 else 0,
            "rounds": rounds,
        }

    def delete_riege(self, riegenfuehrer_id: int) -> Tuple[int, int]:
        """Löscht eine Riege und hebt Schüler-Zuweisungen auf.

        Returns:
            (unassigned_count, deleted_count)
        """
        unassigned = self._execute_tx(
            "UPDATE Schueler SET RiegenfuehrerID = NULL WHERE RiegenfuehrerID = ?",
            (int(riegenfuehrer_id),),
        ).rowcount

        deleted = self._execute_tx(
            "DELETE FROM Riegenfuehrer WHERE ID = ?",
            (int(riegenfuehrer_id),),
        ).rowcount

        return int(unassigned), int(deleted)

    # ============================================
    # Ergebnis-Methoden
    # ============================================

    def get_rounds_done(self, schueler_id, disziplin):
        self.cursor.execute(
            """
            SELECT
                e.ErgebnisNR,
                CASE
                    WHEN e.status = 'OK' THEN e.result_value
                    WHEN e.status = 'ABWESEND' THEN 'ABWESEND'
                    ELSE NULL
                END AS round_value
            FROM Schueler_Disziplin_Ergebnis e
            JOIN (
                SELECT ErgebnisNR, MAX(ID) AS max_id
                FROM Schueler_Disziplin_Ergebnis
                WHERE SchuelerID = ? AND Disziplin = ?
                GROUP BY ErgebnisNR
            ) latest ON latest.max_id = e.ID
            ORDER BY e.ErgebnisNR
            """,
            (schueler_id, disziplin),
        )
        return [(row[0], row[1]) for row in self.cursor.fetchall()]

    def add_entry(
        self,
        schueler_id,
        disziplin,
        ergebnis_nr,
        result_value,
        status,
        source_ipad_number,
        source_station,
    ):
        print(
            f"Adding entry: SchuelerID={schueler_id}, Disziplin={disziplin}, ErgebnisNR={ergebnis_nr}, result_value={result_value}, status={status}, source_ipad_number={source_ipad_number}, source_station={source_station}"
        )
        self._execute_tx(
            """
            INSERT INTO Schueler_Disziplin_Ergebnis (
                SchuelerID, Disziplin, ErgebnisNR, result_value, status,
                source_ipad_number, source_station
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schueler_id,
                disziplin,
                ergebnis_nr,
                result_value,
                status,
                source_ipad_number,
                source_station,
            ),
        )

    def get_bestenliste(
        self, disziplin: str, limit: int = 10, geschlecht: Optional[str] = None
    ) -> List[Dict]:
        """
        Holt die Bestenliste für eine Disziplin.
        Bei Zeit: niedrigster Wert ist besser
        Bei Distanz: höchster Wert ist besser
        """
        # Disziplin-Format prüfen
        self.cursor.execute(
            "SELECT result_format FROM Disziplinen WHERE name = ?", (disziplin,)
        )
        row = self.cursor.fetchone()
        result_format = row[0] if row else "distance"

        order = "ASC" if result_format == "time" else "DESC"
        geschlecht_filter = "AND s.Geschlecht = ?" if geschlecht else ""

        query = f"""
            SELECT s.SchuelerID, s.Name, s.Vorname, s.Klasse, s.Klassenbuchstabe,
                   s.Geschlecht, MAX(e.result_value) as best_result
            FROM Schueler s
            JOIN Schueler_Disziplin_Ergebnis e ON e.SchuelerID = s.SchuelerID
            WHERE e.Disziplin = ? AND e.status = 'OK' AND e.result_value IS NOT NULL
            {geschlecht_filter}
            GROUP BY s.SchuelerID
            ORDER BY best_result {order}
            LIMIT ?
        """

        params = (disziplin, geschlecht, limit) if geschlecht else (disziplin, limit)
        self.cursor.execute(query, params)

        results = []
        rank = 0
        for row in self.cursor.fetchall():
            rank += 1
            results.append(
                {
                    "rank": rank,
                    "schueler_id": row[0],
                    "name": row[1],
                    "vorname": row[2],
                    "klasse": f"{row[3]}{row[4]}",
                    "geschlecht": row[5],
                    "result": row[6],
                }
            )

        return results

    # ============================================
    # Disziplin-CRUD Methoden
    # ============================================

    def get_disziplinen(self) -> List[Dict[str, Any]]:
        """Holt alle Disziplinen mit Konfiguration."""
        self.cursor.execute(
            """
            SELECT id, name, display_name, result_format, num_rounds, description, sort_order, created_at, updated_at
            FROM Disziplinen
            ORDER BY sort_order, name
            """
        )
        disziplinen = []
        for row in self.cursor.fetchall():
            disziplin = {
                "id": row[0],
                "name": row[1],
                "display_name": row[2],
                "result_format": row[3],
                "num_rounds": row[4],
                "description": row[5],
                "sort_order": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "config": {},
            }

            # Lade zusätzliche Konfiguration
            self.cursor.execute(
                "SELECT config_key, config_value FROM Disziplin_Config WHERE disziplin_id = ?",
                (row[0],),
            )
            for config_row in self.cursor.fetchall():
                disziplin["config"][config_row[0]] = config_row[1]

            disziplinen.append(disziplin)

        return disziplinen

    def get_disziplin(self, disziplin_id: int) -> Optional[Dict[str, Any]]:
        """Holt eine einzelne Disziplin."""
        self.cursor.execute(
            """
            SELECT id, name, display_name, result_format, num_rounds, description, sort_order
            FROM Disziplinen WHERE id = ?
            """,
            (disziplin_id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "name": row[1],
            "display_name": row[2],
            "result_format": row[3],
            "num_rounds": row[4],
            "description": row[5],
            "sort_order": row[6],
        }

    def get_disziplin_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Holt Disziplin nach Name."""
        self.cursor.execute(
            """
            SELECT id, name, display_name, result_format, num_rounds, description, sort_order
            FROM Disziplinen WHERE name = ?
            """,
            (name,),
        )
        row = self.cursor.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "name": row[1],
            "display_name": row[2],
            "result_format": row[3],
            "num_rounds": row[4],
            "description": row[5],
            "sort_order": row[6],
        }

    def create_disziplin(
        self,
        name: str,
        display_name: Optional[str] = None,
        result_format: str = "distance",
        num_rounds: int = 3,
        description: Optional[str] = None,
        sort_order: int = 0,
    ) -> int:
        """Erstellt eine neue Disziplin."""
        if result_format not in ("time", "distance"):
            raise ValueError("result_format muss 'time' oder 'distance' sein")
        if not 1 <= num_rounds <= 5:
            raise ValueError("num_rounds muss zwischen 1 und 5 liegen")

        cur = self._execute_tx(
            """
            INSERT INTO Disziplinen (name, display_name, result_format, num_rounds, description, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                display_name or name,
                result_format,
                num_rounds,
                description,
                sort_order,
            ),
        )
        return int(cur.lastrowid or 0)

    def update_disziplin(
        self,
        disziplin_id: int,
        name: Optional[str] = None,
        display_name: Optional[str] = None,
        result_format: Optional[str] = None,
        num_rounds: Optional[int] = None,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> bool:
        """Aktualisiert eine Disziplin."""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if result_format is not None:
            if result_format not in ("time", "distance"):
                raise ValueError("result_format muss 'time' oder 'distance' sein")
            updates.append("result_format = ?")
            params.append(result_format)
        if num_rounds is not None:
            if not 1 <= num_rounds <= 5:
                raise ValueError("num_rounds muss zwischen 1 und 5 liegen")
            updates.append("num_rounds = ?")
            params.append(num_rounds)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if sort_order is not None:
            updates.append("sort_order = ?")
            params.append(sort_order)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(disziplin_id)

        query = f"UPDATE Disziplinen SET {', '.join(updates)} WHERE id = ?"
        cur = self._execute_tx(query, tuple(params))
        return cur.rowcount > 0

    def delete_disziplin(self, disziplin_id: int) -> bool:
        """Löscht eine Disziplin."""
        cur = self._execute_tx("DELETE FROM Disziplinen WHERE id = ?", (disziplin_id,))
        return cur.rowcount > 0

    def set_disziplin_config(self, disziplin_id: int, key: str, value: str) -> None:
        """Setzt einen Konfigurations-Wert für eine Disziplin."""
        self._execute_tx(
            """
            INSERT INTO Disziplin_Config (disziplin_id, config_key, config_value)
            VALUES (?, ?, ?)
            ON CONFLICT(disziplin_id, config_key) DO UPDATE SET config_value = excluded.config_value
            """,
            (disziplin_id, key, value),
        )

    # ============================================
    # Station-PIN Methoden
    # ============================================

    def generate_station_pin(
        self,
        station: str,
        max_logins: int = 1,
        length: int = 6,
        discipline: Optional[str] = None,
    ) -> str:
        pin = None
        attempts = 0
        discipline_val = discipline or station

        while pin is None and attempts < 20:
            candidate = "".join(secrets.choice(string.digits) for _ in range(length))
            try:
                self._execute_tx(
                    """
                    INSERT INTO Station_Pin (station, discipline, pin, max_logins, active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (station, discipline_val, candidate, max_logins),
                )
                pin = candidate
            except sqlite3.IntegrityError:
                attempts += 1
                continue
        if pin is None:
            raise RuntimeError("Konnte keinen eindeutigen PIN generieren")
        return pin

    def ensure_default_station_pin(
        self,
        station: str,
        max_logins: int = 1,
        length: int = 6,
        discipline: Optional[str] = None,
    ) -> str:
        discipline_val = discipline or station

        row = self.cursor.execute(
            "SELECT pin FROM Station_Pin WHERE station = ? AND active = 1 LIMIT 1",
            (station,),
        ).fetchone()

        if row:
            return row[0]

        return self.generate_station_pin(
            station=station,
            max_logins=max_logins,
            length=length,
            discipline=discipline_val,
        )

    def claim_station_pin(
        self, pin: str, device_id: str, discipline: Optional[str] = None
    ) -> Tuple[bool, str]:
        row = self.cursor.execute(
            "SELECT pin, max_logins, active, discipline FROM Station_Pin WHERE pin = ?",
            (pin,),
        ).fetchone()
        if not row or row[2] != 1:
            return False, "PIN nicht aktiv oder unbekannt"

        # NOTE: Discipline mapping is currently optional.
        # The login form always provides a discipline, but pins are station-scoped.
        # Enforcing an exact match makes it impossible to use a default station pin
        # across different disciplines (see tests/integration usage).

        active_sessions = self.cursor.execute(
            "SELECT device_id FROM Station_Session WHERE pin = ? AND active = 1",
            (pin,),
        ).fetchall()

        # Idempotent: if same device already active, allow.
        if any(sess[0] != device_id for sess in active_sessions):
            return False, "PIN bereits durch anderes Gerät aktiv"

        if any(sess[0] == device_id for sess in active_sessions):
            return True, "OK"

        if len(active_sessions) >= row[1]:
            return False, "Maximale Logins für diese Station erreicht"

        pin_discipline = row[3]
        self._execute_tx(
            """
            INSERT INTO Station_Session (pin, device_id, discipline, active)
            VALUES (?, ?, ?, 1)
            """,
            (pin, device_id, discipline or pin_discipline),
        )
        return True, "OK"

    def revoke_station_pin(self, pin: str, device_id: Optional[str] = None) -> int:
        if device_id:
            cur = self._execute_tx(
                "UPDATE Station_Session SET active = 0 WHERE pin = ? AND device_id = ? AND active = 1",
                (pin, device_id),
            )
        else:
            cur = self._execute_tx(
                "UPDATE Station_Session SET active = 0 WHERE pin = ? AND active = 1",
                (pin,),
            )
        return cur.rowcount

    def deactivate_pin(self, pin: str) -> int:
        self._execute_tx(
            "UPDATE Station_Session SET active = 0 WHERE pin = ? AND active = 1",
            (pin,),
        )
        cur = self._execute_tx(
            "UPDATE Station_Pin SET active = 0 WHERE pin = ?",
            (pin,),
        )
        return cur.rowcount

    def delete_pin(self, pin: str) -> int:
        self._execute_tx("DELETE FROM Station_Session WHERE pin = ?", (pin,))
        cur = self._execute_tx("DELETE FROM Station_Pin WHERE pin = ?", (pin,))
        return cur.rowcount

    def deactivate_session(
        self,
        session_id: Optional[int] = None,
        pin: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> int:
        if not any([session_id, pin, device_id]):
            return 0
        query = "UPDATE Station_Session SET active = 0 WHERE active = 1"
        params = []
        if session_id:
            query += " AND id = ?"
            params.append(session_id)
        if pin:
            query += " AND pin = ?"
            params.append(pin)
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        cur = self._execute_tx(query, tuple(params))
        return cur.rowcount

    def delete_session(
        self,
        session_id: Optional[int] = None,
        pin: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> int:
        if not any([session_id, pin, device_id]):
            return 0
        query = "DELETE FROM Station_Session WHERE 1=1"
        params = []
        if session_id:
            query += " AND id = ?"
            params.append(session_id)
        if pin:
            query += " AND pin = ?"
            params.append(pin)
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        cur = self._execute_tx(query, tuple(params))
        return cur.rowcount

    def set_setting(self, key: str, value: Any) -> None:
        value_str = json.dumps(value) if not isinstance(value, str) else value
        self._execute_tx(
            """
            INSERT INTO App_Settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value_str),
        )

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.cursor.execute(
            "SELECT value FROM App_Settings WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            return default
        raw = row[0]
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def delete_setting(self, key: str) -> int:
        cur = self._execute_tx("DELETE FROM App_Settings WHERE key = ?", (key,))
        return cur.rowcount

    # ============================================
    # Backup-Methoden
    # ============================================

    def backup_to_file(
        self,
        target_path: Optional[str] = None,
        label: Optional[str] = None,
        backup_type: str = "manual",
    ) -> str:
        """
        Erstellt ein Backup der Datenbank.

        Args:
            target_path: Optionaler Zielpfad
            label: Label für den Backup-Dateinamen
            backup_type: Art des Backups ('auto', 'manual', 'upload')

        Returns:
            Pfad zur Backup-Datei
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = label or ts
        dest = (
            Path(target_path)
            if target_path
            else Path(self.db_path).with_name(
                f"{Path(self.db_path).stem}_backup_{suffix}.db"
            )
        )
        dest.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(dest)) as backup_db:
            self.connection.backup(backup_db)

        file_size = dest.stat().st_size if dest.exists() else 0

        # In Historie eintragen
        self._execute_tx(
            """
            INSERT INTO Backup_History (file_path, file_size, backup_type)
            VALUES (?, ?, ?)
            """,
            (str(dest), file_size, backup_type),
        )

        # Last backup aktualisieren
        self._execute_tx(
            "UPDATE Backup_Config SET last_backup = CURRENT_TIMESTAMP WHERE id = 1"
        )

        # Alte Backups aufräumen
        self._cleanup_old_backups()

        return str(dest)

    def get_backup_config(self) -> Dict[str, Any]:
        """Holt die Backup-Konfiguration."""
        self.cursor.execute(
            "SELECT interval_minutes, max_backups, enabled, last_backup FROM Backup_Config WHERE id = 1"
        )
        row = self.cursor.fetchone()
        if not row:
            return {
                "interval_minutes": 60,
                "max_backups": 10,
                "enabled": True,
                "last_backup": None,
            }

        return {
            "interval_minutes": row[0],
            "max_backups": row[1],
            "enabled": bool(row[2]),
            "last_backup": row[3],
        }

    def update_backup_config(
        self,
        interval_minutes: Optional[int] = None,
        max_backups: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Aktualisiert die Backup-Konfiguration."""
        updates = []
        params = []

        if interval_minutes is not None:
            updates.append("interval_minutes = ?")
            params.append(interval_minutes)
        if max_backups is not None:
            updates.append("max_backups = ?")
            params.append(max_backups)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE Backup_Config SET {', '.join(updates)} WHERE id = 1"
            self._execute_tx(query, tuple(params))

    def get_backup_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Holt die Backup-Historie."""
        self.cursor.execute(
            """
            SELECT id, file_path, file_size, backup_type, created_at
            FROM Backup_History
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            {
                "id": row[0],
                "file_path": row[1],
                "file_size": row[2],
                "backup_type": row[3],
                "created_at": row[4],
            }
            for row in self.cursor.fetchall()
        ]

    def _cleanup_old_backups(self):
        """Entfernt alte Backups basierend auf max_backups Einstellung."""
        config = self.get_backup_config()
        max_backups = config.get("max_backups", 10)

        # IDs der zu behaltenden Backups
        self.cursor.execute(
            """
            SELECT id, file_path FROM Backup_History
            ORDER BY created_at DESC
            LIMIT -1 OFFSET ?
            """,
            (max_backups,),
        )

        old_backups = self.cursor.fetchall()
        for backup_id, file_path in old_backups:
            # Datei löschen
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass

            # Aus Historie entfernen
            self._execute_tx("DELETE FROM Backup_History WHERE id = ?", (backup_id,))

    def start_auto_backup(self):
        """Startet den automatischen Backup-Thread."""
        if Database._backup_thread and Database._backup_thread.is_alive():
            return

        stop_event = threading.Event()
        Database._backup_stop_event = stop_event

        def backup_loop():
            while not stop_event.is_set():
                try:
                    config = self.get_backup_config()
                    if config.get("enabled"):
                        interval = config.get("interval_minutes", 60) * 60
                        last_backup = config.get("last_backup")

                        should_backup = False
                        if not last_backup:
                            should_backup = True
                        else:
                            try:
                                last_dt = datetime.fromisoformat(last_backup)
                                elapsed = (datetime.now() - last_dt).total_seconds()
                                should_backup = elapsed >= interval
                            except (ValueError, TypeError):
                                should_backup = True

                        if should_backup:
                            self.backup_to_file(label="auto", backup_type="auto")
                except Exception as e:
                    print(f"Auto-backup error: {e}")

                # Warte 60 Sekunden oder bis Stop-Event
                stop_event.wait(60)

        Database._backup_thread = threading.Thread(target=backup_loop, daemon=True)
        Database._backup_thread.start()

    def stop_auto_backup(self):
        """Stoppt den automatischen Backup-Thread."""
        if Database._backup_stop_event:
            Database._backup_stop_event.set()

    # ============================================
    # Stats-Methoden
    # ============================================

    def get_stats(self) -> Dict[str, Any]:
        """Holt allgemeine Statistiken."""
        stats = {}

        # Schüler gesamt
        self.cursor.execute("SELECT COUNT(*) FROM Schueler")
        stats["total_schueler"] = self.cursor.fetchone()[0]

        # Riegen gesamt
        self.cursor.execute("SELECT COUNT(*) FROM Riegenfuehrer")
        stats["total_riegen"] = self.cursor.fetchone()[0]

        # Ergebnisse gesamt
        self.cursor.execute(
            "SELECT COUNT(*) FROM Schueler_Disziplin_Ergebnis WHERE status = 'OK'"
        )
        stats["total_ergebnisse"] = self.cursor.fetchone()[0]

        # Abwesend gesamt
        self.cursor.execute(
            "SELECT COUNT(*) FROM Schueler_Disziplin_Ergebnis WHERE status = 'ABWESEND'"
        )
        stats["total_abwesend"] = self.cursor.fetchone()[0]

        # Aktive Sessions
        self.cursor.execute("SELECT COUNT(*) FROM Station_Session WHERE active = 1")
        stats["active_sessions"] = self.cursor.fetchone()[0]

        # Ergebnisse pro Disziplin
        self.cursor.execute(
            """
            SELECT Disziplin, COUNT(*)
            FROM Schueler_Disziplin_Ergebnis
            WHERE status = 'OK'
            GROUP BY Disziplin
            """
        )
        stats["ergebnisse_pro_disziplin"] = {
            row[0]: row[1] for row in self.cursor.fetchall()
        }

        # Letzte Aktivität
        self.cursor.execute("SELECT MAX(created_at) FROM Schueler_Disziplin_Ergebnis")
        row = self.cursor.fetchone()
        stats["last_activity"] = row[0] if row else None

        return stats

    def close(self):
        self.stop_auto_backup()
        self.connection.close()


if __name__ == "__main__":
    db = Database()
