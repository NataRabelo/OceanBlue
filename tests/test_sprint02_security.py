import hashlib
import base64
import hmac
import json
import re
import subprocess
import sys
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace

import pytest
from flask import g
from flask_jwt_extended import decode_token
from sqlalchemy import text
from openpyxl import Workbook
from werkzeug.datastructures import FileStorage
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models.db import AuditLog, CategoriaProduto, Empresa, Funcionario, FuncionarioEmpresa, PlatformOwner, Produto, ProdutoEmpresa, Role, RolePermission, Tenant, TipoEmpresa
from app.models.security import LoginAttempt, PasswordReset
from app.security.field_crypto import FieldCrypto
from app.security.password import hash_password
from app.security.rate_limit import LoginRateLimiter
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.auth_service import AuthService
from app.services.saas_plan_service import SaasPlanService
from app.services.tenant_bootstrap_service import TenantBootstrapService
from app.services.tenant_entitlement_service import TenantEntitlementService
from app.services.time_service import TimeService
from app.services.import_export_service import ImportExportService
from app.models.db import ConfiguracaoClienteEmpresa, FormaPagamento, ItemVenda, PagamentoVenda, TipoOperacao, Venda
from tests.database import reset_test_database


PASSWORD = "Long-password!2026"


@pytest.fixture
def security_app():
    app = create_app()
    with app.app_context():
        reset_test_database()
        for number in (1, 2):
            tenant = Tenant(nome=f"Tenant {number}", limite_empresas=3)
            db.session.add(tenant)
            db.session.flush()
            roles = TenantBootstrapService.garantir_permissoes_e_roles(tenant.id)
            user = Funcionario(tenant_id=tenant.id, role_id=roles["administrador"].id,
                               nome="Admin", usuario="same-user", cpf="12345678901", senha_hash=hash_password(PASSWORD))
            db.session.add(user)
            db.session.flush()
            for branch in (1, 2):
                company = Empresa(tenant_id=tenant.id, cnpj=f"{number}-{branch}",
                                  razao_social="Empresa", nome_fantasia=f"Empresa {number}-{branch}", tipo_empresa=TipoEmpresa.MATRIZ)
                db.session.add(company)
                db.session.flush()
                if branch == 1:
                    db.session.add(FuncionarioEmpresa(tenant_id=tenant.id, funcionario_id=user.id, empresa_id=company.id))
        db.session.add(PlatformOwner(nome="Owner", usuario="same-user", senha_hash=hash_password(PASSWORD)))
        db.session.commit()
    yield app
    with app.app_context():
        reset_test_database()


def login(client, tenant="Tenant 1", password=PASSWORD, scope="tenant", headers=None):
    client.get("/login")
    with client.session_transaction() as browser_session:
        csrf = browser_session["login_csrf"]
    return client.post("/login", data={"tenant": tenant, "scope": scope, "usuario": "same-user",
                                      "senha": password, "login_csrf": csrf}, headers=headers or {})


def csrf_headers(client):
    return {"X-CSRF-TOKEN": client.get_cookie("csrf_access_token").value}


def test_login_requires_tenant_and_never_falls_back_to_platform(security_app):
    client = security_app.test_client()
    assert login(client, tenant="").status_code == 401
    assert login(client, tenant="missing").status_code == 401
    assert login(client).status_code == 302
    with security_app.app_context():
        claims = decode_token(client.get_cookie("access_token_cookie").value)
        assert claims["tenant_id"] == 1 and claims["auth_scope"] == "tenant"
    assert login(client, tenant="Tenant 2").status_code == 302
    with security_app.app_context():
        assert decode_token(client.get_cookie("access_token_cookie").value)["tenant_id"] == 2
    assert login(client, tenant="", scope="platform").status_code == 302


def test_csrf_login_logout_and_replay_revocation(security_app):
    client = security_app.test_client()
    assert client.post("/login", data={"usuario": "same-user", "senha": PASSWORD}).status_code == 400
    assert login(client).status_code == 302
    stolen = client.get_cookie("access_token_cookie").value
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 401
    assert client.post("/logout", headers=csrf_headers(client)).status_code == 302
    client.set_cookie("access_token_cookie", stolen)
    assert client.get("/api/produtos/").status_code == 401


