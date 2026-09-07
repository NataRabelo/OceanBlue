from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.adiantamento_service import AdiantamentoService
from app.services.financeiro_service import FinanceiroService

financeiro_bp = Blueprint("financeiro", __name__)


@financeiro_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_financeiro")
def pagina():
    return render_template("modulos/financeiro/financeiro.html")


@financeiro_bp.route("/lancamentos/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_financeiro")
def pagina_lancamentos():
    return render_template("modulos/financeiro/financeiro_lancamentos.html")


@financeiro_bp.route("/relatorios/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_relatorio_financeiro")
def pagina_relatorios():
    return render_template("modulos/financeiro/financeiro_relatorios.html")


@financeiro_bp.route("/auxiliares", methods=["GET"])
@permission_required("visualizar_financeiro")
def auxiliares():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = FinanceiroService.listar_auxiliares(tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@financeiro_bp.route("/dashboard", methods=["GET"])
@permission_required("visualizar_financeiro")
def dashboard():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        periodo_dias = request.args.get("periodo_dias", default=30, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = FinanceiroService.obter_dashboard(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            periodo_dias=periodo_dias,
        )
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@financeiro_bp.route("/lancamentos", methods=["GET"])
@permission_required("visualizar_financeiro")
def listar_lancamentos():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        tipo = request.args.get("tipo", type=str)
        data_inicio = request.args.get("data_inicio", type=str)
        data_fim = request.args.get("data_fim", type=str)
        limite = request.args.get("limite", default=100, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = FinanceiroService.listar_lancamentos(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limite=limite,
        )
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@financeiro_bp.route("/lancamentos", methods=["POST"])
@permission_required("criar_lancamento_financeiro")
def criar_lancamento():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        lancamento = FinanceiroService.criar_lancamento_manual(data, tenant_id, escopo, funcionario_id)

        return jsonify({
            "success": True,
            "message": "Lancamento financeiro registrado com sucesso.",
            "data": lancamento,
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@financeiro_bp.route("/fechamentos", methods=["GET"])
@permission_required("visualizar_financeiro")
def listar_fechamentos():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        limite = request.args.get("limite", default=30, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = FinanceiroService.listar_fechamentos(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            limite=limite,
        )
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@financeiro_bp.route("/fechamentos", methods=["POST"])
@permission_required("fechar_caixa")
def criar_fechamento():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        fechamento = FinanceiroService.criar_fechamento(data, tenant_id, escopo, funcionario_id)

        return jsonify({
            "success": True,
            "message": "Fechamento de caixa registrado com sucesso.",
            "data": fechamento,
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@financeiro_bp.route("/relatorios/fluxo-caixa/impressao", methods=["GET"])
@permission_required("visualizar_relatorio_financeiro")
def relatorio_fluxo_caixa_impressao():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        data_inicio = request.args.get("data_inicio", type=str)
        data_fim = request.args.get("data_fim", type=str)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        relatorio = FinanceiroService.obter_relatorio_fluxo_caixa(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        return render_template("relatorios/fluxo_caixa.html", relatorio=relatorio)
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@financeiro_bp.route("/relatorios/adiantamentos/impressao", methods=["GET"])
@permission_required("visualizar_relatorio_financeiro")
def relatorio_adiantamentos_impressao():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        competencia = request.args.get("competencia", type=str)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        registros = AdiantamentoService.listar(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            competencia=competencia,
            limite=500,
        )
        resumo = AdiantamentoService.obter_resumo_folha(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            competencia=competencia,
        )
        return render_template(
            "relatorios/adiantamentos.html",
            registros=registros,
            resumo=resumo,
        )
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@financeiro_bp.route("/relatorios/produtos-mais-vendidos/impressao", methods=["GET"])
@permission_required("visualizar_relatorio_financeiro")
def relatorio_produtos_mais_vendidos_impressao():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        data_inicio = request.args.get("data_inicio", type=str)
        data_fim = request.args.get("data_fim", type=str)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        relatorio = FinanceiroService.obter_relatorio_produtos_vendidos(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limite=100,
        )
        return render_template("relatorios/produtos_mais_vendidos.html", relatorio=relatorio)
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
