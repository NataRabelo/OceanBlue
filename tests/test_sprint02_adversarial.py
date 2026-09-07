import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models.db import CanalMensagemCliente, CategoriaProduto, Cliente, ConfiguracaoClienteEmpresa, Funcionario, NotaFiscalVenda, Permission, Produto, ProdutoEmpresa, Role, RolePermission, TipoOperacao, TipoOperacaoEnum, Venda
from app.security.rate_limit import LoginRateLimiter
from app.services.comunicacao_service import ComunicacaoService
from app.services.fiscal_service import FiscalService
from tests.test_sprint02_security import PASSWORD, csrf_headers, login, security_app


def test_platform_account_limit_ignores_supplied_tenant(security_app):
    client = security_app.test_client()
    statuses = [login(client, scope="platform", tenant=f"ignored-{number}", password="wrong").status_code for number in range(6)]
    assert statuses == [401] * 5 + [429]


def test_case_sensitive_accounts_do_not_share_lockout(security_app):
    client = security_app.test_client()
    for number in range(5):
        assert login(client, tenant="TENANT 1", password="wrong").status_code == 401
    assert login(client, tenant="Tenant 1").status_code == 302


def test_platform_limit_survives_concurrent_ips_and_tenant_variations(security_app):
    def attempt(number):
        client = security_app.test_client()
        client.get("/login")
        with client.session_transaction() as browser_session:
            csrf = browser_session["login_csrf"]
        return client.post("/login", data={"scope": "platform", "tenant": f"ignored-{number}",
                                          "usuario": "same-user", "senha": "wrong", "login_csrf": csrf},
                           environ_overrides={"REMOTE_ADDR": f"192.0.2.{number + 1}"}).status_code
    with ThreadPoolExecutor(max_workers=10) as executor:
        statuses = list(executor.map(attempt, range(15)))
    assert statuses.count(401) == 5
    assert statuses.count(429) == 10


def test_homonymous_tenant_lockouts_are_independent(security_app):
    client = security_app.test_client()
    for number in range(5):
        assert login(client, password="wrong").status_code == 401
    assert login(client).status_code == 429
    assert login(client, tenant="Tenant 2").status_code == 302
    assert login(client, scope="platform").status_code == 302


@pytest.mark.parametrize("path", ["/login", "/redefinir-senha"])
def test_unicode_csrf_is_invalid_input_not_server_error(security_app, path):
    client = security_app.test_client()
    client.get(path)
    response = client.post(path, data={"login_csrf": "\u00e7", "nova_senha": PASSWORD})
    assert response.status_code == 400


@pytest.mark.parametrize("scope,path", [("tenant", "/home"), ("platform", "/platform/home")])
def test_authenticated_html_is_never_cached(security_app, scope, path):
    client = security_app.test_client()
    assert login(client, scope=scope).status_code == 302
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "no-store"


def test_successful_provider_response_cannot_disclose_credentials(security_app, monkeypatch):
    response = Mock()
    response.read.return_value = b'{"debug":"Bearer PRIVATE-provider-secret"}'
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr("app.services.comunicacao_service.validate_webhook", lambda endpoint: None)
    monkeypatch.setattr("app.services.comunicacao_service.request.build_opener", lambda *args: opener)
    with security_app.app_context():
        result = ComunicacaoService._enviar_webhook(
            SimpleNamespace(sms_habilitado=True, request_timeout_segundos=1),
            CanalMensagemCliente.SMS, "test", "test", "test", None,
            "https://provider.invalid/send", "PRIVATE-provider-secret",
        )
    assert "PRIVATE" not in json.dumps(result)
    response.read.assert_not_called()


def test_fiscal_mock_does_not_probe_server_files_or_environment(security_app, monkeypatch):
    probes = []
    monkeypatch.setattr("app.services.fiscal_service.os.path.exists", lambda path: probes.append(path) or True)
    monkeypatch.setattr("app.services.fiscal_service.os.getenv", lambda key: probes.append(key) or "PRIVATE")
    with security_app.app_context():
        FiscalService._validar_certificado(SimpleNamespace(certificado_caminho="/private/key.pfx", certificado_senha_env="JWT_SECRET_KEY"))
    assert probes == []