def test_password_change_revokes_every_session_and_rejects_wrong_password(security_app):
    first, second = security_app.test_client(), security_app.test_client()
    assert login(first).status_code == 302
    assert login(second).status_code == 302
    assert first.post("/senha", json={"senha_atual": "wrong", "nova_senha": "Replacement-pass!2026"}, headers=csrf_headers(first)).status_code == 400
    assert first.post("/senha", json={"senha_atual": PASSWORD, "nova_senha": "short"}, headers=csrf_headers(first)).status_code == 400
    assert first.post("/senha", json={"senha_atual": PASSWORD, "nova_senha": "Replacement-pass!2026"}, headers=csrf_headers(first)).status_code == 200
    assert second.get("/api/produtos/").status_code == 401
    assert login(second, password="Replacement-pass!2026").status_code == 302


@pytest.mark.parametrize("scope", ["tenant", "platform"])
def test_deactivation_revokes_existing_cookie(security_app, scope):
    client = security_app.test_client()
    assert login(client, scope=scope).status_code == 302
    with security_app.app_context():
        model = Funcionario if scope == "tenant" else PlatformOwner
        user = db.session.get(model, 1)
        user.ativo = False
        db.session.commit()
    path = "/api/produtos/" if scope == "tenant" else "/platform"
    response = client.get(path)
    if scope == "platform":
        response = client.get("/senha")
    assert response.status_code == 401


def test_reset_token_is_hashed_tenant_bound_expiring_and_single_use(security_app):
    with security_app.app_context():
        user = db.session.get(Funcionario, 1)
        token = AuthService.emitir_redefinicao(user, "tenant")
        record = db.session.get(PasswordReset, hashlib.sha256(token.encode()).hexdigest())
        assert record.tenant_id == 1 and record.token_hash != token
        record.expires_at = TimeService.now_utc_naive() - timedelta(minutes=1)
        db.session.commit()
        with pytest.raises(ValueError, match="expirada"):
            AuthService.redefinir_senha(token, PASSWORD + "new")
        db.session.rollback()
        token = AuthService.emitir_redefinicao(user, "tenant")
        AuthService.redefinir_senha(token, PASSWORD + "new")
        with pytest.raises(ValueError, match="expirada"):
            AuthService.redefinir_senha(token, PASSWORD + "again")
        db.session.rollback()
        assert db.session.get(Funcionario, 2).session_version == 1


def test_concurrent_reset_accepts_one_consumer(security_app):
    with security_app.app_context():
        token = AuthService.emitir_redefinicao(db.session.get(Funcionario, 1), "tenant")
    def consume(number):
        with security_app.app_context():
            try:
                AuthService.redefinir_senha(token, PASSWORD + str(number))
                return True
            except ValueError:
                db.session.rollback()
                return False
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(consume, range(4))) == 1


def test_rate_limit_shared_across_apps_and_concurrent_requests(security_app):
    def attempt(number):
        with create_app().app_context():
            return LoginRateLimiter.hit("shared-account", 5, 300)[0]
    with ThreadPoolExecutor(max_workers=10) as executor:
        assert sum(executor.map(attempt, range(15))) == 5
    with security_app.app_context():
        row = LoginAttempt.query.one()
        assert row.attempts == 15
        row.expires_at = TimeService.now_utc_naive() - timedelta(seconds=1)
        db.session.commit()
        assert LoginRateLimiter.hit("shared-account", 5, 300)[0]


def test_forwarded_header_does_not_evade_limit_and_retry_is_present(security_app):
    client = security_app.test_client()
    for number in range(5):
        assert login(client, password="wrong", headers={"X-Forwarded-For": f"192.0.2.{number}"}).status_code == 401
    response = login(client, headers={"X-Forwarded-For": "198.51.100.1"})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_cross_tenant_foreign_keys_and_company_admin_scope(security_app):
    with security_app.app_context():
        scope = AcessoEmpresaService.obter_escopo(1, 1)
        AcessoEmpresaService.validar_empresa(1, scope)
        with pytest.raises(PermissionError):
            AcessoEmpresaService.validar_empresa(3, scope)
        product = Produto(tenant_id=1, nome="Produto isolado")
        db.session.add(product)
        db.session.commit()
        db.session.add(ProdutoEmpresa(tenant_id=1, empresa_id=1, produto_id=product.id))
        db.session.commit()
        db.session.add(ProdutoEmpresa(tenant_id=1, empresa_id=3, produto_id=product.id))
        with pytest.raises(IntegrityError, match="outro tenant"):
            db.session.commit()
        db.session.rollback()
        role = Role.query.filter_by(tenant_id=2).first()
        user = db.session.get(Funcionario, 1)
        user.role_id = role.id
        with pytest.raises(IntegrityError, match="outro tenant"):
            db.session.commit()
        db.session.rollback()


