import io
import json
import logging
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from flask import Flask, g, request

from app.health import healthcheck, readiness
from app.operations import OperationalFormatter, register_operations, storage_probe
from app.security.headers import register_security_headers
from app.security.proxy import TrustedProxy


PRIVATE = "senha=S06_PRIVATE;cpf=529.982.247-25;cartao=4111111111111111;Bearer S06_SECRET"
HEALTH_PATHS = ("/health", "/readiness", "/api/health", "/api/ready")


@pytest.fixture
def operational_app(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.config.update(TESTING=True, FORCE_HTTPS=True, JWT_COOKIE_SECURE=True)
    register_operations(app)
    register_security_headers(app)
    for path in HEALTH_PATHS:
        app.add_url_rule(path, path, healthcheck if "health" in path else readiness)
    app.add_url_rule("/login", "login", lambda: "ok", methods=["GET", "POST"])
    app.add_url_rule("/item/<path:value>", "item", lambda value: "ok", methods=["GET", "POST"])
    return app


@pytest.fixture
def operational_logs(operational_app):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(OperationalFormatter())
    previous_level = operational_app.logger.level
    operational_app.logger.addHandler(handler)
    operational_app.logger.setLevel(logging.INFO)
    yield stream
    operational_app.logger.removeHandler(handler)
    operational_app.logger.setLevel(previous_level)


@pytest.mark.parametrize("path", HEALTH_PATHS)
@pytest.mark.parametrize("forwarded", ["127.0.0.1", "::1", "203.0.113.9, 127.0.0.1"])
def test_forwarded_loopback_cannot_unlock_http_health(operational_app, path, forwarded):
    operational_app.wsgi_app = TrustedProxy(operational_app.wsgi_app, "10.33.0.2/32")
    response = operational_app.test_client().get(path,
        headers={"X-Forwarded-For": forwarded, "X-Forwarded-Proto": "http"},
        environ_overrides={"REMOTE_ADDR": "10.33.0.2"})
    assert response.status_code == 403


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_direct_loopback_health_stays_available(operational_app, peer):
    operational_app.wsgi_app = TrustedProxy(operational_app.wsgi_app, "10.33.0.2/32")
    response = operational_app.test_client().get("/health", environ_overrides={"REMOTE_ADDR": peer})
    assert response.status_code == 200
    assert operational_app.test_client().get("/login", environ_overrides={"REMOTE_ADDR": peer}).status_code == 403


@pytest.mark.parametrize("peer", ["203.0.113.9", "not-an-ip", ""])
def test_untrusted_peer_cannot_promote_scheme_or_host(operational_app, peer):
    operational_app.wsgi_app = TrustedProxy(operational_app.wsgi_app, "10.33.0.2/32")
    response = operational_app.test_client().get("/login", headers={
        "X-Forwarded-For": "127.0.0.1", "X-Forwarded-Proto": "https",
        "X-Forwarded-Host": "evil.invalid", "Forwarded": "for=127.0.0.1;proto=https"},
        environ_overrides={"REMOTE_ADDR": peer})
    assert response.status_code == 403


def test_trusted_proxy_uses_last_hop_without_forwarded_host(operational_app):
    operational_app.add_url_rule("/transport", "transport", lambda: {
        "peer": request.remote_addr, "scheme": request.scheme, "host": request.host,
        "prefix": request.script_root})
    operational_app.wsgi_app = TrustedProxy(operational_app.wsgi_app, "10.33.0.2/32")
    response = operational_app.test_client().get("/transport", headers={
        "X-Forwarded-For": "127.0.0.1, 203.0.113.9", "X-Forwarded-Proto": "http, https",
        "X-Forwarded-Host": "evil.invalid", "X-Forwarded-Port": "9999", "X-Forwarded-Prefix": "/evil"},
        environ_overrides={"REMOTE_ADDR": "10.33.0.2"})
    assert response.status_code == 200
    assert response.json == {"peer": "203.0.113.9", "scheme": "https", "host": "localhost", "prefix": ""}


@pytest.mark.parametrize("authorization", ["Bearer senh\u00e3", "Bearer \u2603", "Bearer " + "x" * 8192],
    ids=["latin1", "unicode", "oversized"])
def test_metrics_invalid_authorization_fails_closed(operational_app, monkeypatch, authorization):
    monkeypatch.setenv("METRICS_TOKEN", "s06-metrics-private-token-32-characters")
    response = operational_app.test_client().get("/metrics", base_url="https://localhost",
        headers={"Authorization": authorization})
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("token", ["", "short", "\u2603" * 32], ids=["empty", "short", "unicode"])
def test_metrics_unusable_token_fails_closed(operational_app, monkeypatch, token):
    monkeypatch.setenv("METRICS_TOKEN", token)
    response = operational_app.test_client().get("/metrics", base_url="https://localhost",
        headers={"Authorization": "Bearer " + token})
    assert response.status_code == 404


def test_metrics_first_scrape_includes_zero_counters(operational_app, monkeypatch):
    token = "s06-metrics-private-token-32-characters"
    monkeypatch.setenv("METRICS_TOKEN", token)
    response = operational_app.test_client().get("/metrics", base_url="https://localhost",
        headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    values = dict(line.split() for line in response.text.splitlines())
    for name in ("requests_total", "errors_total", "slow_requests_total", "duration_seconds_total"):
        assert float(values["oceanblue_" + name]) == 0
    assert response.headers["Cache-Control"] == "no-store"
    assert token not in response.text


@pytest.mark.parametrize("field", ["event", "request_id", "route", "method", "status", "duration_ms"])
def test_structured_log_fields_cannot_smuggle_secrets(field):
    record = logging.LogRecord("app", logging.ERROR, "", 0, {field: PRIVATE}, (), None)
    formatted = OperationalFormatter().format(record)
    assert PRIVATE not in formatted
    assert "S06_PRIVATE" not in formatted
    assert "529.982.247-25" not in formatted
    assert "4111111111111111" not in formatted
    assert isinstance(json.loads(formatted), dict)


@pytest.mark.parametrize("value", [{"password": PRIVATE}, object(), float("nan"), float("inf")])
def test_structured_log_invalid_values_do_not_break_json(value):
    record = logging.LogRecord("app", logging.INFO, "", 0, {"event": value, "duration_ms": value}, (), None)
    formatted = OperationalFormatter().format(record)
    assert "S06_PRIVATE" not in formatted
    assert "NaN" not in formatted and "Infinity" not in formatted
    json.loads(formatted)


def test_http_log_method_and_request_id_injection(operational_app, operational_logs):
    response = operational_app.test_client().open("/health", base_url="https://localhost",
        environ_overrides={"REQUEST_METHOD": "S06_PRIVATE", "HTTP_X_REQUEST_ID": 'bad\r\n{"event":"forged"}'})
    assert response.status_code == 405
    assert re.fullmatch(r"[a-f0-9]{32}", response.headers["X-Request-ID"])
    lines = operational_logs.getvalue().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert "S06_PRIVATE" not in lines[0] and "forged" not in lines[0]


def test_http_logs_only_route_template_and_preserves_correlation(operational_app, operational_logs):
    supplied = "abcdef0123456789" * 2
    response = operational_app.test_client().post("/item/529.982.247-25?senha=S06_PRIVATE",
        base_url="https://localhost", json={"password": PRIVATE, "card": "4111111111111111"},
        headers={"Authorization": "Bearer S06_SECRET", "X-Request-ID": supplied,
            "Cookie": "password=S06_PRIVATE"})
    payload = json.loads(operational_logs.getvalue())
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == payload["request_id"] == supplied
    assert payload["route"] == "/item/<path:value>"
    assert payload["method"] == "POST" and payload["status"] == 200
    for secret in ("S06_PRIVATE", "529.982.247-25", "4111111111111111", "S06_SECRET"):
        assert secret not in operational_logs.getvalue()


def test_exception_text_and_traceback_are_not_logged():
    try:
        raise RuntimeError(PRIVATE + '\n{"event":"forged"}')
    except RuntimeError as error:
        record = logging.LogRecord("app", logging.ERROR, "", 0, PRIVATE, (),
            (type(error), error, error.__traceback__))
    payload = json.loads(OperationalFormatter().format(record))
    assert payload["error_type"] == "RuntimeError"
    assert "S06_PRIVATE" not in json.dumps(payload) and "forged" not in json.dumps(payload)


def test_correlation_survives_earlier_request_gate(operational_app, operational_logs):
    operational_app.before_request_funcs[None].insert(0, lambda: ("denied", 403))
    with operational_app.app_context():
        response = operational_app.test_client().get("/health")
        payload = json.loads(operational_logs.getvalue())
        assert response.status_code == 403
        assert payload["request_id"] == response.headers["X-Request-ID"] == g.request_id
        counters, _ = operational_app.extensions["operational_metrics"]
        assert counters["duration_seconds_total"] >= 0


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_responses_are_not_cacheable(operational_app, monkeypatch, path):
    session = Mock()
    session.execute.return_value.scalar_one.return_value = operational_app.config["SCHEMA_REVISION"]
    monkeypatch.setattr("app.health.db", Mock(session=session))
    response = operational_app.test_client().get(path, base_url="https://localhost")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_dependency_failures_keep_health_alive_and_hide_details(operational_app, operational_logs, monkeypatch):
    session = Mock()
    session.execute.side_effect = RuntimeError(PRIVATE)
    monkeypatch.setattr("app.health.db", Mock(session=session))
    client = operational_app.test_client()
    assert client.get("/health", base_url="https://localhost").status_code == 200
    assert not session.execute.called
    response = client.get("/readiness", base_url="https://localhost")
    assert response.status_code == 503
    assert response.json == {"status": "error", "database": "error"}
    session.rollback.assert_called_once()
    assert "S06_PRIVATE" not in response.text + operational_logs.getvalue()


def test_storage_short_write_fails_readiness_and_cleans_probe(operational_app, monkeypatch):
    monkeypatch.setattr("app.operations.os.write", lambda descriptor, data: len(data) - 1)
    with operational_app.app_context(), pytest.raises(OSError):
        storage_probe()
    assert not list(Path(operational_app.config["STORAGE_ROOT"]).iterdir())


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_storage_failure_blocks_mutation_but_not_health(operational_app, monkeypatch, method):
    operational_app.testing = False
    probe = Mock(side_effect=OSError(PRIVATE))
    monkeypatch.setattr("app.operations.storage_probe", probe)
    response = operational_app.test_client().open("/login", method=method, base_url="https://localhost")
    assert response.status_code == 503
    assert "S06_PRIVATE" not in response.text
    assert operational_app.test_client().get("/health", base_url="https://localhost").status_code == 200
