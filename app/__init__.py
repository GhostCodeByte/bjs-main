"""App-Factory und Datenbankzugriff für die Flask-Anwendung."""

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, current_app, g
from flask_wtf.csrf import CSRFProtect, generate_csrf

from config import get_config

from .database.database import Database
from .db_registry import DbRegistry, default_meta_db_path

csrf = CSRFProtect()
load_dotenv()


def create_app():
    """Erzeugt und konfiguriert die Flask-Anwendung samt Blueprints."""
    konfigurationsklasse = get_config()
    app = Flask(__name__)
    app.config.from_object(konfigurationsklasse)
    csrf.init_app(app)

    @app.teardown_appcontext
    def close_db(_exc=None):
        """Schließt die pro Request gecachte Datenbankverbindung."""
        datenbank = g.pop("db", None)
        if datenbank is not None:
            datenbank.close()

    def get_db():
        """Lädt die aktuell aktive Event-Datenbank aus der Registry."""
        if "db" not in g:
            registry = DbRegistry(
                default_meta_db_path(Path(app.root_path).parent)
            )
            aktive_datenbank = registry.get_active_db_path()
            # Es wird bewusst nur die in der Registry gewählte Event-Datenbank verwendet.
            datenbankpfad = aktive_datenbank
            g.db = Database(path=datenbankpfad) if datenbankpfad else None
        return g.db

    # Die Modul-Funktion `get_db()` soll innerhalb anderer Module auf dieselbe Logik zeigen.
    globals()["get_db"] = get_db

    @app.context_processor
    def inject_csrf_token():
        """Stellt das CSRF-Token global für Jinja-Templates bereit."""
        return {"csrf_token": generate_csrf}

    # Blueprints werden erst hier importiert, damit die App vorher vollständig konfiguriert ist.
    from .routes.auth import auth_bp
    from .routes.input import input_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(input_bp)

    return app


def get_db():
    """Liefert die aktuell aktive Event-Datenbank im Flask-Request-Kontext."""
    if "db" not in g:
        registry = DbRegistry(
            default_meta_db_path(Path(current_app.root_path).parent)
        )
        aktive_datenbank = registry.get_active_db_path()
        # Es gibt absichtlich keinen Fallback auf eine Standarddatenbank.
        datenbankpfad = aktive_datenbank
        g.db = Database(path=datenbankpfad) if datenbankpfad else None
    return g.db
