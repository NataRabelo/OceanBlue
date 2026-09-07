from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.funcionario_service import FuncionarioService

funcionario_bp = Blueprint("funcionario", __name__)


@funcionario_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_funcionario")
def pagina():
    return render_template("modulos/funcionario/funcionario.html")


@funcionario_bp.route("/empresas-disponiveis", methods=["GET"])
@permission_required("visualizar_funcionario")
def listar_empresas_disponiveis():
    try:
        tenant_id = get_jwt().get("tenant_id")
        empresas = FuncionarioService.listar_empresas(tenant_id)

        return jsonify({
            "success": True,
            "data": [
                {
                    "id": empresa.id,
                    "nome_fantasia": empresa.nome_fantasia,
                    "razao_social": empresa.razao_social
                }
                for empresa in empresas
            ]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@funcionario_bp.route("/roles-disponiveis", methods=["GET"])
@permission_required("visualizar_funcionario")
def listar_roles_disponiveis():
    try:
        tenant_id = get_jwt().get("tenant_id")
        roles = FuncionarioService.listar_roles(tenant_id)

        return jsonify({
            "success": True,
            "data": [
                {
                    "id": role.id,
                    "nome": role.nome,
                    "codigo": role.codigo,
                    "descricao": role.descricao
                }
                for role in roles
            ]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@funcionario_bp.route("/", methods=["GET"])
@permission_required("visualizar_funcionario")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionarios = FuncionarioService.listar(tenant_id)
        return jsonify({"success": True, "data": funcionarios}), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@funcionario_bp.route("/", methods=["POST"])
@permission_required("criar_funcionario")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        funcionario = FuncionarioService.criar(data, tenant_id)

        return jsonify({
            "success": True,
            "data": {
                "id": funcionario.id,
                "funcionario_id": funcionario.funcionario.id,
                "empresa_id": funcionario.empresa.id,
                "empresa_nome": funcionario.empresa.nome_fantasia,
                "role_id": funcionario.funcionario.role.id if funcionario.funcionario.role else None,
                "role_nome": funcionario.funcionario.role.nome if funcionario.funcionario.role else "",
                "nome": funcionario.funcionario.nome,
                "cpf": funcionario.funcionario.cpf,
                "usuario": funcionario.funcionario.usuario,
                "salario": str(funcionario.funcionario.salario),
                "meta": str(funcionario.funcionario.meta),
                "ativo": funcionario.funcionario.ativo
            },
            "message": "Funcionario cadastrado com sucesso."
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@funcionario_bp.route("/<int:funcionario_empresa_id>", methods=["PUT"])
@permission_required("editar_funcionario")
def atualizar(funcionario_empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        funcionario = FuncionarioService.atualizar(funcionario_empresa_id, data, tenant_id)

        return jsonify({
            "success": True,
            "data": {
                "id": funcionario.id,
                "funcionario_id": funcionario.funcionario.id,
                "empresa_id": funcionario.empresa.id,
                "empresa_nome": funcionario.empresa.nome_fantasia,
                "role_id": funcionario.funcionario.role.id if funcionario.funcionario.role else None,
                "role_nome": funcionario.funcionario.role.nome if funcionario.funcionario.role else "",
                "nome": funcionario.funcionario.nome,
                "cpf": funcionario.funcionario.cpf,
                "usuario": funcionario.funcionario.usuario,
                "salario": str(funcionario.funcionario.salario),
                "meta": str(funcionario.funcionario.meta),
                "ativo": funcionario.funcionario.ativo
            },
            "message": "Funcionario atualizado com sucesso."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@funcionario_bp.route("/<int:funcionario_empresa_id>", methods=["DELETE"])
@permission_required("excluir_funcionario")
def deletar(funcionario_empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        FuncionarioService.deletar(funcionario_empresa_id, tenant_id)

        return jsonify({
            "success": True,
            "message": "Funcionario excluido com sucesso."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