def test_queries_filter_tenant_and_company_including_bulk_mutations(security_app):
    with security_app.app_context():
        for number in (1, 2):
            db.session.add(Produto(tenant_id=number, nome=f"Private {number}"))
        db.session.commit()
    with security_app.test_request_context():
        g.tenant_scope = {"tenant_id": 1, "empresa_ids": [1], "all_companies": False}
        assert [row.id for row in Empresa.query.all()] == [1]
        assert [row.nome for row in Produto.query.all()] == ["Private 1"]
        assert Produto.query.filter_by(tenant_id=2).update({"nome": "stolen"}) == 0
        assert Empresa.query.filter_by(id=2).delete() == 0
        db.session.rollback()


@pytest.mark.parametrize("table,limit", [("produtos", "limite_produtos"), ("empresas", "limite_empresas"), ("funcionarios", "limite_funcionarios")])
def test_concurrent_quota_cannot_be_exceeded(security_app, table, limit):
    with security_app.app_context():
        tenant = db.session.get(Tenant, 1)
        initial = db.session.execute(text(f"SELECT count(*) FROM {table} WHERE tenant_id=1")).scalar_one()
        setattr(tenant, limit, initial + 1)
        role_id = Role.query.filter_by(tenant_id=1, codigo="administrador").one().id
        db.session.commit()
    def create(number):
        with security_app.app_context():
            if table == "produtos":
                record = Produto(tenant_id=1, nome=f"Race {number}")
            elif table == "empresas":
                record = Empresa(tenant_id=1, cnpj=f"race-{number}", nome_fantasia=f"Race {number}", razao_social="Race", tipo_empresa=TipoEmpresa.FILIAL)
            else:
                record = Funcionario(tenant_id=1, role_id=role_id, nome=f"Race {number}", usuario=f"race-{number}", cpf=f"race-{number}", senha_hash=hash_password(PASSWORD))
            db.session.add(record)
            try:
                db.session.commit()
                return True
            except IntegrityError as error:
                db.session.rollback()
                assert "saas_quota" in str(error.orig)
                return False
    with ThreadPoolExecutor(max_workers=6) as executor:
        assert sum(executor.map(create, range(6))) == 1
    with security_app.app_context():
        assert db.session.execute(text(f"SELECT count(*) FROM {table} WHERE tenant_id=1")).scalar_one() == initial + 1


def test_trial_missing_expired_and_last_day_consistent(security_app):
    with security_app.app_context():
        tenant = db.session.get(Tenant, 1)
        for end, allowed in ((None, False), (TimeService.today_br() - timedelta(days=1), False), (TimeService.today_br(), True)):
            tenant.trial_ate = end
            db.session.commit()
            if allowed:
                assert TenantEntitlementService.validar_assinatura(1) == tenant
            else:
                with pytest.raises(PermissionError):
                    TenantEntitlementService.validar_assinatura(1)
        expiry = tenant.trial_ate
        SaasPlanService.apply_plan(tenant, codigo="business")
        assert tenant.trial_ate == expiry
        from app.services.platform_service import PlatformService
        PlatformService.atualizar_assinatura(1, {"assinatura_status": "active", "trial_ate": ""})
        PlatformService.atualizar_assinatura(1, {"assinatura_status": "trial"})
        assert tenant.trial_ate == expiry


def test_field_rotation_tampering_and_unknown_key(security_app):
    with security_app.app_context():
        first = FieldCrypto.encrypt("private-value")
        assert first != FieldCrypto.encrypt("private-value")
        original = security_app.config["FIELD_ENCRYPTION_KEY"]
        security_app.config["FIELD_ENCRYPTION_KEYS"] = {"primary": original, "next": "Next-random-field-key-unique-2026-0123456789"}
        security_app.config["FIELD_ENCRYPTION_ACTIVE_KEY_ID"] = "next"
        rotated = FieldCrypto.encrypt(first)
        assert rotated.startswith("enc:v2:next:")
        assert FieldCrypto.decrypt(rotated) == "private-value"
        with pytest.raises(ValueError):
            FieldCrypto.decrypt(rotated[:-8] + "tampered")
        security_app.config["FIELD_ENCRYPTION_KEYS"] = {"next": "Next-random-field-key-unique-2026-0123456789"}
        assert FieldCrypto.decrypt(rotated) == "private-value"
        with pytest.raises(ValueError):
            FieldCrypto.decrypt(first)


