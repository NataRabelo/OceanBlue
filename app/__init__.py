import os
import logging
import sys

from flask import Flask
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.extensions import db, jwt, migrate
from app.models.db import Funcionario, ModoVisualEmpresa, PlatformOwner
from app.routes import register_blueprints
from app.security.headers import register_security_headers
from app.security.jwt import get_auth_scope
from app.security.errors import register_errors
from app.security import isolation
from app.seeds.seed import run_seed
from app.services.acesso_empresa_service import AcessoEmpresaService


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)


def register_context_processors(app: Flask) -> None:
    tenant_navigation_items = [
        {
            "label": "Home Operacional",
            "endpoint": "main.home",
            "icon": "layout-grid",
            "permission": None,
            "group": "Painel",
            "active_prefixes": ["/home"],
        },
        {
            "label": "Configuracoes",
            "endpoint": "main.settings_home",
            "icon": "sliders-horizontal",
            "permission": None,
            "flag": "can_view_settings",
            "group": "Configuracoes",
            "active_prefixes": ["/configuracoes/home"],
        },
        {
            "label": "PDV",
            "endpoint": "main.pdv_home",
            "icon": "shopping-cart",
            "permission": "visualizar_pdv",
            "group": "Operacao",
            "active_prefixes": ["/pdv/home", "/api/pdv/view"],
        },
        {
            "label": "Estoque",
            "endpoint": "main.estoque_home",
            "icon": "boxes",
            "permission": "visualizar_produto",
            "group": "Operacao",
            "active_prefixes": ["/estoque/home", "/api/estoque/view", "/api/estoque/indicadores/view"],
        },
        {
            "label": "Financeiro",
            "endpoint": "main.financeiro_home",
            "icon": "landmark",
            "permission": "visualizar_financeiro",
            "group": "Operacao",
            "active_prefixes": [
                "/financeiro/home",
                "/api/financeiro/view",
                "/api/financeiro/lancamentos/view",
                "/api/financeiro/relatorios/view",
            ],
        },
        {
            "label": "Fiscal",
            "href": "/api/fiscal/view",
            "icon": "receipt",
            "permission": "visualizar_fiscal",
            "group": "Configuracoes",
            "active_prefixes": ["/api/fiscal/"],
        },
        {
            "label": "Clientes",
            "href": "/api/clientes/view",
            "icon": "contact-round",
            "permission": "visualizar_cliente",
            "group": "Relacionamento",
            "active_prefixes": ["/api/clientes/view"],
        },
        {
            "label": "Alertas",
            "href": "/api/estoque/alertas/view",
            "icon": "shield-alert",
            "permission": "visualizar_notificacao",
            "group": "Configuracoes",
            "active_prefixes": ["/api/estoque/alertas/view"],
        },
        {
            "label": "Produtos",
            "href": "/api/produtos/view",
            "icon": "package-plus",
            "permission": "visualizar_produto",
            "group": "Cadastros",
            "active_prefixes": ["/api/produtos/view"],
        },
        {
            "label": "Categorias",
            "href": "/api/categorias/view",
            "icon": "layers",
            "permission": "visualizar_categoria",
            "group": "Cadastros",
            "active_prefixes": ["/api/categorias/view"],
        },
        {
            "label": "Funcionarios",
            "href": "/api/funcionarios/view",
            "icon": "users",
            "permission": "visualizar_funcionario",
            "group": "Configuracoes",
            "active_prefixes": ["/api/funcionarios/view"],
        },
        {
            "label": "Cupons",
            "href": "/api/cupons/view",
            "icon": "ticket-percent",
            "permission": "visualizar_cupom",
            "group": "Cadastros",
            "active_prefixes": ["/api/cupons/view"],
        },
        {
            "label": "Vales",
            "href": "/api/adiantamentos/view",
            "icon": "wallet-cards",
            "permission": "visualizar_adiantamento",
            "group": "Cadastros",
            "active_prefixes": ["/api/adiantamentos/view"],
        },
        {
            "label": "Importacao em Lote",
            "href": "/api/importacao-exportacao/view",
            "icon": "sheet",
            "permission": "visualizar_importacao_exportacao",
            "group": "Cadastros",
            "active_prefixes": ["/api/importacao-exportacao/view"],
        },
        {
            "label": "Roles",
            "href": "/api/roles/view",
            "icon": "shield-check",
            "permission": "visualizar_role",
            "group": "Configuracoes",
            "active_prefixes": ["/api/roles/view"],
        },
        {
            "label": "Permissions",
            "href": "/api/permissions/view",
            "icon": "key-round",
            "permission": "visualizar_permission",
            "group": "Configuracoes",
            "active_prefixes": ["/api/permissions/view"],
        },
    ]

    def _to_theme_skin(mode):
        visual_mode = mode or ModoVisualEmpresa.MODERNO
        if isinstance(visual_mode, str):
            visual_mode = visual_mode.upper()
            return "classic" if visual_mode == ModoVisualEmpresa.LEGADO.value else "modern"

        return "classic" if visual_mode == ModoVisualEmpresa.LEGADO else "modern"

    def _build_tenant_theme_config(funcionario):
        empresas_ativas = []

        for vinculo in getattr(funcionario, "empresas_vinculadas", []) or []:
            empresa = getattr(vinculo, "empresa", None)
            if not vinculo.ativo or not empresa or not empresa.ativo:
                continue
            empresas_ativas.append(empresa)

        empresas_ativas.sort(key=lambda item: (item.nome_fantasia or "").lower())

        company_modes = {
            str(empresa.id): _to_theme_skin(getattr(empresa, "visual_modo", None))
            for empresa in empresas_ativas
        }
        unique_modes = set(company_modes.values())
        default_mode = next(iter(unique_modes)) if len(unique_modes) == 1 else "modern"

        return {
            "defaultMode": default_mode,
            "companyModes": company_modes,
            "storageKey": "oceanblue:empresa-visual-selecionada",
        }

    def _get_permission_codes(funcionario):
        return AcessoEmpresaService.extrair_codigos_permissao(funcionario)

    def _build_navigation(permission_codes, ui_flags):
        navigation = []
        for item in tenant_navigation_items:
            flag = item.get("flag")
            if flag and not ui_flags.get(flag):
                continue
            permission = item.get("permission")
            if permission and permission not in permission_codes:
                continue
            navigation.append(item)
        return navigation

    def _build_navigation_groups(navigation_items):
        groups = []
        group_index = {}

        for item in navigation_items:
            group_name = item.get("group") or "Geral"
            if group_name not in group_index:
                group_index[group_name] = len(groups)
                groups.append({
                    "label": group_name,
                    "items": [],
                })

            groups[group_index[group_name]]["items"].append(item)

        return groups

    def _build_template_flags(permission_codes):
        return {
            "can_view_pdv": "visualizar_pdv" in permission_codes,
            "can_manage_sales": "registrar_venda" in permission_codes,
            "can_cancel_sales": "cancelar_venda" in permission_codes,
            "can_cancel_sale_items": "cancelar_item_venda" in permission_codes,
            "can_view_stock": "visualizar_produto" in permission_codes,
            "can_manage_products": "criar_produto" in permission_codes or "editar_produto" in permission_codes,
            "can_cancel_stock_movements": "cancelar_movimentacao_estoque" in permission_codes,
            "can_view_categories": "visualizar_categoria" in permission_codes,
            "can_manage_categories": any(
                permission in permission_codes
                for permission in ["criar_categoria", "editar_categoria", "excluir_categoria"]
            ),
            "can_view_customers": "visualizar_cliente" in permission_codes,
            "can_manage_customers": any(
                permission in permission_codes
                for permission in ["criar_cliente", "editar_cliente", "excluir_cliente"]
            ),
            "can_send_customer_messages": "enviar_mensagem_cliente" in permission_codes,
            "can_manage_customer_settings": "gerenciar_configuracao_cliente" in permission_codes,
            "can_view_finance": "visualizar_financeiro" in permission_codes,
            "can_view_finance_reports": "visualizar_relatorio_financeiro" in permission_codes,
            "can_manage_finance_entries": "criar_lancamento_financeiro" in permission_codes,
            "can_close_cashier": "fechar_caixa" in permission_codes,
            "can_view_fiscal": "visualizar_fiscal" in permission_codes,
            "can_manage_fiscal": "gerenciar_fiscal" in permission_codes,
            "can_view_notifications": "visualizar_notificacao" in permission_codes,
            "can_manage_stock_alerts": "gerenciar_alerta_estoque" in permission_codes,
            "can_view_staff": "visualizar_funcionario" in permission_codes,
            "can_view_roles": "visualizar_role" in permission_codes,
            "can_view_permissions": "visualizar_permission" in permission_codes,
            "can_view_coupons": "visualizar_cupom" in permission_codes,
            "can_view_advance": "visualizar_adiantamento" in permission_codes,
            "can_view_import_export": "visualizar_importacao_exportacao" in permission_codes,
            "can_view_settings": AcessoEmpresaService.possui_acesso_configuracoes({
                "permission_codes": permission_codes,
            }),
        }

    @app.context_processor
    def inject_user():
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()

            if user_id:
                auth_scope = get_auth_scope()

                if auth_scope == "platform":
                    owner = db.session.get(PlatformOwner, int(user_id))
                    return {
                        "current_user": None,
                        "current_platform_owner": owner,
                        "current_auth_scope": auth_scope,
                        "current_permission_codes": [],
                        "tenant_navigation_items": [],
                        "tenant_navigation_groups": [],
                        "has_permission": lambda *_args, **_kwargs: False,
                        "ui_flags": {},
                        "tenant_theme_config": {
                            "defaultMode": "modern",
                            "companyModes": {},
                            "storageKey": "oceanblue:empresa-visual-selecionada",
                        },
                        "current_visual_mode": "modern",
                    }

                funcionario = db.session.get(Funcionario, int(user_id))
                permission_codes = _get_permission_codes(funcionario)
                tenant_theme_config = _build_tenant_theme_config(funcionario) if funcionario else {
                    "defaultMode": "modern",
                    "companyModes": {},
                    "storageKey": "oceanblue:empresa-visual-selecionada",
                }
                ui_flags = _build_template_flags(permission_codes)
                navigation_items = _build_navigation(permission_codes, ui_flags)
                return {
                    "current_user": funcionario,
                    "current_platform_owner": None,
                    "current_auth_scope": auth_scope,
                    "current_permission_codes": sorted(permission_codes),
                    "tenant_navigation_items": navigation_items,
                    "tenant_navigation_groups": _build_navigation_groups(navigation_items),
                    "has_permission": lambda code: code in permission_codes,
                    "ui_flags": ui_flags,
                    "tenant_theme_config": tenant_theme_config,
                    "current_visual_mode": tenant_theme_config["defaultMode"],
                }

        except Exception:
            pass

        return {
            "current_user": None,
            "current_platform_owner": None,
            "current_auth_scope": None,
            "current_permission_codes": [],
            "tenant_navigation_items": [],
            "tenant_navigation_groups": [],
            "has_permission": lambda *_args, **_kwargs: False,
            "ui_flags": {},
            "tenant_theme_config": {
                "defaultMode": "modern",
                "companyModes": {},
                "storageKey": "oceanblue:empresa-visual-selecionada",
            },
            "current_visual_mode": "modern",
        }


