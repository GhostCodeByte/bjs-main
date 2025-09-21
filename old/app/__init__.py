from flask import Flask
from flask_session import Session
#import backend.backend as backend
import os

# Projektwurzel (Elternverzeichnis) bestimmen
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__,
           template_folder=os.path.join(project_root, 'frontend', 'templates'),
           static_folder=os.path.join(project_root, 'frontend', 'static'))
app.secret_key = 'supersecretkey'  # Geheimschlüssel für Sessions (in Produktion per Umgebungsvariable setzen)
app.config['SESSION_TYPE'] = 'filesystem'  # Serverseitige Sitzungen im Dateisystem speichern
app.config['SESSION_FILE_DIR'] = os.path.join(project_root, 'flask_session')  # Verzeichnis für Session-Dateien
Session(app)

# Pfad zur SQLite-Datenbank
DB_PATH = os.path.join(project_root, "backend", "database", "bjs.db")

def get_db_path():
    """Gibt den absoluten Pfad zur SQLite-Datenbank zurück"""
    return DB_PATH

# Blueprints importieren und registrieren
from app.routes.auth import auth_bp
from app.routes.schueler import schueler_bp
from app.routes.riegen import riegen_bp
from app.routes.debug import debug_bp

app.register_blueprint(auth_bp)
app.register_blueprint(schueler_bp)
app.register_blueprint(riegen_bp)
app.register_blueprint(debug_bp)

# App-Instanz für main.py exportieren
__all__ = ["app"]
