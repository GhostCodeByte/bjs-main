"""Startpunkt der Flask-Anwendung."""

from app import create_app
from flask import redirect, url_for

app = create_app()


@app.route("/")
def index():
    """Leitet die Wurzel-URL auf die Login-Seite weiter."""
    return redirect(url_for("auth.login"))


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
