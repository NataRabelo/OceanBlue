import base64
import errno
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config import ProductionConfig
from app.extensions import db
from app.models.db import AuditLog, Empresa, FuncionarioEmpresa, Permission, RolePermission
from app.operations import storage_probe
from app.services.audit_service import AuditService
from app.services.boleto_provider import AsaasProvider, MockApiBancariaProvider, get_boleto_provider
from app.services.fiscal_provider import FocusNFeProvider, MockIntegradorFiscalProvider, get_fiscal_provider
from tests.test_sprint02_security import login, security_app


@pytest.fixture
def audit_client(security_app):
    with security_app.app_context():
        for tenant, company in [(None, None), (1, None), (1, 1), (1, 2), (2, 3)]:
            for number in range(5):
                AuditService.registrar(
                    f"DATA_{tenant}_{company}_{number}", tenant_id=tenant, empresa_id=company,
                    details="SECRET-DATA-SENTINEL", actor_id=number,
                )
        db.session.commit()
    client = security_app.test_client()
    assert login(client).status_code == 302
    return client


def restrict_companies():
    permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_todas_empresas").one()
    RolePermission.query.filter_by(permission_id=permission.id).delete()
    db.session.commit()


def test_audit_tenant_cursor_and_header_tampering(audit_client):
    for query in ["", "tenant_id=2", "tenant_id=", "empresa_id=1&tenant_id=2", "before=2147483647"]:
        response = audit_client.get("/api/auditoria/?" + query, headers={"X-Tenant-ID": "2", "X-Empresa-ID": "3"})
        assert response.status_code == 200
        assert response.json["data"]
        assert all(row["empresa_id"] in (None, 1, 2) for row in response.json["data"])
        assert all(not row["action"].startswith(("DATA_None_", "DATA_2_")) for row in response.json["data"])
        assert b"SECRET-DATA-SENTINEL" not in response.data
        assert all(set(row) == {"id", "empresa_id", "action", "status", "actor_id", "request_id", "criado_em"}
                   for row in response.json["data"])
    assert audit_client.get("/api/auditoria/?empresa_id=3").status_code == 403


def test_audit_cookie_claim_tampering(audit_client):
    header, payload, signature = audit_client.get_cookie("access_token_cookie").value.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["tenant_id"] = 2
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    audit_client.set_cookie("access_token_cookie", f"{header}.{forged}.{signature}")
    response = audit_client.get("/api/auditoria/")
    assert response.status_code in (401, 422)
    assert "data" not in (response.json or {})


@pytest.mark.parametrize("path", ["/api/auditoria/", "/api/auditoria/view"])
def test_audit_requires_permission_and_tenant_scope(security_app, path):
    client = security_app.test_client()
    assert client.get(path).status_code == 401
    assert login(client, scope="platform", tenant="").status_code == 302
    assert client.get(path).status_code == 403
    assert login(client).status_code == 302
    with security_app.app_context():
        permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_auditoria").one()
        permission.ativo = False
        db.session.commit()
    assert client.get(path).status_code == 403


def test_audit_live_company_revocation_and_empty_scope(audit_client, security_app):
    with security_app.app_context():
        restrict_companies()
    response = audit_client.get("/api/auditoria/?limit=2")
    assert response.status_code == 200
    assert all(row["empresa_id"] == 1 for row in response.json["data"])
    cursor = response.json["next_cursor"]
    assert cursor is not None
    assert audit_client.get("/api/auditoria/?empresa_id=2").status_code == 403
    with security_app.app_context():
        FuncionarioEmpresa.query.filter_by(tenant_id=1, funcionario_id=1).update({"ativo": False})
        db.session.commit()
    assert audit_client.get(f"/api/auditoria/?before={cursor}").json == {"data": [], "next_cursor": None}
    assert audit_client.get("/api/auditoria/?empresa_id=1").status_code == 403


def test_audit_inactive_company_denied(audit_client, security_app):
    with security_app.app_context():
        restrict_companies()
        db.session.get(Empresa, 1).ativo = False
        db.session.commit()
    assert audit_client.get("/api/auditoria/").json == {"data": [], "next_cursor": None}
    assert audit_client.get("/api/auditoria/?empresa_id=1").status_code == 403


