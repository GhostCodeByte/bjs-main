"""Zentrale Konfigurationen fuer Entwicklungs-, Test- und Produktivbetrieb."""

import os
from datetime import timedelta
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    """Wandelt typische Umgebungswerte in bool um."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "ja", "on"}


class BaseConfig:
    ENV_NAME = "development"
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    DB_PATH = os.getenv(
        "DB_PATH"
    )  # Bleibt leer, bis ein CSV-Import eine Datenbank erzeugt.
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    EVENT_PASSWORD = os.getenv("EVENT_PASSWORD")
    STATION_DEFAULT_PIN = os.getenv("STATION_DEFAULT_PIN")
    STATION_DEFAULT_NAME = os.getenv("STATION_DEFAULT_NAME", "Station")
    STATION_DEFAULT_MAX_LOGINS = int(os.getenv("STATION_DEFAULT_MAX_LOGINS", "1"))
    STATION_DEFAULT_PIN_LENGTH = int(os.getenv("STATION_DEFAULT_PIN_LENGTH", "6"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    TRUST_PROXY = _as_bool(os.getenv("TRUST_PROXY"), default=False)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    UI_THEME_COLORS = {
        "bg": "#F5F3F5",
        "panel": "#F5F3F5",
        "panel-muted": "#F5F3F5",
        "border": "#C9CECB",
        "border-strong": "#A9B0AB",
        "text": "#080708",
        "muted": "#5B615D",
        "primary": "#3772FF",
        "primary-hover": "#275DE0",
        "primary-soft": "rgba(55, 114, 255, 0.12)",
        "success": "#3772FF",
        "success-soft": "rgba(55, 114, 255, 0.12)",
        "success-contrast": "#1F4DBA",
        "success-border": "rgba(55, 114, 255, 0.28)",
        "danger": "#DF2935",
        "danger-hover": "#C61E2A",
        "danger-soft": "rgba(223, 41, 53, 0.12)",
        "danger-contrast": "#A51B24",
        "danger-border": "rgba(223, 41, 53, 0.26)",
        "warning": "#FDCA40",
        "warning-soft": "rgba(253, 202, 64, 0.22)",
        "warning-contrast": "#6F5600",
        "warning-border": "rgba(253, 202, 64, 0.42)",
        "header-bg": "#080708",
        "header-text": "#F5F3F5",
        "header-border": "#080708",
        "toast-bg": "#080708",
        "toast-info": "#3772FF",
        "toast-info-border": "#275DE0",
        "focus-ring": "rgba(55, 114, 255, 0.18)",
        "shadow-sm": "rgba(8, 7, 8, 0.08)",
        "shadow": "rgba(8, 7, 8, 0.14)",
        "bg-rgb": "245, 243, 245",
        "panel-rgb": "245, 243, 245",
        "primary-rgb": "55, 114, 255",
        "danger-rgb": "223, 41, 53",
        "warning-rgb": "253, 202, 64",
    }

    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # Wird in Produktion normalerweise auf True gesetzt.
    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "http")

    DEBUG = False
    TESTING = False

    @classmethod
    def ensure_paths(cls) -> None:
        """Erzeugt das Zielverzeichnis der Datenbank, falls ein Pfad gesetzt ist."""
        if cls.DB_PATH:
            Path(cls.DB_PATH).parent.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    DB_PATH = os.getenv("TEST_DB_PATH", "database/test.db")


CONFIG_MAP: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
}


def get_config(env_name: str | None = None) -> type[BaseConfig]:
    """Liefert die passende Konfigurationsklasse anhand der Umgebung."""
    umgebungsname = (
        env_name or os.getenv("ENV") or os.getenv("FLASK_ENV") or ""
    ).lower()
    konfigurationsklasse = CONFIG_MAP.get(umgebungsname, DevelopmentConfig)
    konfigurationsklasse.ensure_paths()
    return konfigurationsklasse
