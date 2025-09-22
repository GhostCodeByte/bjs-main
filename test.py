import sqlite3

conn = sqlite3.connect("alles_neu/app/database/bjs_database_2025.db")  # Pfad zu deiner DB
cursor = conn.cursor()

# Riegenführer einfügen (falls noch nicht vorhanden)
cursor.execute("""
    INSERT OR IGNORE INTO Riegenfuehrer (Name, Geschlecht, Profil, Stufe, Klassenendungen)
    VALUES (?, ?, ?, ?, ?)
""", ("elian", "M", 1, 5, "a"))

# Schüler updaten
cursor.execute("""
    UPDATE Schueler
    SET RiegenfuehrerID = 1
    WHERE Geschlecht = ? AND Profil = ? AND Klasse = ? AND Klassenbuchstabe = ?
""", ("M", 1, 5, "a"))

conn.commit()
conn.close()