def test_role_changes_are_audited_without_password_hash(security_app):
    with security_app.app_context():
        role = Role.query.filter_by(tenant_id=1, codigo="operador").one()
        role.nome = "Operador revisado"
        db.session.commit()
        assert AuditLog.query.filter_by(action="access.role.update", tenant_id=1).count() == 1
        assert all("senha_hash" not in (record.details or "") for record in AuditLog.query.all())


@pytest.mark.parametrize("entity,limit,initial", [("produtos", "limite_produtos", 0), ("funcionarios", "limite_funcionarios", 1)])
def test_import_quota_partial_rows_updates_and_password_policy(security_app, entity, limit, initial):
    with security_app.app_context():
        tenant = db.session.get(Tenant, 1)
        setattr(tenant, limit, initial + 1)
        db.session.commit()
        scope = AcessoEmpresaService.obter_escopo(1, 1)
        config = ImportExportService.ENTITY_DEFINITIONS[entity]
        workbook = Workbook()
        sheet = workbook.active
        sheet.append([column["header"] for column in config["columns"]])
        for number in (1, 2):
            row = {"empresa": "Empresa 1-1", "nome": f"Imported {number}", "role": "operador",
                   "cpf": f"1112223334{number}", "usuario": f"imported-{number}", "senha": PASSWORD}
            sheet.append([row.get(column["key"]) for column in config["columns"]])
        buffer = BytesIO()
        workbook.save(buffer)
        content = buffer.getvalue()
        def upload():
            return FileStorage(stream=BytesIO(content), filename="import.xlsx")
        result = ImportExportService.importar_entidade(entity, upload(), 1, scope, 1)
        assert result["criadas"] == 0 and result["falhas"] == 1 and not result["confirmado"], result
        assert result["erros"][0]["mensagem"] == "Limite do plano atingido."
        result = ImportExportService.importar_entidade(entity, upload(), 1, scope, 1)
        assert result["atualizadas"] == 0 and result["falhas"] == 1 and not result["confirmado"], result
        assert "INSERT INTO" not in json.dumps(result)

        sheet.delete_rows(3)
        single = BytesIO()
        workbook.save(single)
        content = single.getvalue()
        created = ImportExportService.importar_entidade(entity, upload(), 1, scope, 1)
        assert created["confirmado"] and created["criadas"] == 1 and created["falhas"] == 0
        updated = ImportExportService.importar_entidade(entity, upload(), 1, scope, 1)
        assert updated["confirmado"] and updated["atualizadas"] == 1 and updated["falhas"] == 0


def test_all_tenant_tables_and_foreign_keys_have_database_integrity_guard(security_app):
    with security_app.app_context():
        triggers = dict(db.session.execute(text("""
            SELECT relation.relname, encode(trigger.tgargs, 'escape')
            FROM pg_trigger trigger JOIN pg_class relation ON relation.oid = trigger.tgrelid
            WHERE trigger.tgname = 'security_integrity'
        """)).all())
        for table in db.metadata.tables.values():
            if "tenant_id" not in table.c and table.name not in {"parcelas_boleto", "eventos_boleto"}:
                continue
            assert table.name in triggers, table.name
            for foreign_key in table.foreign_keys:
                if foreign_key.column.table.name != "tenants":
                    assert foreign_key.parent.name in triggers[table.name]
                    assert foreign_key.column.table.name in triggers[table.name]


def test_sales_quota_is_concurrent_and_cross_tenant_child_is_rejected(security_app):
    with security_app.app_context():
        TenantBootstrapService.garantir_cadastros_operacionais(1)
        tenant = db.session.get(Tenant, 1)
        tenant.limite_vendas_mes = 1
        operation = TipoOperacao.query.filter_by(tenant_id=1).first()
        operation_id = operation.id
        db.session.commit()
    def create(number):
        with security_app.app_context():
            db.session.add(Venda(tenant_id=1, empresa_id=1, tipo_operacao_id=operation_id, numero_unico=f"race-{number}"))
            try:
                db.session.commit()
                return True
            except IntegrityError as error:
                db.session.rollback()
                assert "saas_quota" in str(error.orig)
                return False
    with ThreadPoolExecutor(max_workers=5) as executor:
        assert sum(executor.map(create, range(5))) == 1
    with security_app.app_context():
        sale = Venda.query.one()
        payment = FormaPagamento.query.filter_by(tenant_id=1).first()
        db.session.add(PagamentoVenda(tenant_id=2, venda_id=sale.id, forma_pagamento_id=payment.id, valor=0))
        with pytest.raises(IntegrityError, match="outro tenant"):
            db.session.commit()
        db.session.rollback()