def register_commands(app: Flask) -> None:
    from app.cli.alertas import register_alert_commands
    register_alert_commands(app)
    from app.cli.security import register_security_commands
    register_security_commands(app)
    @app.cli.command("seed")
    def seed_command():
        """Executa a carga inicial de dados do sistema."""
        run_seed()


def configure_logging(app: Flask) -> None:
    log_level = logging.DEBUG if app.debug else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    gunicorn_logger = logging.getLogger("gunicorn.error")

    if gunicorn_logger.handlers:
        app.logger.handlers = gunicorn_logger.handlers
    else:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        app.logger.handlers = [stream_handler]

    app.logger.setLevel(log_level)
    logging.getLogger().setLevel(log_level)


def create_app() -> Flask:
    config_class = get_config()
    config_class.validate_runtime()

    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

    if os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"}:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=int(os.getenv("PROXY_FIX_X_FOR", "1")),
            x_proto=int(os.getenv("PROXY_FIX_X_PROTO", "1")),
            x_host=int(os.getenv("PROXY_FIX_X_HOST", "1")),
            x_port=int(os.getenv("PROXY_FIX_X_PORT", "0")),
            x_prefix=int(os.getenv("PROXY_FIX_X_PREFIX", "0")),
        )

    configure_logging(app)

    register_extensions(app)
    register_errors(app)
    register_security_headers(app)
    register_blueprints(app)
    register_context_processors(app)
    register_commands(app)

    return app
