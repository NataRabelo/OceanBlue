import socket
import json
from pathlib import Path
from threading import Lock

import pytest

from scripts.test_environment import configure_test_environment

configure_test_environment()

from app import create_app
from app.extensions import db
from flask_migrate import upgrade
from flask import Flask, request as flask_request


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    app = create_app()
    with app.app_context():
        upgrade()
        db.session.remove()
        db.engine.dispose()
    yield


@pytest.fixture(autouse=True)
def isolated_process_state(monkeypatch):
    def deny_network(*args, **kwargs):
        raise RuntimeError("Conexao externa proibida nos testes; use um mock.")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    yield


@pytest.fixture(scope="session")
def observed_http_routes():
    observations = set()
    lock = Lock()
    yield observations, lock
    destination = Path("/tmp/http-route-coverage.json")
    destination.write_text(json.dumps({"scope": "Observed in-process Flask requests only; browser subprocesses are recorded by their E2E evidence.",
        "observations": [{"test": test, "endpoint": endpoint, "method": method, "status": status}
            for test, endpoint, method, status in sorted(observations)]}, indent=2), encoding="utf-8")


@pytest.fixture(autouse=True)
def record_http_routes(monkeypatch, request, observed_http_routes):
    original = Flask.full_dispatch_request
    observations, lock = observed_http_routes

    def dispatch(application):
        response = original(application)
        if flask_request.endpoint:
            with lock:
                observations.add((request.node.nodeid, flask_request.endpoint, flask_request.method, response.status_code))
        return response

    monkeypatch.setattr(Flask, "full_dispatch_request", dispatch)
