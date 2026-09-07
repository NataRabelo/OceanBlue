import json
import logging
import time
from pathlib import Path

import pytest
from sqlalchemy import event, text

from app import create_app
from app.extensions import db
from app.models.db import AuditLog, Permission, RolePermission
from app.operations import OperationalFormatter, storage_probe
from app.security.proxy import TrustedProxy
from app.services.audit_service import AuditService
from tests.test_sprint02_security import security_app, login
from tests.test_startup import run_startup


@pytest.mark.parametrize("flag", ["FEATURE_BOLETO", "FEATURE_FISCAL", "FEATURE_EXTERNAL_PROVIDERS"])
@pytest.mark.parametrize("value", ["true", "garbage"])
def test_production_flags_fail_closed(flag, value):
    result = run_startup({flag: value})
    assert result.returncode != 0 and "bloqueada" in result.stderr


@pytest.mark.parametrize("overrides", [{"FORCE_HTTPS": "false"}, {"TRUST_PROXY_HEADERS": "true"},
    {"TRUST_PROXY_HEADERS": "true", "TRUSTED_PROXY_NETWORKS": "0.0.0.0/0"}])
def test_unsafe_transport_configuration_rejected(overrides):
    assert run_startup(overrides).returncode != 0


@pytest.mark.parametrize("peer,secure", [("10.33.0.2", True), ("10.34.0.2", False)])
def test_proxy_trusts_only_transport_peer(peer, secure):
    app = create_app()
    app.wsgi_app = TrustedProxy(app.wsgi_app, "10.33.0.2/32")
    app.config["FORCE_HTTPS"] = True
    response = app.test_client().get("/health", headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "203.0.113.1"}, environ_overrides={"REMOTE_ADDR": peer})
    assert response.status_code == (200 if secure else 403)


def test_storage_readiness_and_write_failure_closed(tmp_path):
    app = create_app()
    app.config["STORAGE_ROOT"] = str(tmp_path / "missing")
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/readiness").status_code == 503
    app.testing = False
    assert client.post("/login").status_code == 503
    assert not list(tmp_path.iterdir())


def test_readiness_refuses_stale_schema(security_app):
    with security_app.app_context():
        db.session.execute(text("UPDATE alembic_version SET version_num='stale'"))
        db.session.commit()
    try:
        client = security_app.test_client()
        assert client.get("/health").status_code == 200
        assert client.get("/readiness").status_code == 503
    finally:
        with security_app.app_context():
            db.session.execute(text("UPDATE alembic_version SET version_num='a0d1e2f3a4b5'"))
            db.session.commit()


def test_production_ui_and_payment_lookup_hide_blocked_modules(security_app):
    from app.models.db import FormaPagamento
    from app.repositorys.pdv_repository import PdvRepository
    from app.services.tenant_bootstrap_service import TenantBootstrapService
    client = security_app.test_client()
    login(client)
    security_app.testing = False
    security_app.config.update(FEATURE_BOLETO=False, FEATURE_FISCAL=False)
    response = client.get("/api/financeiro/view")
    assert response.status_code == 200
    assert b'href="/api/financeiro/boletos/view"' not in response.data
    assert b'href="/api/fiscal/view"' not in response.data
    with security_app.app_context():
        TenantBootstrapService.garantir_cadastros_operacionais(1)
        db.session.commit()
        boleto = FormaPagamento.query.filter_by(tenant_id=1, nome="Boleto").one()
        assert boleto.id not in [record.id for record in PdvRepository.listar_formas_pagamento(1)]
        assert PdvRepository.buscar_formas_pagamento_por_ids([boleto.id], 1) == []


def test_storage_probe_private_atomic_and_no_symlinks(tmp_path):
    app = create_app()
    app.config["STORAGE_ROOT"] = str(tmp_path)
    with app.app_context():
        storage_probe()
        assert not list(tmp_path.iterdir())
        link = tmp_path / "link"
        link.symlink_to(tmp_path, target_is_directory=True)
        app.config["STORAGE_ROOT"] = str(link)
        with pytest.raises(OSError):
            storage_probe()


def test_request_id_redaction_and_metrics(monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "metrics-secret-only-32-characters-long")
    app = create_app()
    client = app.test_client()
    response = client.get("/health?password=private", headers={"X-Request-ID": "private-token"})
    assert len(response.headers["X-Request-ID"]) == 32
    supplied = "a" * 32
    assert client.get("/health", headers={"X-Request-ID": supplied}).headers["X-Request-ID"] == supplied
    assert client.get("/metrics").status_code == 404
    response = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret-only-32-characters-long"})
    assert b"oceanblue_requests_total" in response.data and b"private" not in response.data
    record = logging.LogRecord("app", logging.ERROR, "", 0, "password=private", (), None)
    assert "private" not in OperationalFormatter().format(record)


@pytest.mark.parametrize("path", ["/api/fiscal/view", "/api/financeiro/boletos/view", "/api/fiscal/configuracao", "/api/financeiro/boletos/"])
def test_production_routes_block_even_authenticated(security_app, path):
    client = security_app.test_client()
    login(client)
    security_app.testing = False
    assert client.get(path).status_code == 404


