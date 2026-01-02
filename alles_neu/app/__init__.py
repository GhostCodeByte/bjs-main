from config import get_config
from dotenv import load_dotenv
from flask import Flask, current_app, g
from flask_wtf.csrf import CSRFProtect, generate_csrf

from .database.database import Database

csrf = CSRFProtect()
load_dotenv()


def create_app():
    config_cls = get_config()
    app = Flask(__name__)
    app.config.from_object(config_cls)
    csrf.init_app(app)

    @app.teardown_appcontext
    def close_db(_exc=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def get_db():
        if "db" not in g:
            db_path = app.config.get("DB_PATH")
            g.db = Database(path=db_path)
        return g.db

    app.get_db = get_db
    globals()["get_db"] = get_db

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": generate_csrf}

    # Blueprints importieren und registrieren
    from .routes.auth import auth_bp
    from .routes.input import input_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(input_bp)

    return app


def get_db():
    if "db" not in g:
        db_path = current_app.config.get("DB_PATH")
        g.db = Database(path=db_path)
    return g.db