def test_company_isolation_of_financial_links_within_same_tenant(security_app):
    from app.models.db import BancoEmissor, ConfiguracaoParcelamento
    with security_app.app_context():
        bank = BancoEmissor(tenant_id=1, empresa_id=1, banco_codigo="000", banco_nome="Mock", carteira="1",
                            agencia="1", conta="1", codigo_cedente="1")
        db.session.add(bank)
        db.session.commit()
        config = ConfiguracaoParcelamento(tenant_id=1, empresa_id=2, banco_emissor_id=bank.id, numero_max_parcelas=3, valor_minimo_por_parcela=0)
        db.session.add(config)
        with pytest.raises(IntegrityError, match="outra empresa"):
            db.session.commit()
        db.session.rollback()


def test_http_cross_tenant_crud_reset_and_platform_boundary(security_app):
    with security_app.app_context():
        category = CategoriaProduto(tenant_id=2, nome="Private category")
        db.session.add(category)
        db.session.commit()
        category_id = category.id
    client = security_app.test_client()
    assert login(client).status_code == 302
    assert b"Private category" not in client.get("/api/categorias/").data
    assert client.delete(f"/api/categorias/{category_id}", headers=csrf_headers(client)).status_code >= 400
    assert client.post("/api/auth/funcionarios/2/redefinicao", headers=csrf_headers(client)).status_code == 400
    assert client.get("/api/platform/tenants").status_code == 403
    assert login(client, scope="platform").status_code == 302
    assert client.get("/api/categorias/").status_code == 403


def test_nonadmin_cannot_grant_roles_or_import_staff_even_with_permission(security_app):
    with security_app.app_context():
        user = db.session.get(Funcionario, 1)
        custom_role = Role(tenant_id=1, codigo="custom", nome="Custom")
        db.session.add(custom_role)
        db.session.flush()
        for link in user.role.permissions_links:
            db.session.add(RolePermission(tenant_id=1, role_id=custom_role.id, permission_id=link.permission_id))
        user.role_id = custom_role.id
        db.session.commit()
        scope = AcessoEmpresaService.obter_escopo(1, 1)
        with pytest.raises(PermissionError, match="administrador"):
            ImportExportService._validate_operation("funcionarios", scope, "import")
    client = security_app.test_client()
    assert login(client).status_code == 302
    for path in ("/api/roles/", "/api/permissions/", "/api/funcionarios/"):
        assert client.post(path, json={}, headers=csrf_headers(client)).status_code == 403


def test_http_errors_hide_database_and_exception_details(security_app, monkeypatch):
    from app.services.categoria_service import CategoriaService
    client = security_app.test_client()
    assert login(client).status_code == 302
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE-password-and-SQL")
    monkeypatch.setattr(CategoriaService, "listar", fail)
    response = client.get("/api/categorias/")
    assert response.status_code == 500
    assert b"PRIVATE" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_every_api_requires_auth_except_health_and_disabled_webhook(security_app):
    client = security_app.test_client()
    for rule in security_app.url_map.iter_rules():
        if not rule.rule.startswith("/api/") or rule.rule in {"/api/health", "/api/ready"}:
            continue
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", "1", rule.rule)
        method = "GET" if "GET" in rule.methods else sorted(rule.methods - {"HEAD", "OPTIONS"})[0]
        response = client.open(path, method=method)
        assert response.status_code in {401, 403}, (path, method, response.status_code)


