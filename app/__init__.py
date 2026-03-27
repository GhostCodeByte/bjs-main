"""App-Factory und Datenbankzugriff fuer die Flask-Anwendung."""

import logging
from http import HTTPStatus
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, current_app, g, jsonify, request
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from app.core.settings import get_config

from .database.database import Database
from .core.registry import DbRegistry, default_meta_db_path

csrf = CSRFProtect()
load_dotenv()


def _build_theme_css_vars(theme: dict[str, str] | None) -> str:
    """Wandelt Theme-Werte aus der App-Konfiguration in CSS-Variablen um."""
    if not theme:
        return ""
    return "; ".join(f"--{key}: {value}" for key, value in theme.items())


def _configure_logging(app: Flask) -> None:
    """Initialisiert eine einfache Logging-Konfiguration fuer App und Gunicorn."""
    log_level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )

    app.logger.setLevel(log_level)


def _is_production(app: Flask) -> bool:
    """Prueft, ob die App im Produktionsmodus laeuft."""
    return str(app.config.get("ENV_NAME", "")).lower() == "production"


def _validate_production_config(app: Flask) -> None:
    """Blockiert unsichere Produktionsstarts mit klaren Fehlermeldungen."""
    if not _is_production(app):
        return

    fehler: list[str] = []
    if app.config.get("SECRET_KEY") in {None, "", "change-me"}:
        fehler.append("SECRET_KEY muss in Produktion gesetzt sein und darf nicht 'change-me' sein.")
    if app.config.get("ADMIN_PASSWORD") in {None, "", "admin123"}:
        fehler.append("ADMIN_PASSWORD muss in Produktion gesetzt sein und darf nicht 'admin123' sein.")
    if app.config.get("STATION_DEFAULT_PIN"):
        fehler.append("STATION_DEFAULT_PIN darf in Produktion nicht gesetzt sein.")
    if app.config.get("SESSION_COOKIE_SECURE") and app.config.get("PREFERRED_URL_SCHEME") != "https":
        fehler.append("PREFERRED_URL_SCHEME muss 'https' sein, wenn SESSION_COOKIE_SECURE aktiviert ist.")

    if fehler:
        raise RuntimeError("Produktionskonfiguration ungueltig:\n- " + "\n- ".join(fehler))


def _register_error_handlers(app: Flask) -> None:
    """Registriert produktionsfreundliche Fehlerbehandlung fuer Uploads und CSRF."""

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(_error):
        """Antwortet bei zu grossen Uploads mit HTML oder JSON."""
        nachricht = "Upload zu gross. Bitte eine kleinere Datei verwenden."
        app.logger.warning("Upload wegen MAX_CONTENT_LENGTH abgewiesen: path=%s", request.path)
        if request.is_json:
            return jsonify({"error": nachricht}), HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        return nachricht, HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        """Antwortet bei CSRF-Problemen mit HTML oder JSON."""
        nachricht = f"CSRF-Fehler: {error.description}"
        app.logger.warning("CSRF-Fehler auf %s", request.path)
        if request.is_json:
            return jsonify({"error": nachricht}), HTTPStatus.BAD_REQUEST
        return nachricht, HTTPStatus.BAD_REQUEST


def create_app():
    """Erzeugt und konfiguriert die Flask-Anwendung samt Blueprints."""
    konfigurationsklasse = get_config()
    app = Flask(__name__)
    app.config.from_object(konfigurationsklasse)

    _configure_logging(app)
    _validate_production_config(app)

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    csrf.init_app(app)
    _register_error_handlers(app)

    @app.teardown_appcontext
    def close_db(_exc=None):
        """Schliesst die pro Request gecachte Datenbankverbindung."""
        datenbank = g.pop("db", None)
        if datenbank is not None:
            datenbank.close()

    def _resolve_active_db_path() -> str | None:
        """Liefert die aktive DB oder waehlte automatisch die neueste fuer das aktuelle Jahr."""
        registry = DbRegistry(default_meta_db_path(Path(app.root_path).parent))
        aktive_datenbank = registry.get_active_db_path()
        if aktive_datenbank and Path(aktive_datenbank).exists():
            return aktive_datenbank
        if aktive_datenbank:
            app.logger.warning(
                "Gespeicherter DB-Pfad ist ungueltig und wird ignoriert: %s",
                aktive_datenbank,
            )

        aktuelle_jahres_db = registry.find_latest_db_for_year(datetime.now().year)
        if aktuelle_jahres_db:
            registry.set_active_db_path(aktuelle_jahres_db.path)
            return aktuelle_jahres_db.path
        return None

    def get_db():
        """Laedt die aktuell aktive Event-Datenbank aus der Registry."""
        if "db" not in g:
            datenbankpfad = _resolve_active_db_path()
            g.db = Database(path=datenbankpfad) if datenbankpfad else None
            if datenbankpfad is None:
                app.logger.info("Keine aktive Event-Datenbank gesetzt.")
        return g.db

    globals()["get_db"] = get_db

    @app.context_processor
    def inject_csrf_token():
        """Stellt globale Template-Helfer fuer CSRF und UI-Theme bereit."""
        theme = dict(app.config.get("UI_THEME_COLORS", {}))
        return {
            "csrf_token": generate_csrf,
            "ui_theme_colors": theme,
            "ui_theme_css_vars": _build_theme_css_vars(theme),
        }

    from .routes.auth import auth_bp
    from .routes.input import input_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(input_bp)

    return app


def get_db():
    """Liefert die aktuell aktive Event-Datenbank im Flask-Request-Kontext."""
    if "db" not in g:
        registry = DbRegistry(default_meta_db_path(Path(current_app.root_path).parent))
        aktive_datenbank = registry.get_active_db_path()
        datenbankpfad = aktive_datenbank
        if (not datenbankpfad or not Path(datenbankpfad).exists()):
            if aktive_datenbank:
                current_app.logger.warning(
                    "Gespeicherter DB-Pfad ist ungueltig und wird ignoriert: %s",
                    aktive_datenbank,
                )
            datenbankpfad = None
            aktuelle_jahres_db = registry.find_latest_db_for_year(datetime.now().year)
            if aktuelle_jahres_db:
                registry.set_active_db_path(aktuelle_jahres_db.path)
                datenbankpfad = aktuelle_jahres_db.path
        g.db = Database(path=datenbankpfad) if datenbankpfad else None
        if datenbankpfad is None:
            current_app.logger.info("Keine aktive Event-Datenbank gesetzt.")
    return g.db
