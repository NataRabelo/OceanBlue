import os
import re
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
    JWT_SIGNING_KEY_ID = os.getenv("JWT_SIGNING_KEY_ID", "primary")
    FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "field-dev-secret-change-me-32-bytes-min")
    FIELD_ENCRYPTION_KEYS = os.getenv("FIELD_ENCRYPTION_KEYS")
    FIELD_ENCRYPTION_ACTIVE_KEY_ID = os.getenv("FIELD_ENCRYPTION_ACTIVE_KEY_ID", "primary")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_CSRF_IN_COOKIES = True
    JWT_CSRF_HEADER_NAME = "X-CSRF-TOKEN"
    JWT_CSRF_CHECK_FORM = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
    OUTBOUND_ALLOWED_HOSTS = os.getenv("OUTBOUND_ALLOWED_HOSTS", "")
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
    SQLALCHEMY_ENGINE_OPTIONS = {**Config.SQLALCHEMY_ENGINE_OPTIONS,
        "pool_size": 5, "max_overflow": 5, "pool_timeout": 5,
        "connect_args": {"connect_timeout": 3, "options": "-c statement_timeout=10000 -c lock_timeout=3000"}}
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
        from app.security.secrets import load_field_keys, validate_secret
        for name in ("SECRET_KEY", "JWT_SECRET_KEY", "FIELD_ENCRYPTION_KEY"):
            validate_secret(name, required[name])
        if len(set(required[name] for name in ("SECRET_KEY", "JWT_SECRET_KEY", "FIELD_ENCRYPTION_KEY"))) != 3:
            raise RuntimeError("Os segredos de sessao, JWT e campos devem ser distintos.")
        keys, active_key = load_field_keys({
            **required,
            "FIELD_ENCRYPTION_KEYS": os.getenv("FIELD_ENCRYPTION_KEYS"),
            "FIELD_ENCRYPTION_ACTIVE_KEY_ID": os.getenv("FIELD_ENCRYPTION_ACTIVE_KEY_ID", "primary"),
        })
        if any(value in {required["SECRET_KEY"], required["JWT_SECRET_KEY"]} for value in keys.values()):
            raise RuntimeError("Chaves de campos nao podem reutilizar segredos de sessao/JWT.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", os.getenv("JWT_SIGNING_KEY_ID", "primary")):
            raise RuntimeError("Identificador da chave JWT invalido.")
        if int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5")) < 1 or int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300")) < 1:
            raise RuntimeError("Politica de tentativas invalida.")

        from sqlalchemy.engine import make_url
        from sqlalchemy.exc import ArgumentError

        try:
            database_url = make_url(required["DATABASE_URL"])
            if database_url.get_backend_name() != "postgresql":
                raise ValueError("Backend invalido")
        except (ArgumentError, ValueError):
            raise RuntimeError("DATABASE_URL deve ser uma URL PostgreSQL valida.") from None
        if os.getenv("FORCE_HTTPS", "true") != "true":
            raise RuntimeError("FORCE_HTTPS deve ser true em producao.")
        for flag in ("FEATURE_BOLETO", "FEATURE_FISCAL", "FEATURE_EXTERNAL_PROVIDERS"):
            if os.getenv(flag, "false") != "false":
                raise RuntimeError(f"{flag} bloqueada nesta versao de producao.")
        if os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"}:
            import ipaddress
            try:
                networks = [ipaddress.ip_network(value.strip()) for value in os.getenv("TRUSTED_PROXY_NETWORKS", "").split(",") if value.strip()]
                if not networks or any(network.prefixlen == 0 for network in networks):
                    raise ValueError()
            except ValueError:
                raise RuntimeError("Proxy exige redes de origem explicitas e restritas.") from None


def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()

    if env == "testing":
        return TestingConfig

    if env == "production":
        return ProductionConfig

    if env == "development":
        return DevelopmentConfig

    raise RuntimeError("FLASK_ENV invalido; use development, testing ou production.")
