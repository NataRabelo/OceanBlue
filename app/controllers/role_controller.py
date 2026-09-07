from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.security.permissions import build_permission_groups, normalize_permission_codes
from app.services.permission_service import PermissionService
from app.services.role_service import RoleService

role_bp = Blueprint("role", __name__)


@role_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_role")
def pagina():
    return render_template("modulos/role/role.html")


@role_bp.route("/", methods=["GET"])
@permission_required("visualizar_role")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        roles = RoleService.listar(tenant_id)

        def _serializar_permissions(role):
            permissions = [link.permission for link in role.permissions_links if link.permission]
            effective_codes = normalize_permission_codes(
                permission.codigo
                for permission in permissions
            )
            filtered_permissions = [
                permission
                for permission in permissions
                if permission.codigo in effective_codes
            ]
            return filtered_permissions

        serialized_roles = []
        for role in roles:
            filtered_permissions = _serializar_permissions(role)
            serialized_roles.append({
                "id": role.id,
                "nome": role.nome,
                "codigo": role.codigo,
                "descricao": role.descricao,
                "ativo": role.ativo,
                "permission_ids": [permission.id for permission in filtered_permissions],
                "permissions_text": " ".join(
                    [
                        f"{permission.nome or ''} {permission.codigo or ''}".strip()
                        for permission in filtered_permissions
                    ]
                ),
                "permissions": [
                    {
                        "id": permission.id,
                        "nome": permission.nome,
                        "codigo": permission.codigo,
                    }
                    for permission in filtered_permissions
                ],
                "permissions_grouped": build_permission_groups(filtered_permissions),
            })

        return jsonify({
            "success": True,
            "data": serialized_roles
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@role_bp.route("/permissions-disponiveis", methods=["GET"])
@permission_required("visualizar_role")
def listar_permissions_disponiveis():
    try:
        tenant_id = get_jwt().get("tenant_id")
        permission_groups = PermissionService.listar_agrupadas(tenant_id)

        return jsonify({
            "success": True,
            "data": permission_groups
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@role_bp.route("/", methods=["POST"])
@permission_required("criar_role")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        role = RoleService.criar(data, tenant_id)

        return jsonify({
            "success": True,
            "data": {
                "id": role.id,
                "nome": role.nome,
                "codigo": role.codigo,
                "descricao": role.descricao,
                "ativo": role.ativo
            }
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@role_bp.route("/<int:role_id>", methods=["PUT"])
@permission_required("editar_role")
def atualizar(role_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        role = RoleService.atualizar(role_id, data, tenant_id)

        return jsonify({
            "success": True,
            "data": {
                "id": role.id,
                "nome": role.nome,
                "codigo": role.codigo,
                "descricao": role.descricao,
                "ativo": role.ativo
            },
            "message": "Role atualizada com sucesso."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@role_bp.route("/<int:role_id>", methods=["DELETE"])
@permission_required("excluir_role")
def deletar(role_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        RoleService.deletar(role_id, tenant_id)
        return jsonify({"success": True, "message": "Role excluida com sucesso."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
