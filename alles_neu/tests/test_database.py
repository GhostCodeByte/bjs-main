import os
from pathlib import Path

import pytest
from app.database.database import Database


def _get_single_student(db: Database):
    db.cursor.execute("SELECT SchuelerID FROM Schueler ORDER BY SchuelerID LIMIT 1")
    row = db.cursor.fetchone()
    assert row, "Testdaten müssen einen Schüler enthalten"
    return row[0]


def test_add_entry_and_rounds_ok(db: Database):
    schueler_id = _get_single_student(db)
    db.add_entry(
        schueler_id=schueler_id,
        disziplin="Sprinten",
        ergebnis_nr=1,
        result_value=12.5,
        status="OK",
        source_ipad_number=1,
        source_station="A",
    )
    rounds = db.get_rounds_done(schueler_id, "Sprinten")
    assert rounds == [(1, 12.5)]


def test_add_entry_absent_overrides_round(db: Database):
    schueler_id = _get_single_student(db)
    # Zuerst OK, dann Abwesend für gleiche Runde
    db.add_entry(
        schueler_id=schueler_id,
        disziplin="Sprinten",
        ergebnis_nr=2,
        result_value=13.1,
        status="OK",
        source_ipad_number=1,
        source_station="A",
    )
    db.add_entry(
        schueler_id=schueler_id,
        disziplin="Sprinten",
        ergebnis_nr=2,
        result_value=None,
        status="ABWESEND",
        source_ipad_number=1,
        source_station="A",
    )
    rounds = db.get_rounds_done(schueler_id, "Sprinten")
    assert rounds == [(2, "ABWESEND")]


def test_get_rounds_done_returns_latest_only(db: Database):
    schueler_id = _get_single_student(db)
    db.add_entry(
        schueler_id=schueler_id,
        disziplin="Sprinten",
        ergebnis_nr=3,
        result_value=15.0,
        status="OK",
        source_ipad_number=1,
        source_station="A",
    )
    db.add_entry(
        schueler_id=schueler_id,
        disziplin="Sprinten",
        ergebnis_nr=3,
        result_value=14.8,
        status="OK",
        source_ipad_number=1,
        source_station="A",
    )
    rounds = db.get_rounds_done(schueler_id, "Sprinten")
    assert rounds == [(3, 14.8)]


def test_generate_station_pin_is_unique(db: Database):
    pin1 = db.generate_station_pin(station="S1", max_logins=1, length=4)
    pin2 = db.generate_station_pin(station="S2", max_logins=1, length=4)
    assert pin1 != pin2
    # Pins are stored
    row = db.cursor.execute(
        "SELECT COUNT(*) FROM Station_Pin WHERE pin IN (?, ?)", (pin1, pin2)
    ).fetchone()
    assert row[0] == 2


def test_claim_station_pin_single_session_policy(db: Database):
    pin = db.generate_station_pin(station="TestStation", max_logins=1, length=6)
    ok, msg = db.claim_station_pin(pin=pin, device_id="dev-1")
    assert ok and msg == "OK"

    # zweites Gerät darf nicht gleichzeitig
    ok2, msg2 = db.claim_station_pin(pin=pin, device_id="dev-2")
    assert not ok2
    assert "anderes Gerät" in msg2

    # gleiches Gerät erneut erlaubt (idempotent)
    ok3, msg3 = db.claim_station_pin(pin=pin, device_id="dev-1")
    assert ok3 and msg3 == "OK"


def test_backup_to_file_creates_file_and_history(db: Database, tmp_path: Path):
    target = tmp_path / "backup.db"
    assert not target.exists()
    path = db.backup_to_file(target_path=str(target), backup_type="manual")
    assert path == str(target)
    assert target.exists()
    # History entry
    rows = db.cursor.execute(
        "SELECT file_path, backup_type FROM Backup_History"
    ).fetchall()
    assert any(r[0] == str(target) and r[1] == "manual" for r in rows)


def test_get_stats_counts_entries(db: Database):
    schueler_id = _get_single_student(db)
    db.add_entry(
        schueler_id=schueler_id,
        disziplin="Sprinten",
        ergebnis_nr=1,
        result_value=11.5,
        status="OK",
        source_ipad_number=1,
        source_station="A",
    )
    stats = db.get_stats()
    assert stats["total_schueler"] >= 1
    assert stats["total_riegen"] >= 1
    assert stats["total_ergebnisse"] >= 1
    assert stats["active_sessions"] >= 0
