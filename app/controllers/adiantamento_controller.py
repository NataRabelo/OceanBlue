from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.adiantamento_service import AdiantamentoService

adiantamento_bp = Blueprint("adiantamento", __name__)


@adiantamento_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_adiantamento")
def pagina():
    return render_template("modulos/adiantamento/adiantamento.html")


@adiantamento_bp.route("/auxiliares", methods=["GET"])
@permission_required("visualizar_adiantamento")
def auxiliares():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = AdiantamentoService.listar_auxiliares(tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@adiantamento_bp.route("/", methods=["GET"])
@permission_required("visualizar_adiantamento")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        funcionario_filtro_id = request.args.get("funcionario_id", type=int)
        competencia = request.args.get("competencia", type=str)
        limite = request.args.get("limite", default=100, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = AdiantamentoService.listar(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            funcionario_id=funcionario_filtro_id,
            competencia=competencia,
            limite=limite,
        )
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@adiantamento_bp.route("/resumo", methods=["GET"])
@permission_required("visualizar_adiantamento")
def resumo():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        competencia = request.args.get("competencia", type=str)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = AdiantamentoService.obter_resumo_folha(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            competencia=competencia,
        )
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@adiantamento_bp.route("/", methods=["POST"])
@permission_required("criar_adiantamento")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        registro = AdiantamentoService.criar(data, tenant_id, escopo, funcionario_id)

        return jsonify({
            "success": True,
            "message": "Adiantamento registrado com sucesso.",
            "data": AdiantamentoService.serializar(registro),
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
