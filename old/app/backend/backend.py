import sqlite3

import pandas as pd
import numpy as np
import os

# Standardpfad zur SQLite-Datenbank innerhalb des Projekts
DB_PATH = "backend/database/bjs.db"

class Backend:
    """Zugriffsschicht für SQLite: kapselt Lese-/Schreiboperationen und Hilfsfunktionen."""
    def __init__(self, path_to_db):
        self.connection = sqlite3.connect(path_to_db)
        self.cursor = self.connection.cursor()
        # Sicherstellen, dass neue Ergebnistabelle existiert
        self.ensure_results_table()

    def get_ergebnisse_alle(self):
        """Liefert alle Schüler mit Gesamtpunktzahl, Note und Urkunde; sortiert nach Klasse und Name."""
        self.cursor.execute(
            """
            SELECT schueler.klasse, schueler.klassenbuchstabe, schueler.name, schueler.vorname, schueler.gesamtpunktzahl, schueler.note, schueler.Uhrkunde
            FROM schueler
            ORDER BY schueler.klasse, schueler.klassenbuchstabe, schueler.name
            """
        )
        return self.cursor.fetchall()

    def get_riegenfuehrer_liste(self):
        """Liefert eine bereinigte Liste aller in der DB vorhandenen Riegenführer-Namen."""
        self.cursor.execute(
            """
            SELECT DISTINCT schueler.riegenfuehrername
            FROM schueler
            """
        )
        return clean_riegenfuehrer(self.cursor.fetchall())

    def get_schueler_from_riege(self, riegenfuehrer, disziplin=None):
        """Lädt alle Schüler einer Riege; optional disziplinspezifisch.
        Rückgabe je Schüler: (Klasse, Klassenbuchstabe, Geschlecht, Name, Vorname, SchuelerID,
        Runde1_Fertig(bool), Runde2_Fertig(bool), Runde3_Fertig(bool), Abwesend(bool),
        Ergebnis1, Ergebnis2, Ergebnis3) – Ergebnisse aus der neuesten Zeile je Runde.
        """
        if disziplin:
            # Ergebnisse je Runde: neuestes Ergebnis/Status aus Schueler_Disziplin_Ergebnis
            self.cursor.execute(
                """
                SELECT
                    s.klasse,
                    s.Klassenbuchstabe,
                    s.geschlecht,
                    s.name,
                    s.vorname,
                    s.SchuelerID,
                    CASE
                        WHEN (SELECT e1.status
                              FROM Schueler_Disziplin_Ergebnis e1
                              WHERE e1.SchuelerID = s.SchuelerID AND e1.Disziplin = ? AND e1.ErgebnisNR = 1
                              ORDER BY e1.created_at DESC
                              LIMIT 1) = 'OK' THEN 1 ELSE 0
                    END AS Runde1_Fertig,
                    CASE
                        WHEN (SELECT e2.status
                              FROM Schueler_Disziplin_Ergebnis e2
                              WHERE e2.SchuelerID = s.SchuelerID AND e2.Disziplin = ? AND e2.ErgebnisNR = 2
                              ORDER BY e2.created_at DESC
                              LIMIT 1) = 'OK' THEN 1 ELSE 0
                    END AS Runde2_Fertig,
                    CASE
                        WHEN (SELECT e3.status
                              FROM Schueler_Disziplin_Ergebnis e3
                              WHERE e3.SchuelerID = s.SchuelerID AND e3.Disziplin = ? AND e3.ErgebnisNR = 3
                              ORDER BY e3.created_at DESC
                              LIMIT 1) = 'OK' THEN 1 ELSE 0
                    END AS Runde3_Fertig,
                    COALESCE(sd.Abwesend, 0) AS Abwesend,
                    COALESCE((SELECT e1.result_value
                              FROM Schueler_Disziplin_Ergebnis e1
                              WHERE e1.SchuelerID = s.SchuelerID AND e1.Disziplin = ? AND e1.ErgebnisNR = 1
                              ORDER BY e1.created_at DESC
                              LIMIT 1), 0) AS Ergebnis1,
                    COALESCE((SELECT e2.result_value
                              FROM Schueler_Disziplin_Ergebnis e2
                              WHERE e2.SchuelerID = s.SchuelerID AND e2.Disziplin = ? AND e2.ErgebnisNR = 2
                              ORDER BY e2.created_at DESC
                              LIMIT 1), 0) AS Ergebnis2,
                    COALESCE((SELECT e3.result_value
                              FROM Schueler_Disziplin_Ergebnis e3
                              WHERE e3.SchuelerID = s.SchuelerID AND e3.Disziplin = ? AND e3.ErgebnisNR = 3
                              ORDER BY e3.created_at DESC
                              LIMIT 1), 0) AS Ergebnis3
                FROM schueler s
                LEFT JOIN Schueler_Disziplin sd
                  ON s.SchuelerID = sd.SchuelerID AND sd.Disziplin = ?
                WHERE s.RiegenfuehrerName = ?
                ORDER BY s.klasse, s.Klassenbuchstabe, s.name
                """,
                (disziplin, disziplin, disziplin,
                 disziplin, disziplin, disziplin,
                 disziplin, riegenfuehrer)
            )
        else:
            # Allgemeine Abfrage ohne Disziplin
            self.cursor.execute(
                """
                SELECT
                    s.klasse,
                    s.Klassenbuchstabe,
                    s.geschlecht,
                    s.name,
                    s.vorname,
                    s.SchuelerID,
                    0 AS Runde1_Fertig,
                    0 AS Runde2_Fertig,
                    0 AS Runde3_Fertig,
                    0 AS Abwesend,
                    0 AS Ergebnis1,
                    0 AS Ergebnis2,
                    0 AS Ergebnis3
                FROM schueler s
                WHERE s.RiegenfuehrerName = ?
                ORDER BY s.klasse, s.Klassenbuchstabe, s.name
                """,
                (riegenfuehrer,)
            )

        data = self.cursor.fetchall()
        return [
            (
                row[0], row[1], row[2], row[3], row[4], row[5],  # Klasse, Buchstabe, Geschlecht, Name, Vorname, ID
                bool(row[6]), bool(row[7]), bool(row[8]), bool(row[9]),  # Runde1, Runde2, Runde3, Abwesend
                row[10], row[11], row[12]  # Ergebnis1, Ergebnis2, Ergebnis3
            )
            for row in data
        ]

    def calc_schwierigkeit(self, alter):
        # Platzhalter: Altersabhängige Berechnung der Schwierigkeit kann hier implementiert werden.
        pass

    # Ergebnistabelle sicherstellen (eine Zeile pro Ergebnis und Runde)
    def ensure_results_table(self):
        """Erstellt die Ergebnistabelle, falls nicht vorhanden."""
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS Schueler_Disziplin_Ergebnis (
                id INTEGER PRIMARY KEY,
                SchuelerID INTEGER NOT NULL,
                Disziplin TEXT NOT NULL,
                ErgebnisNR INTEGER NOT NULL CHECK (ErgebnisNR IN (1,2,3)),
                result_value REAL NULL,
                status TEXT NOT NULL, -- 'OK' oder 'ABWESEND'
                source_ipad_number TEXT NULL,
                source_station TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (SchuelerID) REFERENCES Schueler(SchuelerID)
            );
            '''
        )
        self.cursor.execute(
            '''
            CREATE INDEX IF NOT EXISTS idx_erz_lookup
            ON Schueler_Disziplin_Ergebnis (SchuelerID, Disziplin, ErgebnisNR, created_at DESC)
            '''
        )
        self.connection.commit()

    def insert_result_entry(self, schueler_id, disziplin, runde, result_value, status='OK', source_ipad_number=None, source_station=None):
        """Fügt einen Eintrag in die Ergebnistabelle hinzu (eine Zeile pro Runde)."""
        try:
            self.cursor.execute(
                '''
                INSERT INTO Schueler_Disziplin_Ergebnis
                    (SchuelerID, Disziplin, ErgebnisNR, result_value, status, source_ipad_number, source_station)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (schueler_id, disziplin, runde, result_value, status, source_ipad_number, source_station)
            )
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Fehler beim Einfügen des Ergebnisses: {e}")
            return False

    def get_latest_results_for_riege(self, riegenfuehrer, disziplin):
        """Liefert für jede Runde je Schüler den neuesten Eintrag (value und status)."""
        self.cursor.execute(
            """
            SELECT
                s.SchuelerID,
                s.name,
                s.vorname,
                -- Runde 1
                (SELECT e1.result_value FROM Schueler_Disziplin_Ergebnis e1
                 WHERE e1.SchuelerID = s.SchuelerID AND e1.Disziplin = ? AND e1.ErgebnisNR = 1
                 ORDER BY e1.created_at DESC LIMIT 1) AS r1_value,
                (SELECT e1.status FROM Schueler_Disziplin_Ergebnis e1
                 WHERE e1.SchuelerID = s.SchuelerID AND e1.Disziplin = ? AND e1.ErgebnisNR = 1
                 ORDER BY e1.created_at DESC LIMIT 1) AS r1_status,
                -- Runde 2
                (SELECT e2.result_value FROM Schueler_Disziplin_Ergebnis e2
                 WHERE e2.SchuelerID = s.SchuelerID AND e2.Disziplin = ? AND e2.ErgebnisNR = 2
                 ORDER BY e2.created_at DESC LIMIT 1) AS r2_value,
                (SELECT e2.status FROM Schueler_Disziplin_Ergebnis e2
                 WHERE e2.SchuelerID = s.SchuelerID AND e2.Disziplin = ? AND e2.ErgebnisNR = 2
                 ORDER BY e2.created_at DESC LIMIT 1) AS r2_status,
                -- Runde 3
                (SELECT e3.result_value FROM Schueler_Disziplin_Ergebnis e3
                 WHERE e3.SchuelerID = s.SchuelerID AND e3.Disziplin = ? AND e3.ErgebnisNR = 3
                 ORDER BY e3.created_at DESC LIMIT 1) AS r3_value,
                (SELECT e3.status FROM Schueler_Disziplin_Ergebnis e3
                 WHERE e3.SchuelerID = s.SchuelerID AND e3.Disziplin = ? AND e3.ErgebnisNR = 3
                 ORDER BY e3.created_at DESC LIMIT 1) AS r3_status
            FROM schueler s
            WHERE s.RiegenfuehrerName = ?
            ORDER BY s.klasse, s.Klassenbuchstabe, s.name
            """,
            (disziplin, disziplin, disziplin, disziplin, disziplin, disziplin, riegenfuehrer)
        )
        return self.cursor.fetchall()

    def get_relative_punktzahl(self):
        punkte_ehrenurkunde = [
            [[10, "m"], 720],
            [[10, "w"], 680],
        ]
        return punkte_ehrenurkunde

    def get_schuelerdata(self):
        """Rohdaten aller Schüler (ohne Disziplin-Bezug) für Übersichten/Exporte."""
        self.cursor.execute(
            """
            SELECT
                schueler.Klasse,
                schueler.Klassenbuchstabe,
                schueler.Name,
                schueler.Vorname,
                schueler.Gesamtpunktzahl,
                schueler.Note,
                schueler.Uhrkunde
            FROM schueler
            ORDER BY schueler.Klasse, schueler.Klassenbuchstabe, schueler.Name;
            """
        )
        return self.cursor.fetchall()

    def get_disziplin_data(self, name, vorname, disziplin):
        """Liefert Stammdaten inkl. Disziplin und Schwierigkeit für einen Schüler (Name/Vorname)."""
        self.cursor.execute(
            """
            SELECT
                schueler.Klasse,
                schueler.klassenbuchstabe,
                schueler.Name,
                schueler.vorname,
                Schueler_Disziplin.Disziplin,
                Schueler_Disziplin.Schwierigkeit
            FROM schueler
            JOIN Schueler_Disziplin ON schueler.SchuelerID = Schueler_Disziplin.SchuelerID
            WHERE schueler.name = ?
            AND schueler.vorname = ?
            AND Schueler_Disziplin.Disziplin = ?
            ORDER BY schueler.Klasse, schueler.Name, Schueler_Disziplin.Punktzahl DESC;
            """,
            (name, vorname, disziplin,)
        )
        return self.cursor.fetchall()

    def get_disziplin_ergebnis(self, name, vorname, disziplin, klasse=None, klassenbuchstabe=None):
        if klasse is None and klassenbuchstabe is None:
            self.cursor.execute(
                """
                SELECT
                    schueler.Klasse,
                    schueler.Klassenbuchstabe,
                    schueler.Name,
                    schueler.vorname,
                    Schueler_Disziplin.Disziplin,
                    Schueler_Disziplin.Punktzahl,
                    Schueler_Disziplin.Ergebnis1,
                    Schueler_Disziplin.Ergebnis2,
                    Schueler_Disziplin.Ergebnis3
                FROM schueler
                JOIN Schueler_Disziplin ON schueler.SchuelerID = Schueler_Disziplin.SchuelerID
                WHERE schueler.name = ?
                AND schueler.vorname = ?
                AND Schueler_Disziplin.Disziplin = ?
                ORDER BY schueler.Klasse, schueler.Name, Schueler_Disziplin.Punktzahl DESC;
                """,
                (name, vorname, disziplin,)
            )
        else:
            self.cursor.execute(
                """
                SELECT
                    schueler.Klasse,
                    schueler.Klassenbuchstabe,
                    schueler.Name,
                    schueler.vorname,
                    Schueler_Disziplin.Disziplin,
                    Schueler_Disziplin.Punktzahl,
                    Schueler_Disziplin.Ergebnis1,
                    Schueler_Disziplin.Ergebnis2,
                    Schueler_Disziplin.Ergebnis3
                FROM schueler
                JOIN Schueler_Disziplin ON schueler.SchuelerID = Schueler_Disziplin.SchuelerID
                WHERE schueler.name = ?
                AND schueler.vorname = ?
                AND Schueler_Disziplin.Disziplin = ?
                AND schueler.klasse = ?
                AND schueler.klassenbuchstabe = ?
                ORDER BY schueler.Klasse, schueler.Name, Schueler_Disziplin.Punktzahl DESC;
                """,
                (name, vorname, disziplin, klasse, klassenbuchstabe)
            )

        return self.cursor.fetchall()

    def update_student_round_status(self, schueler_id, disziplin, runde, status=True):
        """
        Diese Methode ist nicht mehr nötig, da der Status direkt über die Ergebnis-Spalten bestimmt wird.
        Verwenden Sie stattdessen update_student_result() um ein Ergebnis zu speichern.
        """
        print("Warning: update_student_round_status ist deprecated. Verwenden Sie update_student_result().")
        return True

    def update_student_result(self, schueler_id, disziplin, runde, ergebnis):
        """
        Speichert das Ergebnis einer Runde als neue Zeile in der Ergebnistabelle.
        runde: 1, 2, oder 3
        ergebnis: numerischer Messwert (z. B. Sekunden, Weite, etc.)
        """
        try:
            # Sicherstellen, dass Stammdatensatz für die Disziplin existiert (Kompatibilität)
            self.cursor.execute('''
                SELECT SchuelerID FROM Schueler_Disziplin
                WHERE SchuelerID = ? AND Disziplin = ?
            ''', (schueler_id, disziplin))
            exists = self.cursor.fetchone()
            if not exists:
                self.cursor.execute('''
                    INSERT INTO Schueler_Disziplin (SchuelerID, Disziplin, Schwierigkeit, Abwesend)
                    VALUES (?, ?, ?, ?)
                ''', (schueler_id, disziplin, 1, 0))
            else:
                # Abwesenheit auf 0 setzen, da ein Ergebnis eingetragen wird
                self.cursor.execute('''
                    UPDATE Schueler_Disziplin
                    SET Abwesend = 0
                    WHERE SchuelerID = ? AND Disziplin = ?
                ''', (schueler_id, disziplin))

            # Neues Ergebnis einfügen (Status OK). Quelle wird später im Routing ergänzt.
            self.cursor.execute(
                '''
                INSERT INTO Schueler_Disziplin_Ergebnis
                    (SchuelerID, Disziplin, ErgebnisNR, result_value, status, source_ipad_number, source_station)
                VALUES (?, ?, ?, ?, 'OK', NULL, NULL)
                ''',
                (schueler_id, disziplin, runde, ergebnis)
            )
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Fehler beim Speichern des Ergebnisses: {e}")
            return False

    def mark_student_absent(self, schueler_id, disziplin, absent=True):
        """
        Markiert einen Schüler als abwesend für eine spezifische Disziplin
        """
        try:
            # Erst prüfen ob Eintrag existiert
            self.cursor.execute('''
                SELECT SchuelerID FROM Schueler_Disziplin
                WHERE SchuelerID = ? AND Disziplin = ?
            ''', (schueler_id, disziplin))

            exists = self.cursor.fetchone()

            if not exists:
                # Eintrag erstellen
                self.cursor.execute('''
                    INSERT INTO Schueler_Disziplin (SchuelerID, Disziplin, Schwierigkeit, Abwesend)
                    VALUES (?, ?, ?, ?)
                ''', (schueler_id, disziplin, 1, 1 if absent else 0))
            else:
                # Abwesenheit aktualisieren
                self.cursor.execute('''
                    UPDATE Schueler_Disziplin
                    SET Abwesend = ?
                    WHERE SchuelerID = ? AND Disziplin = ?
                ''', (1 if absent else 0, schueler_id, disziplin))

            self.connection.commit()
            return True

        except Exception as e:
            print(f"Fehler beim Markieren als abwesend: {e}")
            return False

    def get_student_id_by_name(self, name, vorname):
        """
        Findet die SchuelerID basierend auf Name und Vorname
        """
        try:
            self.cursor.execute('''
                SELECT SchuelerID FROM Schueler
                WHERE Name = ? AND Vorname = ?
            ''', (name, vorname))

            result = self.cursor.fetchone()
            return result[0] if result else None

        except Exception as e:
            print(f"Fehler beim Finden der SchuelerID: {e}")
            return None

    def get_student_result(self, riegenfuehrer, disziplin, schueler_id, runde):
        """
        Gibt das neueste Ergebnis (value) und den Fertig-Status ('OK') für eine Runde zurück.
        """
        print(f"DEBUG get_student_result: riegenfuehrer={riegenfuehrer}, disziplin={disziplin}, schueler_id={schueler_id}, runde={runde}")
        try:
            # Neuester Eintrag je Runde aus Ergebnistabelle
            self.cursor.execute(
                """
                SELECT e.result_value, e.status
                FROM Schueler_Disziplin_Ergebnis e
                JOIN schueler s ON s.SchuelerID = e.SchuelerID
                WHERE s.RiegenfuehrerName = ?
                  AND e.SchuelerID = ?
                  AND e.Disziplin = ?
                  AND e.ErgebnisNR = ?
                ORDER BY e.created_at DESC
                LIMIT 1
                """,
                (riegenfuehrer, schueler_id, disziplin, runde)
            )
            row = self.cursor.fetchone()
            print(f"DEBUG Latest result row: {row}")
            if row:
                value, status = row
                if status == 'OK':
                    return {'result': value, 'round_completed': True}
                else:
                    return {'result': None, 'round_completed': False}
            return None
        except Exception as e:
            print(f"ERROR in get_student_result: {e}")
            return None

