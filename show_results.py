import os
import sqlite3
import sys


def show_results(db_path):
    # Füge .db hinzu, falls der Benutzer es vergessen hat, aber die Datei ohne Endung nicht existiert
    if not os.path.exists(db_path) and not db_path.endswith(".db"):
        candidate = db_path + ".db"
        if os.path.exists(candidate):
            db_path = candidate

    # Versuche auch im database/ Ordner zu schauen, falls nur der Dateiname angegeben wurde
    if not os.path.exists(db_path):
        candidate = os.path.join("database", db_path)
        if os.path.exists(candidate):
            db_path = candidate

    if not os.path.exists(db_path):
        print(f"Fehler: Die Datenbankdatei '{db_path}' wurde nicht gefunden.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Abfrage der Schüler und ihrer Ergebnisse
        query = """
        SELECT
            s.Vorname,
            s.Name,
            s.Klasse,
            s.Klassenbuchstabe,
            e.Disziplin,
            e.result_value,
            e.status
        FROM Schueler_Disziplin_Ergebnis e
        JOIN Schueler s ON e.SchuelerID = s.SchuelerID
        ORDER BY e.created_at DESC
        LIMIT 20
        """

        try:
            cursor.execute(query)
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                print(
                    f"Die Datenbank '{db_path}' scheint keine gültige BJS-Datenbank zu sein (Tabellen fehlen)."
                )
                return
            raise e

        if not rows:
            print(f"Keine Ergebnisse in '{db_path}' gefunden.")

            # Prüfen, ob zumindest Schüler da sind
            cursor.execute("SELECT COUNT(*) FROM Schueler")
            count = cursor.fetchone()[0]
            print(f"Anzahl registrierter Schüler: {count}")
            return

        print(f"\n--- Letzte 20 Ergebnisse aus {os.path.basename(db_path)} ---\n")

        # Tabellenkopf formatieren
        header = f"{'Vorname':<15} {'Nachname':<15} {'Klasse':<8} {'Disziplin':<20} {'Wert':<10} {'Status':<10}"
        print(header)
        print("-" * len(header))

        for row in rows:
            vorname, nachname, klasse, buch, disziplin, wert, status = row

            # None-Werte sicher handhaben
            vorname = vorname or ""
            nachname = nachname or ""
            klasse_full = f"{klasse or ''}{buch or ''}"
            disziplin = disziplin or ""

            wert_str = str(wert) if wert is not None else "-"
            status_str = status if status else "OK"

            print(
                f"{vorname:<15} {nachname:<15} {klasse_full:<8} {disziplin:<20} {wert_str:<10} {status_str:<10}"
            )

        conn.close()

    except sqlite3.Error as e:
        print(f"Datenbankfehler: {e}")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Bitte gib den Namen oder Pfad der Datenbank ein.")
        print("Beispiele: 'BJS_2026_1.db' oder 'database/BJS_2026_1.db'")
        db_input = input("Datenbank: ").strip()

        if db_input:
            # Entferne Anführungszeichen, falls der User per Drag & Drop den Pfad eingefügt hat
            db_input = db_input.strip('"').strip("'")
            show_results(db_input)
        else:
            print("Keine Eingabe. Programm beendet.")
    else:
        show_results(sys.argv[1])
