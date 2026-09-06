import os
from datetime import timedelta


class Config:
    ENV = os.getenv("FLASK_ENV", "development").lower()
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me-32-bytes-min")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "1800")),
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-dev-secret-change-me-32-bytes-min")
    FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "field-dev-secret-change-me-32-bytes-min")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_CSRF_IN_COOKIES = True
    JWT_CSRF_HEADER_NAME = "X-CSRF-TOKEN"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
    LOGIN_RATE_LIMIT_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5"))
    LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))
    FORCE_HTTPS = os.getenv("FORCE_HTTPS", "false").lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def validate_runtime():
        return


class DevelopmentConfig(Config):
    DEBUG = True
    JWT_COOKIE_CSRF_PROTECT = os.getenv("JWT_COOKIE_CSRF_PROTECT", "false").lower() in {"1", "true", "yes", "on"}


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    FORCE_HTTPS = False
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

    @staticmethod
    def validate_runtime():
        from sqlalchemy.engine import make_url

        database_url = make_url(os.environ.get("DATABASE_URL", ""))
        if database_url.get_backend_name() != "postgresql" or database_url.database != "oceanblue_test":
            raise RuntimeError("TestingConfig exige PostgreSQL exclusivo oceanblue_test.")


class ProductionConfig(Config):
    DEBUG = False
    JWT_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    FORCE_HTTPS = os.getenv("FORCE_HTTPS", "true").lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def validate_runtime():
        required = {
            "SECRET_KEY": os.getenv("SECRET_KEY"),
            "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
            "FIELD_ENCRYPTION_KEY": os.getenv("FIELD_ENCRYPTION_KEY"),
            "DATABASE_URL": os.getenv("DATABASE_URL"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError("Variaveis obrigatorias ausentes em producao: " + ", ".join(missing))

        weak = [
            name
            for name in ("SECRET_KEY", "JWT_SECRET_KEY", "FIELD_ENCRYPTION_KEY")
            if len(required[name] or "") < 32
        ]
        if weak:
            raise RuntimeError("Segredos fracos em producao. Use pelo menos 32 caracteres para: " + ", ".join(weak))

        if required["DATABASE_URL"].startswith("sqlite"):
            raise RuntimeError("SQLite nao deve ser usado em producao. Configure DATABASE_URL para Postgres.")


def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()

    if env == "testing":
        return TestingConfig

    if env == "production":
        return ProductionConfig

    return DevelopmentConfig
