import sqlite3
from datetime import datetime
import os

class Database:
    # Die ID kann genuzt werden wen man mehrere datenbanken gleichzeitig haben will 
    def __init__(self, id = None):

        if id == None:
            id = datetime.now().year

        self.connection = sqlite3.connect(f"bjs_database_{id}.db")
        self.cursor = self.connection.cursor()
        self.connection.execute("PRAGMA foreign_keys = ON")
        
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
                RiegenfuehrerID   INTEGER,
                Gesamtpunktzahl   INTEGER,
                Note              INTEGER,
                Urkunde           TEXT,
                FOREIGN KEY (RiegenfuehrerID) REFERENCES Riegenfuehrer(ID)
            )
        """)


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

if __name__ == "__main__":
    db = Database()