# Entfernt: ungenutzte Klasse Create_db_from_csv




def insert_riegenfuehrer(riegen, db_path=DB_PATH):
    #fügt riegenführer aus einer .txt in die sql-datenbank ein
    keys = []
    values = []
    for key, value in riegen.items():
        keys.append(key)
        values.append(value)

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert the data
    for i, (name, riege_id) in enumerate(zip(keys, values)):
        cursor.execute('''
        UPDATE Schueler
        SET RiegenfuehrerName = ?
        WHERE SchuelerID = ?
        ''', (name, riege_id))

    # Commit changes and close connection
    conn.commit()
    conn.close()

def clean_riegenfuehrer(data):
    # Extrahiert den Namen aus jedem Tupel und gibt eine saubere Liste zurück
    return [name[0] for name in data]

def setup_database_with_csv(csv_path='backend/Mappe1.csv', db_path=DB_PATH):
    """
    Hauptfunktion zum Einrichten der Datenbank mit CSV-Daten

    Args:
        csv_path (str): Pfad zur CSV-Datei
        db_path (str): Pfad zur Datenbank-Datei

    Returns:
        bool: True wenn erfolgreich, False bei Fehlern
    """
    try:
        # Sicherstellen, dass das Verzeichnis existiert
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Verbindung zur Datenbank herstellen
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Tabellen erstellen
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Schueler (
            SchuelerID INTEGER PRIMARY KEY,
            Name TEXT,
            Vorname TEXT,
            Geschlecht TEXT,
            Klasse INTEGER,
            Klassenbuchstabe TEXT,
            Geburtsjahr INTEGER,
            Bundesjugentspielalter INTEGER,
            Profil BOOLEAN,
            RiegenfuehrerName TEXT,
            Gesamtpunktzahl INTEGER,
            Note INTEGER,
            Uhrkunde TEXT
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Schueler_Disziplin (
            SchuelerID INTEGER,
            Disziplin TEXT,
            Schwierigkeit INTEGER,
            Ergebnis1 REAL,
            Ergebnis2 REAL,
            Ergebnis3 REAL,
            Punktzahl INTEGER,
            Abwesend INTEGER DEFAULT 0,
            PRIMARY KEY (SchuelerID, Disziplin),
            FOREIGN KEY (SchuelerID) REFERENCES Schueler(SchuelerID)
        );
        ''')

        # Bestehende Daten löschen
        cursor.execute('DELETE FROM Schueler_Disziplin')
        cursor.execute('DELETE FROM Schueler')

        # Tabelle neu erstellen um sicherzustellen, dass Profil-Spalte existiert
        cursor.execute('DROP TABLE IF EXISTS Schueler')
        cursor.execute('''
        CREATE TABLE Schueler (
            SchuelerID INTEGER PRIMARY KEY,
            Name TEXT,
            Vorname TEXT,
            Geschlecht TEXT,
            Klasse INTEGER,
            Klassenbuchstabe TEXT,
            Geburtsjahr INTEGER,
            Bundesjugentspielalter INTEGER,
            Profil BOOLEAN,
            RiegenfuehrerName TEXT,
            Gesamtpunktzahl INTEGER,
            Note INTEGER,
            Uhrkunde TEXT
        );
        ''')

        # CSV-Daten laden
        df = pd.read_csv(csv_path, delimiter=';')
        data = np.array(df)
        # Index hinzufügen (1-basiert)
        index = np.arange(1, len(data) + 1).reshape(-1, 1)
        data = np.hstack((index, data))

        # Disziplinen definieren
        disziplinen = ["Wurf/Stoßen", "Laufen", "Sprint", "Weitsprung"]

        # Schüler einfügen
        for i in range(len(data)):
            schueler_data = data[i]

            # CSV-Spalten: [ID], Geschlecht, Klasse, Name, Vorname, Geburtsjahr, Profil
            # Profil-Wert von String zu Boolean konvertieren
            profil_value = str(schueler_data[6]).strip().lower() == 'true'

            # Schüler einfügen mit korrekten Spalten-Indizes
            cursor.execute('''
            INSERT INTO Schueler (SchuelerID, Name, Vorname, Geschlecht, Klasse, Klassenbuchstabe,
                                Geburtsjahr, Bundesjugentspielalter, Profil, riegenfuehrerName,
                                Gesamtpunktzahl, Note, Uhrkunde)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''', (
                schueler_data[0],  # ID (hinzugefügter Index)
                schueler_data[3],  # Name
                schueler_data[4],  # Vorname
                schueler_data[1],  # Geschlecht
                schueler_data[2][:-1],  # Klasse (ohne letzten Buchstaben)
                schueler_data[2][-1:],  # Klassenbuchstabe (letzter Buchstabe)
                schueler_data[5],  # Geburtsjahr
                12,  # Alter (standardmäßig 12)
                profil_value,  # Profil (Boolean)
                None,  # Riegenführername (wird später über Admin zugewiesen)
                None,  # Gesamtpunktzahl
                None,  # Note
                None   # Urkunde
            ))

            # Disziplin-Daten für den Schüler einfügen
            for disziplin in disziplinen:
                schwierigkeit = 100  # Standardwert
                cursor.execute('''
                    INSERT INTO Schueler_Disziplin (SchuelerID, Disziplin, Schwierigkeit,
                                                  Ergebnis1, Ergebnis2, Ergebnis3, Punktzahl)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (schueler_data[0], disziplin, schwierigkeit, None, None, None, None))

        conn.commit()
        conn.close()
        print(f"Import erfolgreich abgeschlossen! {len(data)} Schüler wurden eingefügt.")
        return True

    except Exception as e:
        print(f"Fehler beim Import: {e}")
        return False