def test_database_failure_is_redacted_in_readiness_logs(security_app, monkeypatch):
    def fail(*args, **kwargs):
        raise OperationalError("SELECT PRIVATE-sql", {"password": "PRIVATE-secret"}, RuntimeError("PRIVATE-driver"))
    with monkeypatch.context() as patch:
        warning = Mock()
        patch.setattr(security_app.logger, "warning", warning)
        patch.setattr(db.session, "execute", fail)
        response = security_app.test_client().get("/api/ready")
    assert response.status_code == 503
    assert b"PRIVATE" not in response.data
    warning.assert_called_once()
    assert "PRIVATE" not in str(warning.call_args)


@pytest.mark.parametrize("target", ["limiter", "session", "logout"])
def test_database_failures_deny_auth_and_leave_session_recoverable(security_app, monkeypatch, target):
    client = security_app.test_client()
    assert login(client).status_code == 302
    stolen = client.get_cookie("access_token_cookie").value
    def fail(*args, **kwargs):
        raise OperationalError("PRIVATE-sql", {}, RuntimeError("PRIVATE-driver"))
    with monkeypatch.context() as patch:
        if target == "limiter":
            patch.setattr(LoginRateLimiter, "hit", fail)
            response = login(client)
        elif target == "session":
            patch.setattr(db.session, "get", fail)
            response = client.get("/api/produtos/")
        else:
            patch.setattr(db.session, "commit", fail)
            response = client.post("/logout", headers=csrf_headers(client))
    assert response.status_code == 500
    assert b"PRIVATE" not in response.data
    client.set_cookie("access_token_cookie", stolen)
    assert client.get("/api/produtos/").status_code == 200


def test_permission_and_company_revocation_apply_to_existing_cookie(security_app):
    client = security_app.test_client()
    assert login(client).status_code == 302
    with security_app.app_context():
        user = db.session.get(Funcionario, 1)
        for code in ("visualizar_produto", "visualizar_todas_empresas"):
            permission = Permission.query.filter_by(tenant_id=1, codigo=code).one()
            RolePermission.query.filter_by(role_id=user.role_id, permission_id=permission.id).delete()
        db.session.commit()
    assert client.get("/api/produtos/").status_code == 403
    assert client.get("/api/clientes/configuracoes/2").status_code in {400, 403}
    assert client.get("/api/clientes/configuracoes/1").status_code == 200


@pytest.mark.parametrize("field,value", [("tenant_id", 2), ("sub", "2"), ("auth_scope", "platform"), ("session_version", 100)])
def test_modified_unsigned_claims_cannot_authenticate(security_app, field, value):
    client = security_app.test_client()
    assert login(client).status_code == 302
    header, payload, signature = client.get_cookie("access_token_cookie").value.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims[field] = value
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    client.set_cookie("access_token_cookie", ".".join((header, payload, signature)))
    assert client.get("/api/produtos/").status_code == 422


@pytest.mark.parametrize("mode", ["anonymous", "wrong_scope", "missing_csrf"])
def test_every_api_method_enforces_auth_scope_and_csrf(security_app, mode):
    tenant_client = security_app.test_client()
    platform_client = security_app.test_client()
    if mode != "anonymous":
        assert login(tenant_client).status_code == 302
        assert login(platform_client, scope="platform").status_code == 302
    checked = 0
    for rule in security_app.url_map.iter_rules():
        if not rule.rule.startswith("/api/") or rule.rule in {"/api/health", "/api/ready"}:
            continue
        path = re.sub(r"<[^>]+>", "2", rule.rule)
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            if mode == "missing_csrf" and method == "GET":
                continue
            is_platform = path.startswith("/api/platform/")
            if mode == "wrong_scope":
                client = tenant_client if is_platform else platform_client
                headers = csrf_headers(client)
            else:
                client = platform_client if is_platform else tenant_client
                headers = {}
            response = client.open(path, method=method, json={"tenant_id": 2, "empresa_id": 3, "id": 2}, headers=headers)
            if mode == "wrong_scope" and method == "GET" and response.status_code == 302:
                assert response.headers["Location"] in {"/platform/home", "/home", "/login"}
            else:
                assert response.status_code in {401, 403}, (mode, path, method, response.status_code)
            checked += 1
    assert checked > 50
    print(f"API_MATRIX {mode}: {checked} route/method pairs denied")


