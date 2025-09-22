from flask import Flask, g
from .database.database import Database

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dein_secret_key'

    @app.teardown_appcontext
    def close_db(_exc=None):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    def get_db():
        if 'db' not in g:
            g.db = Database()
        return g.db
    
    app.get_db = get_db
    globals()['get_db'] = get_db

    # Blueprints importieren und registrieren
    from .routes.auth import auth_bp
    from .routes.input import input_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(input_bp)

    return app

def get_db():
    if 'db' not in g:
        g.db = Database()
    return g.db