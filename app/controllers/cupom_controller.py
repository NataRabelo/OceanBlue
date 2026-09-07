from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.cupom_service import CupomService

cupom_bp = Blueprint("cupom", __name__)


@cupom_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_cupom")
def pagina():
    return render_template("modulos/cupom/cupom.html")


@cupom_bp.route("/", methods=["GET"])
@permission_required("visualizar_cupom")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        return jsonify({"success": True, "data": CupomService.listar(tenant_id)})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@cupom_bp.route("/", methods=["POST"])
@permission_required("criar_cupom")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        cupom = CupomService.criar(data, tenant_id, funcionario_id)
        return jsonify({
            "success": True,
            "message": "Cupom cadastrado com sucesso.",
            "data": CupomService.serializar(cupom),
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cupom_bp.route("/<int:cupom_id>", methods=["PUT"])
@permission_required("editar_cupom")
def atualizar(cupom_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        cupom = CupomService.atualizar(cupom_id, data, tenant_id)
        return jsonify({
            "success": True,
            "message": "Cupom atualizado com sucesso.",
            "data": CupomService.serializar(cupom),
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cupom_bp.route("/<int:cupom_id>", methods=["DELETE"])
@permission_required("excluir_cupom")
def deletar(cupom_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        CupomService.deletar(cupom_id, tenant_id)
        return jsonify({"success": True, "message": "Cupom excluido com sucesso."})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