@pytest.mark.parametrize("query", [
    "limit=0", "limit=101", "limit=-1", "limit=", "limit=1.0", "limit=1e2", "limit=1_0",
    "before=0", "before=2147483648", "before=", "before=1%20OR%201=1", "limit=%2B1", "limit=%201",
    "limit=%EF%BC%91", "empresa_id=%00", pytest.param("limit=" + "9" * 5000, id="limit-5000-digits"),
    "empresa_id=", "empresa_id=-1", "empresa_id=0", "empresa_id=2147483648",
    "empresa_id=99999999999999999999999999999999999999999999999999",
    "empresa_id=1&empresa_id=3", "limit=1&limit=100", "before=20&before=1",
])
def test_audit_rejects_ambiguous_or_out_of_range_parameters(audit_client, query):
    assert audit_client.get("/api/auditoria/?" + query).status_code == 400


def test_audit_pagination_survives_insert_and_reaches_end(audit_client, security_app):
    first = audit_client.get("/api/auditoria/?empresa_id=1&limit=2").json
    seen = [row["id"] for row in first["data"]]
    with security_app.app_context():
        inserted = AuditService.registrar("CONCURRENT", tenant_id=1, empresa_id=1, commit=True).id
    cursor = first["next_cursor"]
    for page in range(10):
        if cursor is None:
            break
        response = audit_client.get(f"/api/auditoria/?empresa_id=1&limit=2&before={cursor}")
        assert response.status_code == 200
        payload = response.json
        assert all(row["id"] < cursor for row in payload["data"])
        seen.extend(row["id"] for row in payload["data"])
        cursor = payload["next_cursor"]
    assert cursor is None
    assert len(seen) == len(set(seen)) == 5
    assert seen == sorted(seen, reverse=True)
    assert inserted not in seen
    assert audit_client.get("/api/auditoria/?before=1").json == {"data": [], "next_cursor": None}


def test_audit_first_page_includes_maximum_integer_id(audit_client, security_app):
    with security_app.app_context():
        db.session.execute(text("INSERT INTO audit_logs (id, tenant_id, empresa_id, action, criado_em) VALUES (2147483647, 1, 1, 'MAX_ID', now())"))
        db.session.commit()
    response = audit_client.get("/api/auditoria/?empresa_id=1&limit=1")
    assert response.status_code == 200
    assert response.json["data"][0]["id"] == 2147483647
    assert response.json["next_cursor"] == 2147483647
    assert audit_client.get("/api/auditoria/?empresa_id=1&before=2147483647").json["data"][0]["id"] < 2147483647


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_audit_http_tampering_is_read_only(audit_client, method):
    before = audit_client.get("/api/auditoria/").json
    response = audit_client.open("/api/auditoria/", method=method, json={"id": 1, "tenant_id": 2, "action": "FORGED"})
    assert response.status_code == 405
    assert audit_client.get("/api/auditoria/").json == before


def test_audit_runtime_role_rejects_update_delete_and_truncate(security_app):
    with security_app.app_context():
        record_id = AuditService.registrar("IMMUTABLE", tenant_id=1, empresa_id=1, commit=True).id
        with db.engine.begin() as connection:
            connection.execute(text("CREATE ROLE oceanblue_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"))
            for command in Path("infra/production/runtime_grants.sql").read_text().splitlines()[1:]:
                connection.execute(text(command.replace("DATABASE oceanblue ", "DATABASE oceanblue_test ").replace("ROLE oceanblue_owner ", "ROLE oceanblue_test ")))
        try:
            for statement in ["UPDATE audit_logs SET action='FORGED'", "DELETE FROM audit_logs", "TRUNCATE audit_logs"]:
                with db.engine.connect() as connection:
                    connection.execute(text("SET LOCAL ROLE oceanblue_runtime"))
                    with pytest.raises(DBAPIError) as refused:
                        connection.execute(text(statement))
                    assert refused.value.orig.pgcode == "42501"
                    connection.rollback()
            assert db.session.get(AuditLog, record_id).action == "IMMUTABLE"
        finally:
            with db.engine.begin() as connection:
                connection.execute(text("DROP OWNED BY oceanblue_runtime"))
                connection.execute(text("DROP ROLE oceanblue_runtime"))


@pytest.fixture
def storage_app(tmp_path):
    app = Flask(__name__)
    root = tmp_path / "storage"
    root.mkdir(mode=0o700)
    app.config["STORAGE_ROOT"] = str(root)
    with app.app_context():
        yield app, root


