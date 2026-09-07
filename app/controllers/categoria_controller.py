from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.categoria_service import CategoriaService

categoria_bp = Blueprint("categoria", __name__)


@categoria_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_categoria")
def pagina():
    return render_template("modulos/categoria/categoria.html")


@categoria_bp.route("/", methods=["GET"])
@permission_required("visualizar_categoria")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        categorias = CategoriaService.listar(tenant_id, escopo)

        return jsonify({
            "success": True,
            "data": [
                {"id": categoria.id, "nome": categoria.nome, "descricao": categoria.descricao}
                for categoria in categorias
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@categoria_bp.route("/", methods=["POST"])
@permission_required("criar_categoria")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        categoria = CategoriaService.criar(data, tenant_id)

        return jsonify({
            "success": True,
            "data": {
                "id": categoria.id,
                "nome": categoria.nome,
                "descricao": categoria.descricao
            }
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@categoria_bp.route("/<int:categoria_id>", methods=["PUT"])
@permission_required("editar_categoria")
def atualizar(categoria_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        CategoriaService.atualizar(categoria_id, data, tenant_id)

        return jsonify({"success": True, "message": "Atualizado com sucesso"})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@categoria_bp.route("/<int:categoria_id>", methods=["DELETE"])
@permission_required("excluir_categoria")
def deletar(categoria_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        CategoriaService.deletar(categoria_id, tenant_id)

        return jsonify({"success": True, "message": "Deletado com sucesso"})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
