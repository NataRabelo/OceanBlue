import os

from sqlalchemy.engine import make_url


def configure_test_environment():
    database_url = os.environ.get("TEST_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL obrigatoria; use o PostgreSQL isolado de compose.test.yml.")
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql" or parsed.database != "oceanblue_test":
        raise RuntimeError("Testes exigem PostgreSQL com banco exclusivo oceanblue_test.")
    os.environ.update({
        "FLASK_ENV": "testing",
        "FLASK_DEBUG": "0",
        "FLASK_SKIP_DOTENV": "1",
        "DATABASE_URL": database_url,
        "SECRET_KEY": "test-only-session-secret-32-characters",
        "JWT_SECRET_KEY": "test-only-jwt-secret-32-characters",
        "FIELD_ENCRYPTION_KEY": "test-only-field-secret-32-characters",
        "FORCE_HTTPS": "false",
        "TRUST_PROXY_HEADERS": "false",
        "LOGIN_RATE_LIMIT_ATTEMPTS": "5",
        "LOGIN_RATE_LIMIT_WINDOW_SECONDS": "300",
    })
