from app.controllers.adiantamento_controller import adiantamento_bp
from app.controllers.auth_controller import auth_bp
from app.controllers.boleto_controller import boleto_bp
from app.controllers.categoria_controller import categoria_bp
from app.controllers.cliente_controller import cliente_bp
from app.controllers.cupom_controller import cupom_bp
from app.controllers.estoque_controller import estoque_bp
from app.controllers.fiscal_controller import fiscal_bp
from app.controllers.financeiro_controller import financeiro_bp
from app.controllers.funcionario_controller import funcionario_bp
from app.controllers.import_export_controller import import_export_bp
from app.controllers.main_controller import main_bp
from app.controllers.permission_controller import permission_bp
from app.controllers.pdv_controller import pdv_bp
from app.controllers.platform_controller import platform_bp
from app.controllers.produto_controller import produto_bp
from app.controllers.role_controller import role_bp
from app.health import health_bp
from app.controllers.ciclos_controller import ciclos_bp


def register_blueprints(app):
    app.register_blueprint(ciclos_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(platform_bp)
    app.register_blueprint(produto_bp, url_prefix="/api/produtos")
    app.register_blueprint(cliente_bp, url_prefix="/api/clientes")
    app.register_blueprint(cupom_bp, url_prefix="/api/cupons")
    app.register_blueprint(adiantamento_bp, url_prefix="/api/adiantamentos")
    app.register_blueprint(estoque_bp, url_prefix="/api/estoque")
    app.register_blueprint(pdv_bp, url_prefix="/api/pdv")
    app.register_blueprint(financeiro_bp, url_prefix="/api/financeiro")
    app.register_blueprint(boleto_bp, url_prefix="/api/financeiro/boletos")
    app.register_blueprint(fiscal_bp, url_prefix="/api/fiscal")
    app.register_blueprint(import_export_bp, url_prefix="/api/importacao-exportacao")
    app.register_blueprint(categoria_bp, url_prefix="/api/categorias")
    app.register_blueprint(funcionario_bp, url_prefix="/api/funcionarios")
    app.register_blueprint(role_bp, url_prefix="/api/roles")
    app.register_blueprint(permission_bp, url_prefix="/api/permissions")
