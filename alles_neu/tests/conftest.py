import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Tuple

import pytest
from app import create_app
from app.database.database import Database


def _seed_sample_data(db: Database) -> None:
    """Seed a minimal dataset for integration/unit tests."""
    # Riegenführer
    rf_rows: Iterable[Tuple] = [
        ("Riege Alpha", "m", True, 5, "a"),
        ("Riege Beta", "w", False, 6, "b"),
    ]
    db.cursor.executemany(
        """
        INSERT INTO Riegenfuehrer (Name, Geschlecht, Profil, Stufe, Klassenendungen)
        VALUES (?, ?, ?, ?, ?)
        """,
        rf_rows,
    )
    db.connection.commit()

    # Fetch IDs for foreign keys
    db.cursor.execute("SELECT ID, Name FROM Riegenfuehrer ORDER BY ID")
    riegen = db.cursor.fetchall()
    riege_alpha_id = riegen[0][0]
    riege_beta_id = riegen[1][0]

    current_year = datetime.now().year
    students: Iterable[Tuple] = [
        (
            "Muster",  # Name
            "Max",  # Vorname
            "m",
            5,  # Klasse
            "a",
            current_year - 12,  # Geburtsjahr
            12,  # Bundesjugentspielalter
            True,  # Profil
            riege_alpha_id,  # RiegenfuehrerID
        ),
        (
            "Meyer",
            "Mia",
            "w",
            6,
            "b",
            current_year - 13,
            13,
            False,
            riege_beta_id,
        ),
    ]
    db.cursor.executemany(
        """
        INSERT INTO Schueler (
            Name, Vorname, Geschlecht, Klasse, Klassenbuchstabe,
            Geburtsjahr, Bundesjugentspielalter, Profil, RiegenfuehrerID,
            Gesamtpunktzahl, Note, Urkunde
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
        """,
        students,
    )
    db.connection.commit()


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory) -> str:
    db_file = tmp_path_factory.mktemp("data") / "test.db"
    return str(db_file)


@pytest.fixture(scope="function")
def app(test_db_path, monkeypatch):
    # Ensure we use testing config
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("TEST_DB_PATH", test_db_path)

    flask_app = create_app()
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="testing-secret",
        DB_PATH=test_db_path,
    )

    with flask_app.app_context():
        db = Database(path=test_db_path)
        _seed_sample_data(db)

    yield flask_app

    # Cleanup
    with flask_app.app_context():
        try:
            flask_app.get_db().close()
        except Exception:
            pass
    Path(test_db_path).unlink(missing_ok=True)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield app.get_db()
