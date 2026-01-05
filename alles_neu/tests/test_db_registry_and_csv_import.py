import io

from app.db_registry import DbRegistry
from app.services_csv_import import import_students_csv_to_new_db


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


def test_registry_set_active(tmp_path):
    meta_path = tmp_path / "meta.db"
    registry = DbRegistry(meta_path)

    registry.set_active_db_path("/tmp/some.db")
    assert registry.get_active_db_path() == "/tmp/some.db"