def test_audit_permission_scope_pagination_and_private_projection(security_app):
    with security_app.app_context():
        for tenant, company in [(1, 1), (1, 2), (2, 3)]:
            for number in range(3):
                AuditService.registrar("TEST", tenant_id=tenant, empresa_id=company, details="private-sensitive", commit=True)
    client = security_app.test_client()
    login(client)
    first = client.get("/api/auditoria/?limit=2&empresa_id=1")
    assert first.status_code == 200
    assert len(first.json["data"]) == 2
    assert b"private-sensitive" not in first.data
    second = client.get(f"/api/auditoria/?limit=2&empresa_id=1&before={first.json['next_cursor']}")
    assert len(second.json["data"]) == 1
    assert {row["id"] for row in first.json["data"]}.isdisjoint(row["id"] for row in second.json["data"])
    assert client.get("/api/auditoria/?empresa_id=3").status_code == 403
    assert client.get("/api/auditoria/?limit=101").status_code == 400
    with security_app.app_context():
        permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_auditoria").one()
        RolePermission.query.filter_by(permission_id=permission.id).delete()
        db.session.commit()
    assert client.get("/api/auditoria/").status_code == 403


def test_audit_request_trace_and_lossy_downgrade_refused(security_app):
    from flask_migrate import downgrade
    with security_app.test_request_context("/test"):
        from flask import g
        g.request_id = "b" * 32
        AuditService.registrar("TRACE", tenant_id=1, empresa_id=1, commit=True)
        assert AuditLog.query.filter_by(action="TRACE").one().request_id == "b" * 32
    with security_app.app_context():
        with pytest.raises(SystemExit) as refused:
            downgrade(revision="9c0d1e2f3a4b")
        assert refused.value.code == 1
        db.session.rollback()
        assert db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "a0d1e2f3a4b5"


def test_company_restricted_audit_excludes_global_and_other_company(security_app):
    with security_app.app_context():
        permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_todas_empresas").one()
        RolePermission.query.filter_by(permission_id=permission.id).delete()
        for company in (None, 1, 2):
            AuditService.registrar("SCOPED", tenant_id=1, empresa_id=company)
        db.session.commit()
    client = security_app.test_client()
    login(client)
    response = client.get("/api/auditoria/")
    assert response.status_code == 200
    assert response.json["data"]
    assert all(row["empresa_id"] == 1 for row in response.json["data"])


def test_runtime_database_role_cannot_ddl_truncate_or_erase_audit(security_app):
    from sqlalchemy.exc import DBAPIError
    with security_app.app_context():
        engine = db.engine
        with engine.begin() as connection:
            connection.execute(text("CREATE ROLE oceanblue_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"))
            commands = Path("infra/production/runtime_grants.sql").read_text().splitlines()[1:]
            for command in commands:
                connection.execute(text(command.replace("DATABASE oceanblue ", "DATABASE oceanblue_test ").replace("ROLE oceanblue_owner ", "ROLE oceanblue_test ")))
        try:
            for statement in ["CREATE TABLE forbidden (id int)", "TRUNCATE tenants CASCADE", "DELETE FROM audit_logs", "UPDATE alembic_version SET version_num='fake'"]:
                with engine.connect() as connection:
                    connection.execute(text("SET LOCAL ROLE oceanblue_runtime"))
                    with pytest.raises(DBAPIError):
                        connection.execute(text(statement))
                    connection.rollback()
            with engine.begin() as connection:
                connection.execute(text("SET LOCAL ROLE oceanblue_runtime"))
                assert connection.execute(text("SELECT count(*) FROM tenants")).scalar_one() == 2
                connection.execute(text("INSERT INTO audit_logs (tenant_id, action, criado_em) VALUES (1, 'RUNTIME', now())"))
        finally:
            with engine.begin() as connection:
                connection.execute(text("DROP OWNED BY oceanblue_runtime"))
                connection.execute(text("DROP ROLE oceanblue_runtime"))


def test_audit_benchmark_bounded_queries_and_index(security_app):
    with security_app.app_context():
        db.session.execute(text("INSERT INTO audit_logs (tenant_id, empresa_id, action, criado_em) SELECT 1, 1, 'BENCH', now() FROM generate_series(1, 10000)"))
        db.session.commit()
        db.session.execute(text("ANALYZE audit_logs"))
        plan = db.session.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) SELECT id FROM audit_logs WHERE tenant_id=1 AND empresa_id=1 AND id < 9999 ORDER BY id DESC LIMIT 51")).scalar_one()
        assert "Index" in json.dumps(plan)
    client = security_app.test_client()
    login(client)
    queries = []
    def count_queries(connection, cursor, statement, parameters, context, many):
        queries.append(statement)
    with security_app.app_context():
        event.listen(db.engine, "before_cursor_execute", count_queries)
        try:
            started = time.monotonic()
            response = client.get("/api/auditoria/?empresa_id=1&limit=50")
            elapsed = time.monotonic() - started
        finally:
            event.remove(db.engine, "before_cursor_execute", count_queries)
    assert response.status_code == 200 and len(response.json["data"]) == 50
    assert len(queries) <= 30, len(queries)
    assert elapsed < 2.0, elapsed
    Path("/tmp/benchmark-s06.json").write_text(json.dumps({"rows": 10000, "returned": 50,
        "queries": len(queries), "query_limit": 30, "elapsed_seconds": elapsed, "latency_limit_seconds": 2,
        "plan": plan}), encoding="utf-8")
