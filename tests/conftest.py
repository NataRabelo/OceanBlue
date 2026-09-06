import socket

import pytest

from scripts.test_environment import configure_test_environment

configure_test_environment()

from app import create_app
from app.extensions import db
from app.security.rate_limit import LoginRateLimiter
from flask_migrate import upgrade


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    app = create_app()
    with app.app_context():
        upgrade()
        yield
        db.session.remove()
        db.engine.dispose()


@pytest.fixture(autouse=True)
def isolated_process_state(monkeypatch):
    LoginRateLimiter._attempts.clear()

    def deny_network(*args, **kwargs):
        raise RuntimeError("Conexao externa proibida nos testes; use um mock.")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    yield
    LoginRateLimiter._attempts.clear()
