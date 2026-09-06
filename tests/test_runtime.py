import socket

import pytest
from sqlalchemy.exc import OperationalError

from app import create_app
from app.config import ProductionConfig, TestingConfig
from app.extensions import db
from scripts.test_environment import configure_test_environment


@pytest.mark.parametrize("database_url", [
    "sqlite:///production.db",
    "postgresql://user:password@localhost/oceanblue",
    "",
])
def test_test_environment_rejects_non_test_database(monkeypatch, database_url):
    monkeypatch.setenv("TEST_DATABASE_URL", database_url)
    with pytest.raises(RuntimeError):
        configure_test_environment()


def test_testing_config_rejects_production_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost/oceanblue")
    with pytest.raises(RuntimeError, match="exclusivo"):
        TestingConfig.validate_runtime()


def test_production_requires_secrets(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.validate_runtime()


def test_production_rejects_short_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="Segredos fracos"):
        ProductionConfig.validate_runtime()


def test_test_app_preserves_csrf_and_disables_debug():
    app = create_app()
    assert app.testing
    assert not app.debug
    assert app.config["JWT_COOKIE_CSRF_PROTECT"]
    assert not app.config["FORCE_HTTPS"]


def test_external_network_is_blocked():
    with pytest.raises(RuntimeError, match="externa proibida"):
        socket.create_connection(("example.com", 443))


def test_health_and_readiness_on_migrated_postgresql():
    client = create_app().test_client()
    assert client.get("/api/health").json["status"] == "ok"
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json["database"] == "ok"


def test_readiness_fails_without_leaking_database_details(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("private-database-details"))

    monkeypatch.setattr(db.session, "execute", unavailable)
    response = create_app().test_client().get("/api/ready")
    assert response.status_code == 503
    assert response.json == {"status": "error", "database": "error"}
    assert b"private-database-details" not in response.data
