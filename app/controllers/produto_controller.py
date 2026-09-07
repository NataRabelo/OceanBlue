from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.produto_service import ProdutoService

produto_bp = Blueprint("produto", __name__)


@produto_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_produto")
def pagina():
    return render_template("modulos/produto/produto.html")


@produto_bp.route("/", methods=["GET"])
@permission_required("visualizar_produto")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        registros = ProdutoService.listar(tenant_id, escopo)

        return jsonify({
            "success": True,
            "data": [
                {
                    "id": item.id,
                    "produto_id": item.produto.id,
                    "empresa_id": item.empresa.id,
                    "empresa_nome": item.empresa.nome_fantasia,
                    "categoria_id": item.produto.categoria.id if item.produto.categoria else None,
                    "categoria_nome": item.produto.categoria.nome if item.produto.categoria else "",
                    "nome": item.produto.nome,
                    "descricao": item.produto.descricao,
                    "codigo_barras": item.produto.codigo_barras,
                    "possui_ncm": item.produto.possui_ncm,
                    "ncm": item.produto.ncm,
                    "estoque_atual": int(item.estoque_atual),
                    "estoque_minimo": int(item.estoque_minimo),
                    "valor_compra": str(item.valor_compra),
                    "valor_venda": str(item.valor_varejo),
                    "valor_varejo": str(item.valor_varejo),
                    "valor_atacado": str(item.valor_atacado),
                    "quantidade_minima_atacado": int(item.quantidade_minima_atacado),
                    "data_validade": item.data_validade.isoformat() if item.data_validade else None,
                    "ativo": item.ativo
                }
                for item in registros
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@produto_bp.route("/auxiliares", methods=["GET"])
@permission_required("visualizar_produto")
def auxiliares():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        categorias = ProdutoService.listar_categorias(tenant_id, escopo)
        empresas = ProdutoService.listar_empresas(tenant_id, escopo)

        return jsonify({
            "success": True,
            "data": {
                "categorias": [{"id": c.id, "nome": c.nome} for c in categorias],
                "empresas": [{"id": e.id, "nome": e.nome_fantasia} for e in empresas]
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@produto_bp.route("/", methods=["POST"])
@permission_required("criar_produto")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json() or {}
        item = ProdutoService.criar(data, tenant_id, escopo, funcionario_id)

        return jsonify({
            "success": True,
            "data": {
                "id": item.id,
                "produto_id": item.produto.id,
                "empresa_id": item.empresa.id,
                "empresa_nome": item.empresa.nome_fantasia,
                "categoria_id": item.produto.categoria.id if item.produto.categoria else None,
                "categoria_nome": item.produto.categoria.nome if item.produto.categoria else "",
                "nome": item.produto.nome,
                "descricao": item.produto.descricao,
                "codigo_barras": item.produto.codigo_barras,
                "possui_ncm": item.produto.possui_ncm,
                "ncm": item.produto.ncm,
                "estoque_atual": int(item.estoque_atual),
                "estoque_minimo": int(item.estoque_minimo),
                "valor_compra": str(item.valor_compra),
                "valor_venda": str(item.valor_varejo),
                "valor_varejo": str(item.valor_varejo),
                "valor_atacado": str(item.valor_atacado),
                "quantidade_minima_atacado": int(item.quantidade_minima_atacado),
                "data_validade": item.data_validade.isoformat() if item.data_validade else None,
                "ativo": item.ativo
            }
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@produto_bp.route("/<int:produto_empresa_id>", methods=["PUT"])
@permission_required("editar_produto")
def atualizar(produto_empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json() or {}
        item = ProdutoService.atualizar(produto_empresa_id, data, tenant_id, escopo)

        return jsonify({
            "success": True,
            "data": {
                "id": item.id,
                "produto_id": item.produto.id,
                "empresa_id": item.empresa.id,
                "empresa_nome": item.empresa.nome_fantasia,
                "categoria_id": item.produto.categoria.id if item.produto.categoria else None,
                "categoria_nome": item.produto.categoria.nome if item.produto.categoria else "",
                "nome": item.produto.nome,
                "descricao": item.produto.descricao,
                "codigo_barras": item.produto.codigo_barras,
                "possui_ncm": item.produto.possui_ncm,
                "ncm": item.produto.ncm,
                "estoque_atual": int(item.estoque_atual),
                "estoque_minimo": int(item.estoque_minimo),
                "valor_compra": str(item.valor_compra),
                "valor_venda": str(item.valor_varejo),
                "valor_varejo": str(item.valor_varejo),
                "valor_atacado": str(item.valor_atacado),
                "quantidade_minima_atacado": int(item.quantidade_minima_atacado),
                "data_validade": item.data_validade.isoformat() if item.data_validade else None,
                "ativo": item.ativo
            },
            "message": "Produto atualizado com sucesso."
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@produto_bp.route("/<int:produto_empresa_id>", methods=["DELETE"])
@permission_required("excluir_produto")
def deletar(produto_empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        ProdutoService.deletar(produto_empresa_id, tenant_id, escopo)

        return jsonify({"success": True, "message": "Produto deletado com sucesso."})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