def test_seed_requires_explicit_password_and_never_creates_demo_in_production(security_app, monkeypatch):
    monkeypatch.setenv("PLATFORM_OWNER_USER", "new-owner")
    monkeypatch.delenv("PLATFORM_OWNER_PASSWORD", raising=False)
    result = security_app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code != 0
    monkeypatch.setenv("PLATFORM_OWNER_PASSWORD", PASSWORD)
    monkeypatch.setenv("SEED_DEMO", "true")
    result = security_app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0
    assert PASSWORD not in result.output
    with security_app.app_context():
        assert Tenant.query.count() == 2
        assert PlatformOwner.query.filter_by(usuario="new-owner").count() == 1
    monkeypatch.delenv("PLATFORM_OWNER_PASSWORD")
    assert security_app.test_cli_runner().invoke(args=["seed"]).exit_code == 0


def test_rotation_cli_handles_legacy_and_rolls_back_corrupt_fields(security_app):
    with security_app.app_context():
        secret = security_app.config["FIELD_ENCRYPTION_KEY"]
        key = hashlib.sha256(secret.encode()).digest()
        nonce = bytes(range(16))
        plaintext = b"legacy-sensitive"
        stream = hmac.new(key, nonce + bytes(8), hashlib.sha256).digest()
        encrypted = bytes(left ^ right for left, right in zip(plaintext, stream))
        mac = hmac.new(key, nonce + encrypted, hashlib.sha256).digest()
        legacy = "enc:v1:" + base64.urlsafe_b64encode(nonce + mac + encrypted).decode()
        assert FieldCrypto.decrypt(legacy) == plaintext.decode()
        config = ConfiguracaoClienteEmpresa(tenant_id=1, empresa_id=1, smtp_senha=legacy, whatsapp_token="enc:v2:primary:corrupt")
        db.session.add(config)
        db.session.commit()
    runner = security_app.test_cli_runner()
    assert runner.invoke(args=["rotate-field-keys", "--apply"]).exit_code != 0
    with security_app.app_context():
        config = ConfiguracaoClienteEmpresa.query.one()
        assert config.smtp_senha == legacy
        config.whatsapp_token = None
        db.session.commit()
    assert runner.invoke(args=["rotate-field-keys"]).exit_code == 0
    assert runner.invoke(args=["rotate-field-keys", "--apply"]).exit_code == 0
    with security_app.app_context():
        assert ConfiguracaoClienteEmpresa.query.one().smtp_senha.startswith("enc:v2:primary:")


def test_real_integrations_and_webhook_stay_disabled(security_app):
    from app.services.boleto_provider import AsaasProvider, get_boleto_provider
    from app.services.fiscal_provider import FocusNFeProvider, get_fiscal_provider
    with security_app.app_context():
        config = SimpleNamespace(ativo=True, api_key="not-used", ambiente="sandbox", integrador_provider="focus_nfe")
        with pytest.raises(PermissionError):
            get_boleto_provider(SimpleNamespace(empresa=SimpleNamespace(configuracao_asaas=config)))
        with pytest.raises(PermissionError):
            get_fiscal_provider(config)
        with pytest.raises(PermissionError):
            AsaasProvider(config)._request("GET", "/", None)
        with pytest.raises(PermissionError):
            FocusNFeProvider(config)._request("GET", "/", None)
    assert security_app.test_client().post("/api/financeiro/boletos/webhook/asaas/1/1", json={}).status_code == 403


def test_jwt_key_version_rotation_rejects_previous_tokens(security_app):
    client = security_app.test_client()
    assert login(client).status_code == 302
    security_app.config["JWT_SIGNING_KEY_ID"] = "rotated"
    assert client.get("/senha").status_code == 401


def test_rate_limit_shared_between_distinct_processes(security_app):
    source = (
        "from scripts.test_environment import configure_test_environment; configure_test_environment(); "
        "from app import create_app; from app.security.rate_limit import LoginRateLimiter; "
        "app=create_app(); context=app.app_context(); context.push(); "
        "print([LoginRateLimiter.hit('process-account', 5, 300)[0] for attempt in range(4)])"
    )
    first = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=20)
    second = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=20)
    assert first.returncode == second.returncode == 0
    assert "[True, True, True, True]" in first.stdout
    assert "[True, False, False, False]" in second.stdout


def test_http_password_reset_revokes_cookie_and_rejects_reuse(security_app):
    admin = security_app.test_client()
    assert login(admin).status_code == 302
    issued = admin.post("/api/auth/funcionarios/1/redefinicao", headers=csrf_headers(admin))
    assert issued.status_code == 200
    assert issued.headers["Cache-Control"] == "no-store"
    visitor = security_app.test_client()
    visitor.get("/redefinir-senha")
    with visitor.session_transaction() as browser_session:
        csrf = browser_session["login_csrf"]
    payload = {"login_csrf": csrf, "token": issued.json["token"], "nova_senha": PASSWORD + "new"}
    assert visitor.post("/redefinir-senha", json=payload).status_code == 200
    assert admin.get("/senha").status_code == 401
    assert visitor.post("/redefinir-senha", json=payload).status_code == 400


