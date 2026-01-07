import io

from app.db_registry import DbRegistry
from app.services_csv_import import import_students_csv_to_new_db
from app.services_riegen import auto_create_riegen_and_assign


def test_csv_import_creates_new_db_and_registry_entry(tmp_path):
    target_dir = tmp_path / "dbs"
    meta_path = tmp_path / "meta.db"

    csv_data = (
        "Geschlecht;Klasse;Name;Vorname;Geburtsjahr;Profil\n"
        "m;5a;Muster;Max;2014;true\n"
        "w;5a;Meyer;Mia;2014;false\n"
    )

    result = import_students_csv_to_new_db(
        csv_text=io.StringIO(csv_data),
        target_dir=target_dir,
        label="Test Event",
        delimiter=";",
        year=2026,
    )

    assert result.imported == 2
    assert result.errors == 0

    db_path = target_dir / result.db_name
    assert db_path.exists()

    registry = DbRegistry(meta_path)
    registry.register_db(path=result.db_path, name=result.db_name, label="Test Event", year=2026)

    dbs = registry.list_dbs()
    assert any(d.name == result.db_name for d in dbs)


def test_auto_riegen_assignment_with_profil(tmp_path):
    from app.database.database import Database

    db_path = tmp_path / "test.db"
    db = Database(path=str(db_path))

    # Klasse 5a: m/w, davon 1 Profil
    db.add_schueler(
        name="Muster",
        vorname="Max",
        geschlecht="m",
        klasse=5,
        klassenbuchstabe="a",
        geburtsjahr=2014,
        profil=True,
    )
    db.add_schueler(
        name="Meyer",
        vorname="Mia",
        geschlecht="w",
        klasse=5,
        klassenbuchstabe="a",
        geburtsjahr=2014,
        profil=False,
    )

    res = auto_create_riegen_and_assign(
        db=db, leader_names=["Leiter 1"], keep_existing_riegen=False
    )
    assert res.created_riegen == 3  # Profil + m + w

    stats = db.get_riegen_stats()
    assert stats["students_total"] == 2
    assert stats["students_assigned"] == 2
    assert stats["riegen_total"] == 3

    # Profil-Schüler muss zugewiesen sein
    db.cursor.execute(
        "SELECT COUNT(*) FROM Schueler WHERE Profil = 1 AND RiegenfuehrerID IS NOT NULL"
    )
    assert int(db.cursor.fetchone()[0] or 0) == 1


def test_registry_set_active(tmp_path):
    meta_path = tmp_path / "meta.db"
    registry = DbRegistry(meta_path)

    registry.set_active_db_path("/tmp/some.db")
    assert registry.get_active_db_path() == "/tmp/some.db"
