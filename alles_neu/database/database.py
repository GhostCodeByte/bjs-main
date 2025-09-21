import sqlite3
from datetime import datetime

JAHR = datetime.now().year
id_counter = 0

class Database:
    # Die ID kann genuzt werden wen man mehrere datenbanken gleichzeitig haben will 
    def __init__(self, id = None):

        if id == None:
            id = JAHR

        self.connection = sqlite3.connect(f"bjs_database_{id}.db")
        self.cursor = self.connection.cursor()
        self.connection.commit()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        if not self.cursor.fetchall():
            self.datenbank_erstellen()
        else:
            print("Datenbank existiert bereits und wird verwendet")

    def datenbank_erstellen(self):
        self.cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS Schueler (
                SchuelerID        INTEGER PRIMARY KEY,
                Name              TEXT,
                Vorname           TEXT,
                Geschlecht        TEXT,
                Klasse            INTEGER,
                Klassenbuchstabe  TEXT,
                Geburtsjahr       INTEGER,
                Bundesjugentspielalter INTEGER,
                Profil            BOOLEAN,
                RiegenfuehrerName TEXT,
                Gesamtpunktzahl   INTEGER,
                Note              INTEGER,
                Urkunde           TEXT
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
            geschlecht: str, #"m" oder "w"
            klasse: int,
            klassenbuchstabe: str,
            geburtsjahr: int,
            profil: bool
        ):
        alter = JAHR - geburtsjahr
        global id_counter

        self.cursor.execute('''
        INSERT INTO Schueler (SchuelerID, Name, Vorname, Geschlecht, Klasse, Klassenbuchstabe,
                            Geburtsjahr, Bundesjugentspielalter, Profil, RiegenfuehrerName,
                            Gesamtpunktzahl, Note, Urkunde)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        ''', (
            id_counter,  # ID (hinzugefügter Index)
            name,  # Name
            vorname,  # Vorname
            geschlecht,  # Geschlecht
            klasse,  # Klasse (ohne letzten Buchstaben)
            klassenbuchstabe,  # Klassenbuchstabe (letzter Buchstabe)
            geburtsjahr,  # Geburtsjahr
            alter,  # Alter (standardmäßig 12)
            profil,  # Profil (Boolean)
            None,  # Riegenführername (wird später über Admin zugewiesen)
            None,  # Gesamtpunktzahl
            None,  # Note
            None   # Urkunde
        ))
        id_counter += 1
        self.connection.commit()


    def add_riegenfuehrer(
            self,
            name,
            geschlecht,
            profil,
            stufe,
            klassenendung
        ):
        pass

if __name__ == "__main__":
    db = Database()