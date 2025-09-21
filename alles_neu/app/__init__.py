from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dein_secret_key'

    # Blueprints importieren und registrieren
    from .routes.auth import auth_bp
    from .routes.input import input_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(input_bp)

    return app
