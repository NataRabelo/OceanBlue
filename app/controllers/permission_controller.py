from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.permission_service import PermissionService

permission_bp = Blueprint("permission", __name__)


@permission_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_permission")
def pagina():
    return render_template("modulos/permission/permission.html")


@permission_bp.route("/", methods=["GET"])
@permission_required("visualizar_permission")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        permissions = PermissionService.listar(tenant_id)

        return jsonify({
            "success": True,
            "data": [
                {
                    "id": permission.id,
                    "nome": permission.nome,
                    "codigo": permission.codigo,
                    "descricao": permission.descricao,
                    "ativo": permission.ativo
                }
                for permission in permissions
            ]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@permission_bp.route("/", methods=["POST"])
@permission_required("criar_permission")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        permission = PermissionService.criar(data, tenant_id)

        return jsonify({
            "success": True,
            "data": {
                "id": permission.id,
                "nome": permission.nome,
                "codigo": permission.codigo,
                "descricao": permission.descricao,
                "ativo": permission.ativo
            }
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@permission_bp.route("/<int:permission_id>", methods=["PUT"])
@permission_required("editar_permission")
def atualizar(permission_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        permission = PermissionService.atualizar(permission_id, data, tenant_id)

        return jsonify({
            "success": True,
            "data": {
                "id": permission.id,
                "nome": permission.nome,
                "codigo": permission.codigo,
                "descricao": permission.descricao,
                "ativo": permission.ativo
            },
            "message": "Permission atualizada com sucesso."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@permission_bp.route("/<int:permission_id>", methods=["DELETE"])
@permission_required("excluir_permission")
def deletar(permission_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        PermissionService.deletar(permission_id, tenant_id)
        return jsonify({"success": True, "message": "Permission excluida com sucesso."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
