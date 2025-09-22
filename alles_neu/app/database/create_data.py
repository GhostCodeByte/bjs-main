import os
import sqlite3
import random
from datetime import datetime
import database

# Parameter
klassenstufen = list(range(5, 10))  # Klassen 5–9
buchstaben = ["a", "b", "c"]
anzahl_schueler_pro_klasse = 24

# Namen-Listen für Fake-Daten
vornamen_m = ["Max", "Lukas", "Jonas", "Paul", "Leon", "David", "Finn", "Noah", "Ben", "Elias"]
vornamen_w = ["Lea", "Lena", "Anna", "Sophie", "Emma", "Mia", "Clara", "Laura", "Hannah", "Marie"]
nachnamen = ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Wagner", "Becker", "Bauer", "Hoffmann", "Koch"]

# Alter grob passend (Klasse 5 ~ 11 Jahre, Klasse 9 ~ 15 Jahre)
basis_alter = {5: 11, 6: 12, 7: 13, 8: 14, 9: 15}
aktuelles_jahr = datetime.now().year

def ensure_tables(cursor):
    cursor.execute("""
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
            Urkunde           TEXT
        )
    """)


def generate_and_insert_schueler(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    ensure_tables(cursor)

    rows = []

    for stufe in klassenstufen:
        for b in buchstaben:
            for i in range(anzahl_schueler_pro_klasse):
                geschlecht = "M" if i < anzahl_schueler_pro_klasse / 2 else "W"
                if geschlecht == "M":
                    vorname = random.choice(vornamen_m)
                else:
                    vorname = random.choice(vornamen_w)
                name = random.choice(nachnamen)

                geburtsjahr = aktuelles_jahr - basis_alter[stufe]
                alter = basis_alter[stufe]
                profil = True if i < (anzahl_schueler_pro_klasse / 3) else False

                rows.append((
                    name,
                    vorname,
                    geschlecht,
                    stufe,
                    b,
                    geburtsjahr,
                    alter,
                    profil,
                    None,
                    None,
                    None,
                    None,
                ))

    cursor.executemany(
        """
        INSERT INTO Schueler (
            Name, Vorname, Geschlecht, Klasse, Klassenbuchstabe,
            Geburtsjahr, Bundesjugentspielalter, Profil, RiegenfuehrerID,
            Gesamtpunktzahl, Note, Urkunde
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    db_path = f"alles_neu/app/database/bjs_database_{datetime.now().year}.db"
    db = database.Database(path = db_path)
    generate_and_insert_schueler(db_path)
    print(f"Daten erfolgreich in die Datenbank eingefügt: {db_path}")
    db.close()