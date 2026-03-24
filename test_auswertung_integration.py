from app.database.database import Database
from app.services_auswertung import AuswertungService


def test_auswertung_berechnet_gesamtpunkte_und_urkunden(tmp_path):
    db_path = tmp_path / "event.db"
    db = Database(path=str(db_path))

    maennlich_id = db.add_schueler(
        name="Mustermann",
        vorname="Max",
        geschlecht="m",
        klasse=8,
        klassenbuchstabe="a",
        geburtsjahr=2012,
        profil=False,
    )
    weiblich_id = db.add_schueler(
        name="Musterfrau",
        vorname="Mia",
        geschlecht="w",
        klasse=8,
        klassenbuchstabe="b",
        geburtsjahr=2012,
        profil=False,
    )
    unvollstaendig_id = db.add_schueler(
        name="Leer",
        vorname="Lena",
        geschlecht="w",
        klasse=8,
        klassenbuchstabe="c",
        geburtsjahr=2012,
        profil=False,
    )

    for disziplin, werte in {
        "sprint": (10.4, 10.1),
        "wurf": (31.0, 33.5),
        "lauf": (188.0, 182.0),
        "sprung": (4.55, 4.80),
    }.items():
        for runde, wert in enumerate(werte, start=1):
            db.add_entry(maennlich_id, disziplin, runde, wert, "OK", 1, 1)

    for disziplin, werte in {
        "sprint": (10.8, 10.5),
        "wurf": (24.0, 27.0),
        "lauf": (175.0, 170.0),
        "sprung": (4.10, 4.35),
    }.items():
        for runde, wert in enumerate(werte, start=1):
            db.add_entry(weiblich_id, disziplin, runde, wert, "OK", 1, 1)

    db.add_entry(unvollstaendig_id, "sprint", 1, 12.0, "OK", 1, 1)
    db.add_entry(unvollstaendig_id, "wurf", 1, 10.0, "OK", 1, 1)

    service = AuswertungService()
    result = service.evaluate_database(db, year=2026)

    assert result.total_students == 3
    assert result.evaluated_students == 2
    assert result.skipped_students == 1

    rows = db.cursor.execute(
        """
        SELECT SchuelerID, Gesamtpunktzahl, Urkunde
        FROM Schueler
        ORDER BY SchuelerID
        """
    ).fetchall()

    assert rows[0][0] == maennlich_id
    assert rows[0][1] is not None
    assert rows[0][2] in {"Siegerurkunde", "Ehrenurkunde"}

    assert rows[1][0] == weiblich_id
    assert rows[1][1] is not None
    assert rows[1][2] in {"Siegerurkunde", "Ehrenurkunde"}

    assert rows[2] == (unvollstaendig_id, None, None)

    summary = db.get_auswertung_summary()
    assert summary["total"] == 3
    assert summary["evaluated"] == 2
    assert summary["pending"] == 1

    ranking = db.get_gesamt_bestenliste(limit=5)
    assert len(ranking) == 2
    assert ranking[0]["gesamtpunktzahl"] >= ranking[1]["gesamtpunktzahl"]

    db.close()
