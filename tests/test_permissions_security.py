import os
import unittest
from datetime import timedelta

from app import create_app
from tests.database import reset_test_database
from app.extensions import db
from app.models.db import (
    AuditLog,
    Empresa,
    Funcionario,
    FuncionarioEmpresa,
    Permission,
    Role,
    RolePermission,
    Tenant,
    TipoEmpresa,
)
from app.security.password import hash_password
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.tenant_bootstrap_service import TenantBootstrapService
from app.services.time_service import TimeService


class PermissionsSecurityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.app_context.pop()

    def setUp(self):
        reset_test_database()

        tenant = Tenant(nome="Tenant Seguranca")
        db.session.add(tenant)
        db.session.commit()

        roles = TenantBootstrapService.garantir_permissoes_e_roles(tenant.id)
        TenantBootstrapService.garantir_cadastros_operacionais(tenant.id)

        empresa = Empresa(
            tenant_id=tenant.id,
            cnpj="11.222.333/0001-44",
            razao_social="Seguranca LTDA",
            nome_fantasia="Seguranca Matriz",
            tipo_empresa=TipoEmpresa.MATRIZ,
            ativo=True,
        )
        db.session.add(empresa)
        db.session.flush()

        operador = Funcionario(
            tenant_id=tenant.id,
            role_id=roles["operador"].id,
            nome="Operador Restrito",
            cpf="444.555.666-77",
            usuario="operador.restrito",
            senha_hash=hash_password("123456"),
            salario=1800,
            ativo=True,
        )
        db.session.add(operador)
        db.session.flush()

        db.session.add(
            FuncionarioEmpresa(
                tenant_id=tenant.id,
                funcionario_id=operador.id,
                empresa_id=empresa.id,
                ativo=True,
            )
        )
        db.session.commit()

        self.tenant = tenant
        self.empresa = empresa
        self.operador = operador
        self.roles = roles
        self.operator_role_id = roles["operador"].id

        self._remover_permissoes_financeiras_do_operador()
        self.client = self.app.test_client()

    def _remover_permissoes_financeiras_do_operador(self):
        codigos_bloqueados = [
            "visualizar_financeiro",
            "criar_lancamento_financeiro",
            "fechar_caixa",
            "visualizar_relatorio_financeiro",
            "visualizar_fiscal",
            "visualizar_notificacao",
            "gerenciar_alerta_estoque",
            "gerenciar_configuracao_cliente",
            "visualizar_funcionario",
            "visualizar_role",
            "visualizar_permission",
        ]
        permission_ids = [
            item.id
            for item in Permission.query.filter(
                Permission.tenant_id == self.tenant.id,
                Permission.codigo.in_(codigos_bloqueados),
            ).all()
        ]

        if permission_ids:
            (
                RolePermission.query.filter(
                    RolePermission.tenant_id == self.tenant.id,
                    RolePermission.role_id == self.operator_role_id,
                    RolePermission.permission_id.in_(permission_ids),
                )
                .delete(synchronize_session=False)
            )
            db.session.commit()

    def _login_operador(self):
        self.client.get("/login")
        with self.client.session_transaction() as browser_session:
            csrf = browser_session["login_csrf"]
        response = self.client.post(
            "/login",
            data={"usuario": "operador.restrito", "senha": "123456", "tenant": self.tenant.nome, "login_csrf": csrf},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        return response

    def test_bootstrap_nao_reaplica_permissoes_removidas_da_role_existente(self):
        TenantBootstrapService.garantir_permissoes_e_roles(self.tenant.id)
        db.session.commit()

        escopo = AcessoEmpresaService.obter_escopo(self.operador.id, self.tenant.id)

        self.assertNotIn("visualizar_financeiro", escopo["permission_codes"])
        self.assertNotIn("criar_lancamento_financeiro", escopo["permission_codes"])
        self.assertNotIn("fechar_caixa", escopo["permission_codes"])
        self.assertNotIn("visualizar_relatorio_financeiro", escopo["permission_codes"])

    def test_authenticated_write_requires_csrf_token(self):
        self._login_operador()
        response = self.client.post("/api/produtos/", json={})
        self.assertEqual(response.status_code, 401)
        csrf_token = self.client.get_cookie("csrf_access_token").value
        authenticated = self.client.post(
            "/api/produtos/", json={}, headers={"X-CSRF-TOKEN": csrf_token},
        )
        self.assertEqual(authenticated.status_code, 400)
        self.assertFalse(authenticated.json["success"])

    def test_login_nao_renderiza_financeiro_e_bloqueia_url_direta(self):
        self._login_operador()

        escopo = AcessoEmpresaService.obter_escopo(self.operador.id, self.tenant.id)
        self.assertNotIn("visualizar_financeiro", escopo["permission_codes"])

        home_response = self.client.get("/home")
        self.assertEqual(home_response.status_code, 200)
        self.assertNotIn(b"/financeiro/home", home_response.data)

        blocked_response = self.client.get("/financeiro/home", follow_redirects=False)
        self.assertEqual(blocked_response.status_code, 302)
        self.assertIn("/home", blocked_response.headers.get("Location", ""))

    def test_login_nao_renderiza_configuracoes_e_bloqueia_url_direta(self):
        self._login_operador()

        escopo = AcessoEmpresaService.obter_escopo(self.operador.id, self.tenant.id)
        self.assertFalse(AcessoEmpresaService.possui_acesso_configuracoes(escopo))

        home_response = self.client.get("/home")
        self.assertEqual(home_response.status_code, 200)
        self.assertNotIn(b"/configuracoes/home", home_response.data)

        blocked_response = self.client.get("/configuracoes/home", follow_redirects=False)
        self.assertEqual(blocked_response.status_code, 302)
        self.assertIn("/home", blocked_response.headers.get("Location", ""))

    def test_admin_recebe_novas_permissoes_por_padrao(self):
        admin_role = Role.query.filter_by(tenant_id=self.tenant.id, codigo="administrador").first()
        granted_codes = {
            link.permission.codigo
            for link in RolePermission.query.filter_by(
                tenant_id=self.tenant.id,
                role_id=admin_role.id,
            ).all()
        }

        for codigo in {
            "cancelar_item_venda",
            "visualizar_cliente",
            "criar_cliente",
            "editar_cliente",
            "excluir_cliente",
            "enviar_mensagem_cliente",
            "gerenciar_configuracao_cliente",
            "cancelar_movimentacao_estoque",
        }:
            self.assertIn(codigo, granted_codes)

    def test_login_registra_auditoria_e_headers_de_seguranca(self):
        response = self._login_operador()
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

        log = AuditLog.query.filter_by(action="auth.login", status="SUCCESS").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.tenant_id, self.tenant.id)
        self.assertEqual(log.actor_scope, "tenant")
        self.assertEqual(log.actor_id, self.operador.id)

    def test_rate_limit_bloqueia_excesso_de_tentativas_de_login(self):
        self.client.get("/login")
        with self.client.session_transaction() as browser_session:
            csrf = browser_session["login_csrf"]
        for _index in range(self.app.config["LOGIN_RATE_LIMIT_ATTEMPTS"]):
            response = self.client.post(
                "/login",
                data={"usuario": "usuario.bloqueado", "senha": "senha-errada", "tenant": self.tenant.nome, "login_csrf": csrf},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 401)

        blocked = self.client.post(
            "/login",
            data={"usuario": "usuario.bloqueado", "senha": "senha-errada", "tenant": self.tenant.nome, "login_csrf": csrf},
            follow_redirects=False,
        )
        self.assertEqual(blocked.status_code, 429)

    def test_trial_expirado_bloqueia_modulos_do_tenant(self):
        self.tenant.trial_ate = TimeService.today_br() - timedelta(days=1)
        db.session.commit()
        self._login_operador()

        blocked_response = self.client.get("/pdv/home", follow_redirects=False)

        self.assertEqual(blocked_response.status_code, 302)
        self.assertIn("/home", blocked_response.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
