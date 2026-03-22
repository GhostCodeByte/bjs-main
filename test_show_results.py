"""Hilfsskript zum Anzeigen der zuletzt gespeicherten Ergebnisse aus einer SQLite-Datenbank."""

import os
import sqlite3
import sys


def show_results(datenbankpfad: str) -> None:
    """Zeigt die letzten 20 erfassten Ergebnisse einer BJS-Datenbank an."""
    # Ergänzt die Dateiendung automatisch, wenn nur der Dateiname ohne `.db` eingegeben wurde.
    if not os.path.exists(datenbankpfad) and not datenbankpfad.endswith(".db"):
        kandidat_pfad = datenbankpfad + ".db"
        if os.path.exists(kandidat_pfad):
            datenbankpfad = kandidat_pfad

    # Sucht zusätzlich im Standardordner `database/`, falls nur ein Dateiname übergeben wurde.
    if not os.path.exists(datenbankpfad):
        kandidat_pfad = os.path.join("database", datenbankpfad)
        if os.path.exists(kandidat_pfad):
            datenbankpfad = kandidat_pfad

    if not os.path.exists(datenbankpfad):
        print(f"Fehler: Die Datenbankdatei '{datenbankpfad}' wurde nicht gefunden.")
        return

    try:
        verbindung = sqlite3.connect(datenbankpfad)
        datenbank_cursor = verbindung.cursor()

        # Die Abfrage liest die neuesten Einträge mit den zugehörigen Stammdaten der Schüler.
        abfrage = """
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
            datenbank_cursor.execute(abfrage)
            ergebniszeilen = datenbank_cursor.fetchall()
        except sqlite3.OperationalError as fehler:
            if "no such table" in str(fehler):
                print(
                    f"Die Datenbank '{datenbankpfad}' scheint keine gueltige BJS-Datenbank zu sein (Tabellen fehlen)."
                )
                return
            raise

        if not ergebniszeilen:
            print(f"Keine Ergebnisse in '{datenbankpfad}' gefunden.")

            # Wenn noch keine Ergebnisse vorliegen, hilft die Schüleranzahl bei der Einordnung.
            datenbank_cursor.execute("SELECT COUNT(*) FROM Schueler")
            schueleranzahl = datenbank_cursor.fetchone()[0]
            print(f"Anzahl registrierter Schueler: {schueleranzahl}")
            return

        print(
            f"\n--- Letzte 20 Ergebnisse aus {os.path.basename(datenbankpfad)} ---\n"
        )

        tabellenkopf = (
            f"{'Vorname':<15} {'Nachname':<15} {'Klasse':<8} "
            f"{'Disziplin':<20} {'Wert':<10} {'Status':<10}"
        )
        print(tabellenkopf)
        print("-" * len(tabellenkopf))

        for ergebniszeile in ergebniszeilen:
            (
                vorname,
                nachname,
                klasse,
                klassenbuchstabe,
                disziplin,
                wert,
                status,
            ) = ergebniszeile

            # Leere Datenbankwerte werden für die Anzeige in harmlose Standardwerte umgewandelt.
            vorname = vorname or ""
            nachname = nachname or ""
            klassenanzeige = f"{klasse or ''}{klassenbuchstabe or ''}"
            disziplin = disziplin or ""
            wert_text = str(wert) if wert is not None else "-"
            status_text = status if status else "OK"

            print(
                f"{vorname:<15} {nachname:<15} {klassenanzeige:<8} "
                f"{disziplin:<20} {wert_text:<10} {status_text:<10}"
            )
    except sqlite3.Error as fehler:
        print(f"Datenbankfehler: {fehler}")
    except Exception as fehler:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {fehler}")
    finally:
        if "verbindung" in locals():
            verbindung.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Bitte gib den Namen oder Pfad der Datenbank ein.")
        print("Beispiele: 'BJS_2026_1.db' oder 'database/BJS_2026_1.db'")
        benutzer_eingabe = input("Datenbank: ").strip()

        if benutzer_eingabe:
            # Drag-and-drop in Terminals erzeugt oft Pfade mit Anführungszeichen.
            bereinigter_pfad = benutzer_eingabe.strip('"').strip("'")
            show_results(bereinigter_pfad)
        else:
            print("Keine Eingabe. Programm beendet.")
    else:
        show_results(sys.argv[1])