def initialize_database_from_csv(csv_path='backend/Mappe1.csv', db_path=DB_PATH):
    """
    Initialisiert die Datenbank mit Daten aus einer CSV-Datei.

    Args:
        csv_path (str): Pfad zur CSV-Datei mit Schülerdaten
        db_path (str): Pfad zur Datenbank-Datei

    Returns:
        bool: True wenn erfolgreich, False bei Fehlern
    """
    print("Initialisiere Datenbank mit CSV-Daten...")
    success = setup_database_with_csv(csv_path, db_path)

    if success:
        print("Datenbank wurde erfolgreich initialisiert!")
    else:
        print("Fehler bei der Datenbank-Initialisierung!")

    return success

class RiegenManager:
    """Verwaltet die Riegen-Einteilung basierend auf Geschlecht, Profil und Stufe"""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_riegen_tables()

    def create_riegen_tables(self):
        """Erstellt Tabellen für Riegenführer und Riegen-Konfiguration"""
        # Tabelle für Riegenführer
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS Riegenfuehrer (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT UNIQUE NOT NULL,
            Geschlecht TEXT NOT NULL,
            Profil BOOLEAN NOT NULL,
            Stufe INTEGER NOT NULL,
            Klassenendungen TEXT NOT NULL
        );
        ''')

        # Tabelle für Riegen-Zuordnungen
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS Riegen_Zuordnung (
            SchuelerID INTEGER,
            RiegenfuehrerID INTEGER,
            PRIMARY KEY (SchuelerID),
            FOREIGN KEY (SchuelerID) REFERENCES Schueler(SchuelerID),
            FOREIGN KEY (RiegenfuehrerID) REFERENCES Riegenfuehrer(ID)
        );
        ''')

        self.conn.commit()

    def add_riegenfuehrer(self, name, geschlecht, profil, stufe, klassenendungen):
        """Fügt einen neuen Riegenführer hinzu"""
        try:
            self.cursor.execute('''
            INSERT INTO Riegenfuehrer (Name, Geschlecht, Profil, Stufe, Klassenendungen)
            VALUES (?, ?, ?, ?, ?)
            ''', (name, geschlecht, profil, stufe, ','.join(klassenendungen)))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_riegenfuehrer(self):
        """Holt alle Riegenführer"""
        self.cursor.execute('''
        SELECT ID, Name, Geschlecht, Profil, Stufe, Klassenendungen
        FROM Riegenfuehrer
        ORDER BY Name
        ''')
        return self.cursor.fetchall()

    def delete_riegenfuehrer(self, riegenfuehrer_id):
        """Löscht einen Riegenführer"""
        self.cursor.execute('DELETE FROM Riegenfuehrer WHERE ID = ?', (riegenfuehrer_id,))
        self.conn.commit()

    def assign_riegen_automatically(self):
        """Teilt Schüler automatisch in Riegen ein basierend auf den Kriterien"""
        # Alle Schüler holen
        self.cursor.execute('''
        SELECT SchuelerID, Geschlecht, Klasse, Klassenbuchstabe, Geburtsjahr, Profil
        FROM Schueler
        ''')
        schueler = self.cursor.fetchall()

        # Vorherige Zuordnungen löschen
        self.cursor.execute('DELETE FROM Riegen_Zuordnung')

        for schueler_data in schueler:
            schueler_id, geschlecht, klasse, klassenbuchstabe, geburtsjahr, profil = schueler_data

            # Profil-Wert direkt aus der Datenbank verwenden (ist bereits Boolean)
            # Passenden Riegenführer finden
            riegenfuehrer_id = self.find_matching_riegenfuehrer(
                geschlecht, profil, klasse, klassenbuchstabe
            )

            if riegenfuehrer_id:
                # Zuordnung erstellen
                self.cursor.execute('''
                INSERT INTO Riegen_Zuordnung (SchuelerID, RiegenfuehrerID)
                VALUES (?, ?)
                ''', (schueler_id, riegenfuehrer_id))

                # Riegenführer-Name in Schüler-Tabelle aktualisieren
                riegenfuehrer_name = self.get_riegenfuehrer_name(riegenfuehrer_id)
                self.cursor.execute('''
                UPDATE Schueler SET RiegenfuehrerName = ? WHERE SchuelerID = ?
                ''', (riegenfuehrer_name, schueler_id))

        self.conn.commit()
        return True

    def find_matching_riegenfuehrer(self, geschlecht, profil, stufe, klassenbuchstabe):
        """Findet passenden Riegenführer für einen Schüler"""
        self.cursor.execute('''
        SELECT ID FROM Riegenfuehrer
        WHERE Geschlecht = ? AND Profil = ? AND Stufe = ?
        AND (Klassenendungen LIKE ? OR Klassenendungen LIKE ?)
        LIMIT 1
        ''', (geschlecht, profil, stufe, f'%{klassenbuchstabe}%', '%*%'))

        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_riegenfuehrer_name(self, riegenfuehrer_id):
        """Holt den Namen eines Riegenführers"""
        self.cursor.execute('SELECT Name FROM Riegenfuehrer WHERE ID = ?', (riegenfuehrer_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_riegen_statistics(self):
        """Holt Statistiken über die Riegen-Einteilung"""
        self.cursor.execute('''
        SELECT
            r.Name,
            r.Geschlecht,
            r.Profil,
            r.Stufe,
            COUNT(rz.SchuelerID) as Anzahl_Schueler,
            GROUP_CONCAT(DISTINCT s.Profil) as Schueler_Profile
        FROM Riegenfuehrer r
        LEFT JOIN Riegen_Zuordnung rz ON r.ID = rz.RiegenfuehrerID
        LEFT JOIN Schueler s ON rz.SchuelerID = s.SchuelerID
        GROUP BY r.ID, r.Name, r.Geschlecht, r.Profil, r.Stufe
        ORDER BY r.Name
        ''')
        return self.cursor.fetchall()

    def close(self):
        """Schließt die Datenbankverbindung"""
        self.conn.close()

# Entfernt: doppelte Definition von initialize_database_from_csv (Duplikat)

def main():
    # Einfache Initialisierung und kleiner Smoke-Test (nur für lokale Entwicklung)
    initialize_database_from_csv("backend/Mappe1.csv")
    db = Backend(DB_PATH)
    print("Beispiel-Ergebnisse:")
    print(db.get_ergebnisse_alle())


# Example usage when running this file directly
if __name__ == "__main__":
    main()