@pytest.mark.parametrize("attack", ["relative", "traversal", "missing", "file", "symlink", "parent_symlink"])
def test_storage_rejects_unsafe_roots(storage_app, tmp_path, attack):
    app, root = storage_app
    target = root
    if attack == "relative":
        target = Path("relative-storage")
    elif attack == "traversal":
        target = root / ".." / root.name
    elif attack == "missing":
        target = root / "missing"
    elif attack == "file":
        target = root / "file"
        target.write_bytes(b"unchanged")
    elif attack == "symlink":
        target = tmp_path / "linked-root"
        target.symlink_to(root, target_is_directory=True)
    else:
        link = tmp_path / "linked-parent"
        link.symlink_to(tmp_path, target_is_directory=True)
        target = link / root.name
    app.config["STORAGE_ROOT"] = str(target)
    with pytest.raises(OSError):
        storage_probe()
    assert not list(root.glob(".probe-*"))


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_storage_probe_never_overwrites_existing_link(storage_app, tmp_path, monkeypatch, link_kind):
    _, root = storage_app
    victim = tmp_path / "victim"
    victim.write_bytes(b"PRIVATE-UNCHANGED")
    target = root / (".probe-" + "a" * 32)
    if link_kind == "symlink":
        target.symlink_to(victim)
    else:
        os.link(victim, target)
    monkeypatch.setattr("app.operations.secrets.token_hex", lambda size: "a" * 32)
    with pytest.raises(OSError):
        storage_probe()
    assert victim.read_bytes() == b"PRIVATE-UNCHANGED"
    assert target.exists()


@pytest.mark.parametrize("operation,error_number", [
    ("open", errno.EROFS), ("open", errno.EACCES), ("write", errno.ENOSPC),
    ("fsync", errno.EIO), ("lseek", errno.EIO), ("read", errno.EIO),
])
def test_storage_io_errors_fail_closed_and_cleanup(storage_app, monkeypatch, operation, error_number):
    _, root = storage_app
    failing = Mock(side_effect=OSError(error_number, "injected storage failure"))
    with monkeypatch.context() as injection:
        injection.setattr(f"app.operations.os.{operation}", failing)
        with pytest.raises(OSError):
            storage_probe()
    failing.assert_called_once()
    assert not list(root.iterdir())
    storage_probe()
    assert not list(root.iterdir())


def test_storage_read_only_directory_real_permissions(storage_app):
    _, root = storage_app
    assert os.geteuid() != 0
    root.chmod(0o500)
    try:
        with pytest.raises(OSError):
            storage_probe()
    finally:
        root.chmod(0o700)
    assert not list(root.iterdir())


@pytest.mark.parametrize("fault", ["zero_write", "short_write", "corruption", "trailing_bytes"])
def test_storage_probe_detects_incomplete_or_corrupt_write(storage_app, monkeypatch, fault):
    _, root = storage_app
    original_write = os.write

    def damaged_write(descriptor, payload):
        if fault == "zero_write":
            return 0
        if fault == "short_write":
            return original_write(descriptor, payload[:1])
        if fault == "trailing_bytes":
            original_write(descriptor, payload + b"EXTRA")
            return len(payload)
        return original_write(descriptor, b"X" * len(payload))

    with monkeypatch.context() as injection:
        injection.setattr("app.operations.os.write", damaged_write)
        with pytest.raises(OSError):
            storage_probe()
    assert not list(root.iterdir())


def test_storage_failure_http_readiness_and_mutation(security_app, tmp_path, monkeypatch):
    security_app.testing = False
    security_app.config["STORAGE_ROOT"] = str(tmp_path)
    client = security_app.test_client()
    with monkeypatch.context() as injection:
        injection.setattr("app.operations.os.write", Mock(side_effect=OSError(errno.ENOSPC, "disk full")))
        assert client.get("/readiness").status_code == 503
        assert client.post("/login").status_code == 503
        assert client.get("/health").status_code == 200
    assert not list(tmp_path.iterdir())
    assert client.get("/readiness").status_code == 200


@pytest.fixture(params=["file", "directory", "symlink", "dangling_symlink"])
def restore_marker(storage_app, request):
    _, root = storage_app
    marker = root.parent / ".oceanblue-restore-incomplete"
    if request.param == "file":
        marker.write_text("restore interrupted", encoding="utf-8")
    elif request.param == "directory":
        marker.mkdir()
    else:
        target = root.parent / "restore-target"
        if request.param == "symlink":
            target.write_text("restore interrupted", encoding="utf-8")
        marker.symlink_to(target)
    return marker


def remove_restore_marker(marker):
    if marker.is_dir() and not marker.is_symlink():
        marker.rmdir()
    else:
        marker.unlink()


def test_storage_restore_marker_blocks_probe_before_write_and_recovers(storage_app, restore_marker, monkeypatch):
    _, root = storage_app
    opened = Mock(wraps=os.open)
    with monkeypatch.context() as injection:
        injection.setattr("app.operations.os.open", opened)
        with pytest.raises(OSError):
            storage_probe()
    opened.assert_not_called()
    assert not list(root.iterdir())
    remove_restore_marker(restore_marker)
    storage_probe()
    assert not list(root.iterdir())