@pytest.mark.parametrize("company", [2, 3])
def test_company_configuration_idor_read_write_and_test(security_app, company):
    with security_app.app_context():
        user = db.session.get(Funcionario, 1)
        permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_todas_empresas").one()
        RolePermission.query.filter_by(role_id=user.role_id, permission_id=permission.id).delete()
        db.session.add(ConfiguracaoClienteEmpresa(tenant_id=1 if company == 2 else 2, empresa_id=company, smtp_host="PRIVATE-company"))
        db.session.commit()
    client = security_app.test_client()
    assert login(client).status_code == 302
    for method, suffix in [("GET", ""), ("PUT", ""), ("POST", "/testar")]:
        response = client.open(f"/api/clientes/configuracoes/{company}{suffix}", method=method,
                               json={"tenant_id": 1, "empresa_id": 1, "smtp_host": "stolen"}, headers=csrf_headers(client))
        assert response.status_code in {400, 403}
        assert b"PRIVATE" not in response.data
    with security_app.app_context():
        assert ConfiguracaoClienteEmpresa.query.filter_by(empresa_id=company).one().smtp_host == "PRIVATE-company"


def test_foreign_resource_ids_cannot_read_modify_or_delete(security_app):
    with security_app.app_context():
        category = CategoriaProduto(tenant_id=2, nome="PRIVATE-category")
        customer = Cliente(tenant_id=2, nome="PRIVATE-customer")
        product = Produto(tenant_id=2, nome="PRIVATE-product")
        operation = TipoOperacao(tenant_id=2, nome="PRIVATE-operation", codigo="SALE", tipo_operacao=TipoOperacaoEnum.VENDA)
        db.session.add_all([category, customer, product, operation])
        db.session.flush()
        listing = ProdutoEmpresa(tenant_id=2, empresa_id=3, produto_id=product.id)
        sale = Venda(tenant_id=2, empresa_id=3, cliente_id=customer.id, tipo_operacao_id=operation.id, numero_unico="PRIVATE-sale")
        db.session.add_all([listing, sale])
        db.session.flush()
        note = NotaFiscalVenda(tenant_id=2, empresa_id=3, venda_id=sale.id, mensagem_retorno="PRIVATE-note")
        db.session.add(note)
        db.session.commit()
        resources = {
            "categorias": category.id, "clientes": customer.id, "produtos": listing.id,
            "roles": Role.query.filter_by(tenant_id=2, codigo="administrador").one().id,
            "permissions": Permission.query.filter_by(tenant_id=2, codigo="visualizar_produto").one().id,
            "funcionarios": 2,
        }
        customer_id, sale_id, note_id = customer.id, sale.id, note.id
        before = {model.__tablename__: [dict(row) for row in db.session.execute(db.select(model.__table__).where(model.tenant_id == 2)).mappings()]
                  for model in (CategoriaProduto, Cliente, Produto, ProdutoEmpresa, Role, Permission, Funcionario, Venda, NotaFiscalVenda)}
    client = security_app.test_client()
    assert login(client).status_code == 302
    for resource, identity in resources.items():
        response = client.get(f"/api/{resource}/", query_string={"tenant_id": 2, "empresa_id": 3})
        assert response.status_code < 500
        assert b"PRIVATE" not in response.data
        for method in ("PUT", "DELETE"):
            response = client.open(f"/api/{resource}/{identity}", method=method,
                                   json={"nome": "stolen", "tenant_id": 2, "empresa_id": 3, "ativo": False}, headers=csrf_headers(client))
            assert 400 <= response.status_code < 500, (resource, method, response.status_code)
    for suffix in ("carteira", "historico-vendas", "mensagens"):
        response = client.get(f"/api/clientes/{customer_id}/{suffix}")
        assert b"PRIVATE" not in response.data
        assert response.status_code < 500
    for method, path in [
        ("GET", f"/api/pdv/vendas/{sale_id}/comprovante"),
        ("POST", f"/api/pdv/vendas/{sale_id}/cancelar"),
        ("GET", f"/api/fiscal/notas/{note_id}/xml"),
        ("GET", f"/api/fiscal/notas/{note_id}/danfe"),
        ("POST", f"/api/fiscal/notas/{note_id}/consultar"),
        ("POST", f"/api/fiscal/notas/{note_id}/cancelar"),
    ]:
        response = client.open(path, method=method, json={"tenant_id": 2, "empresa_id": 3, "motivo": "stolen"}, headers=csrf_headers(client))
        assert 400 <= response.status_code < 500, (path, response.status_code)
        assert b"PRIVATE" not in response.data
    with security_app.app_context():
        for model in (CategoriaProduto, Cliente, Produto, ProdutoEmpresa, Role, Permission, Funcionario, Venda, NotaFiscalVenda):
            after = [dict(row) for row in db.session.execute(db.select(model.__table__).where(model.tenant_id == 2)).mappings()]
            assert before[model.__tablename__] == after
