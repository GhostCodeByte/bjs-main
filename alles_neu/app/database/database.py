import sqlite3
from datetime import datetime
from alles_neu.admin.admin_database import Database as admin_db


class Database:
    # Die ID kann genuzt werden wen man mehrere datenbanken gleichzeitig haben will
    def __init__(self, id=None, path=None):

        if id == None:
            id = datetime.now().year

        if path is None:
            path = f"alles_neu/app/database/bjs_database_{id}.db"

        admin_db_instance = admin_db(path=path)

        admin_db_instance.connection.close()

        self.connection = sqlite3.connect(path)
        self.cursor = self.connection.cursor()

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

    def close(self):
        self.connection.close()


if __name__ == "__main__":
    db = Database()