def test_storage_restore_marker_blocks_http_and_removal_recovers(security_app, storage_app, restore_marker):
    _, root = storage_app
    security_app.testing = False
    security_app.config["STORAGE_ROOT"] = str(root)
    mutations = []

    def mutation():
        mutations.append("executed")
        return "ok"

    methods = ["POST", "PUT", "PATCH", "DELETE"]
    security_app.add_url_rule("/data-restore-mutation", "data_restore_mutation", mutation, methods=methods)
    client = security_app.test_client()
    assert client.get("/readiness").status_code == 503
    assert client.get("/health").status_code == 200
    for method in methods:
        assert client.open("/data-restore-mutation", method=method).status_code == 503
    assert not mutations
    assert not list(root.iterdir())
    remove_restore_marker(restore_marker)
    assert client.get("/readiness").status_code == 200
    for method in methods:
        assert client.open("/data-restore-mutation", method=method).status_code == 200
    assert len(mutations) == len(methods)
    assert not list(root.iterdir())


@pytest.mark.parametrize("flag", ["FEATURE_BOLETO", "FEATURE_FISCAL", "FEATURE_EXTERNAL_PROVIDERS"])
@pytest.mark.parametrize("value", ["true", "TRUE", "False", "0", "1", "off", "", " false", "false ", "garbage"])
def test_production_feature_flags_reject_noncanonical_values(monkeypatch, flag, value):
    for name in ("FEATURE_BOLETO", "FEATURE_FISCAL", "FEATURE_EXTERNAL_PROVIDERS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FORCE_HTTPS", "true")
    monkeypatch.setenv(flag, value)
    with pytest.raises(RuntimeError, match=flag + " bloqueada"):
        ProductionConfig.validate_runtime()


@pytest.mark.parametrize("factory", [get_boleto_provider, get_fiscal_provider])
@pytest.mark.parametrize("flags", [False, True, "true"])
def test_disabled_production_provider_factory_fails_closed(factory, flags):
    app = Flask(__name__)
    app.config.update(TESTING=False, FEATURE_BOLETO=flags, FEATURE_FISCAL=flags, FEATURE_EXTERNAL_PROVIDERS=flags)
    with app.app_context(), pytest.raises(PermissionError):
        factory()


@pytest.mark.parametrize("factory,flag,provider_class", [
    (get_boleto_provider, "FEATURE_BOLETO", MockApiBancariaProvider),
    (get_fiscal_provider, "FEATURE_FISCAL", MockIntegradorFiscalProvider),
])
def test_mock_provider_requires_explicit_testing_flag(factory, flag, provider_class):
    app = Flask(__name__)
    app.testing = True
    with app.app_context():
        for value in (None, False, "false", "true", 1):
            app.config[flag] = value
            with pytest.raises(PermissionError):
                factory()
        app.config[flag] = True
        assert isinstance(factory(), provider_class)


@pytest.mark.parametrize("provider_class", [AsaasProvider, FocusNFeProvider])
def test_real_provider_request_denied_before_network_or_secret(provider_class, monkeypatch):
    transport = Mock(side_effect=AssertionError("external integration attempted"))
    decrypt = Mock(side_effect=AssertionError("secret accessed before integration guard"))
    monkeypatch.setattr("urllib.request.urlopen", transport)
    monkeypatch.setattr("app.security.field_crypto.FieldCrypto.decrypt", decrypt)
    provider = object.__new__(provider_class)
    with pytest.raises(PermissionError):
        provider._request("POST", "/arbitrary", {"sensitive": "not-sent"})
    transport.assert_not_called()
    decrypt.assert_not_called()


def test_real_provider_selection_and_download_denied(storage_app):
    app, _ = storage_app
    app.config.update(TESTING=True, FEATURE_BOLETO=True, FEATURE_FISCAL=True)
    banco = SimpleNamespace(empresa=SimpleNamespace(configuracao_asaas=SimpleNamespace(ativo=True, api_key="encrypted")))
    with pytest.raises(PermissionError):
        get_boleto_provider(banco)
    with pytest.raises(PermissionError):
        get_fiscal_provider(SimpleNamespace(integrador_provider="focus_nfe"))
    provider = object.__new__(FocusNFeProvider)
    for url in ["file:///etc/passwd", "http://127.0.0.1/", "http://169.254.169.254/", "https://example.invalid/"]:
        with pytest.raises(PermissionError):
            provider._salvar_url(None, url, "../../escape")