def test_admin_without_all_companies_cannot_change_shared_accounts(security_app):
    with security_app.app_context():
        user = db.session.get(Funcionario, 1)
        for link in user.role.permissions_links:
            if link.permission.codigo == "visualizar_todas_empresas":
                db.session.delete(link)
        db.session.commit()
    client = security_app.test_client()
    assert login(client).status_code == 302
    assert client.post("/api/auth/funcionarios/2/redefinicao", headers=csrf_headers(client)).status_code == 403


@pytest.mark.parametrize("url,address,allowed", [
    ("https://provider.example/message", "8.8.8.8", True),
    ("https://provider.example/message", "127.0.0.1", False),
    ("https://provider.example/message", "169.254.169.254", False),
    ("https://provider.example/message", "::1", False),
    ("http://provider.example/message", "8.8.8.8", False),
    ("https://other.example/message", "8.8.8.8", False),
    ("https://user:password@provider.example/message", "8.8.8.8", False),
    ("https://provider.example:8443/message", "8.8.8.8", False),
])
def test_outbound_allowlist_blocks_ssrf(security_app, monkeypatch, url, address, allowed):
    from app.security.outbound import validate_webhook
    monkeypatch.setattr("app.security.outbound.socket.getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", (address, 443))])
    security_app.config["OUTBOUND_ALLOWED_HOSTS"] = "provider.example"
    with security_app.app_context():
        if allowed:
            validate_webhook(url)
        else:
            with pytest.raises(PermissionError):
                validate_webhook(url)


def test_webhook_redirects_and_smtp_provider_details_are_blocked(security_app):
    import smtplib
    from app.security.outbound import NoRedirect
    from app.services.comunicacao_service import ComunicacaoService
    with pytest.raises(PermissionError):
        NoRedirect().redirect_request(None, None, 302, "", {}, "http://169.254.169.254")
    assert "PRIVATE" not in ComunicacaoService._formatar_erro_autenticacao_smtp(
        SimpleNamespace(smtp_host="smtp.gmail.com"), smtplib.SMTPAuthenticationError(535, b"PRIVATE-key"))


def test_security_migration_rejects_legacy_cross_tenant_data_atomically(security_app):
    from flask_migrate import downgrade, upgrade
    with security_app.app_context():
        original_role = db.session.get(Funcionario, 1).role_id
        foreign_role = db.session.get(Funcionario, 2).role_id
        db.session.remove()
        try:
            downgrade(revision="3c4d5e6f7a8b")
            with db.engine.begin() as connection:
                connection.execute(text("UPDATE funcionarios SET role_id=:role WHERE id=1"), {"role": foreign_role})
            with pytest.raises(IntegrityError, match="outro tenant"):
                upgrade()
            with db.engine.connect() as connection:
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "3c4d5e6f7a8b"
            with db.engine.begin() as connection:
                connection.execute(text("UPDATE funcionarios SET role_id=:role WHERE id=1"), {"role": original_role})
            upgrade()
        finally:
            db.session.remove()
            with db.engine.begin() as connection:
                connection.execute(text("UPDATE funcionarios SET role_id=:role WHERE id=1"), {"role": original_role})
            upgrade()


def test_role_creation_and_audit_roll_back_together(security_app, monkeypatch):
    from app.repositorys.role_repository import RoleRepository
    from app.services.role_service import RoleService
    with security_app.app_context():
        permission_id = db.session.get(Funcionario, 1).role.permissions_links[0].permission_id
        add = RoleRepository.adicionar
        def fail_on_link(record):
            if isinstance(record, RolePermission):
                raise RuntimeError("simulated transaction failure")
            return add(record)
        monkeypatch.setattr(RoleRepository, "adicionar", fail_on_link)
        before = AuditLog.query.count()
        with pytest.raises(RuntimeError):
            RoleService.criar({"nome": "Atomic role", "codigo": "atomic", "permission_ids": [permission_id]}, 1)
        assert Role.query.filter_by(codigo="atomic").count() == 0
        assert AuditLog.query.count() == before
