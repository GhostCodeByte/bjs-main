import sqlite3
from datetime import datetime


class Database:
    # Die ID kann genuzt werden wen man mehrere datenbanken gleichzeitig haben will
    def __init__(self, id=None, path=None):
        if id == None:
            id = datetime.now().year

        if path is None:
            path = f"alles_neu/app/database/bjs_database_{id}.db"

        self.connection = sqlite3.connect(path)
        self.cursor = self.connection.cursor()
        self.connection.commit()

        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table';")
        if not self.cursor.fetchall():
            self.datenbank_erstellen()
        else:
            print("Datenbank existiert bereits und wird verwendet")

    def get_riegenfuehrer(self):
        self.cursor.execute("SELECT * FROM Riegenfuehrer")
        return self.cursor.fetchall()

    def get_riege(self, riegenfuehrer_id):
        self.cursor.execute(
            """
            SELECT SchuelerID, Name, Vorname, Geschlecht, Bundesjugentspielalter
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
                "Round1": None,
                "Round2": None,
                "Round3": None,
            }
            schueler_liste.append(schueler)

        return schueler_liste

    def get_rounds_done(self, schueler_id, disziplin):
        self.cursor.execute("""
            SELECT
                ErgebnisNR,
                CASE
                    WHEN SUM(CASE WHEN status = 'OK' THEN 1 ELSE 0 END) > 0 THEN 'OK'
                    WHEN SUM(CASE WHEN status = 'ABWESEND' THEN 1 ELSE 0 END) > 0 THEN 'ABWESEND'
                END AS round_status
            FROM Schueler_Disziplin_Ergebnis
            WHERE SchuelerID = ? AND Disziplin = ?
            GROUP BY ErgebnisNR
            HAVING
                SUM(CASE WHEN status = 'OK' THEN 1 ELSE 0 END) > 0
                OR SUM(CASE WHEN status = 'ABWESEND' THEN 1 ELSE 0 END) > 0
            ORDER BY ErgebnisNR
        """, (schueler_id, disziplin))
        return [(row[0], row[1]) for row in self.cursor.fetchall()]

    def add_entry(self, schueler_id, disziplin, ergebnis_nr, result_value, status, source_ipad_number, source_station):
        print(f"Adding entry: SchuelerID={schueler_id}, Disziplin={disziplin}, ErgebnisNR={ergebnis_nr}, result_value={result_value}, status={status}, source_ipad_number={source_ipad_number}, source_station={source_station}")
        self.cursor.execute("""
            INSERT INTO Schueler_Disziplin_Ergebnis (
                SchuelerID, Disziplin, ErgebnisNR, result_value, status,
                source_ipad_number, source_station
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (schueler_id, disziplin, ergebnis_nr, result_value, status, source_ipad_number, source_station))
        self.connection.commit()

    def datenbank_erstellen(self):
        self.cursor.execute(""" 
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
        )""")

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Schueler_Disziplin_Ergebnis (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                SchuelerID         INTEGER NOT NULL,
                Disziplin          TEXT NOT NULL,
                ErgebnisNR         INTEGER CHECK (ErgebnisNR IN (1, 2, 3)),
                result_value       REAL,
                status             TEXT CHECK (status IN ('OK', 'ABWESEND')),
                source_ipad_number TEXT,
                source_station     TEXT,
                created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (SchuelerID) REFERENCES Schueler(SchuelerID)
        )""")

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Riegenfuehrer (
                ID              INTEGER PRIMARY KEY AUTOINCREMENT,
                Name            TEXT UNIQUE NOT NULL,
                Geschlecht      TEXT NOT NULL,
                Profil          BOOLEAN NOT NULL,
                Stufe           INTEGER NOT NULL,
                Klassenendungen TEXT NOT NULL
        )""")

        print("neue Datenbank erstellt")

    def add_schueler(
        self,
        name: str,
        vorname: str,
        geschlecht: str,  # "m" oder "w"
        klasse: int,
        klassenbuchstabe: str,
        geburtsjahr: int,
        profil: bool
    ):
        alter = datetime.now().year - geburtsjahr

        self.cursor.execute('''
        INSERT INTO Schueler (SchuelerID, Name, Vorname, Geschlecht, Klasse, Klassenbuchstabe,
                            Geburtsjahr, Bundesjugentspielalter, Profil, RiegenfuehrerID,
                            Gesamtpunktzahl, Note, Urkunde)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        ''', (
            None,  # ID (AUTOINCREMENT)
            name,  # Name
            vorname,  # Vorname
            geschlecht,  # Geschlecht
            klasse,  # Klasse
            klassenbuchstabe,  # Klassenbuchstabe
            geburtsjahr,  # Geburtsjahr
            alter,  # Alter
            profil,  # Profil (Boolean)
            None,  # RiegenfuehrerID (wird später über Admin zugewiesen)
            None,  # Gesamtpunktzahl
            None,  # Note
            None   # Urkunde
        ))
        self.connection.commit()

    def add_riegenfuehrer(
        self,
        name,
        geschlecht,
        profil,
        stufe,
        klassenendung
    ):
        self.cursor.execute('''
        INSERT INTO Schueler (ID, Name, Geschlecht, Profil, Stufe, Klassenendungen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        ''', (
            None,  # ID (AUTOINCREMENT)
            name,  # Name des RF
            geschlecht,  # Geschlecht der Riege
            profil, # Profil der Schüler
            stufe,  # stufe der schüler
            klassenendung  # klassenendungen der Schüler
        ))
        self.connection.commit()

    def close(self):
        self.connection.close()


if __name__ == "__main__":
    db = Database()
