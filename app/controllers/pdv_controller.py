from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.audit_service import AuditService
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.pdv_service import PdvService

pdv_bp = Blueprint("pdv", __name__)


@pdv_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_pdv")
def pagina():
    return render_template("modulos/pdv/pdv.html")


@pdv_bp.route("/auxiliares", methods=["GET"])
@permission_required("visualizar_pdv")
def auxiliares():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = PdvService.listar_auxiliares(tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@pdv_bp.route("/produtos", methods=["GET"])
@permission_required("visualizar_pdv")
def listar_produtos():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        busca = request.args.get("busca", type=str)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)

        if not empresa_id:
            return jsonify({"success": False, "message": "Informe a empresa para listar os produtos."}), 400

        dados = PdvService.listar_produtos(tenant_id, escopo, empresa_id, busca=busca)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@pdv_bp.route("/produtos/codigo-barras", methods=["GET"])
@permission_required("visualizar_pdv")
def buscar_produto_por_codigo_barras():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        codigo_barras = request.args.get("codigo_barras", type=str)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)

        if not empresa_id:
            return jsonify({"success": False, "message": "Informe a empresa para localizar o produto."}), 400

        dados = PdvService.buscar_produto_por_codigo_barras(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            codigo_barras=codigo_barras,
        )
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@pdv_bp.route("/vendas", methods=["GET"])
@permission_required("visualizar_pdv")
def listar_vendas():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        status = request.args.get("status", type=str)
        limite = request.args.get("limite", default=30, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)

        dados = PdvService.listar_vendas(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            status=status,
            limite=limite,
        )
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@pdv_bp.route("/vendas", methods=["POST"])
@permission_required("registrar_venda")
def criar_venda():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}

        venda = PdvService.criar_venda(data, tenant_id, escopo, funcionario_id)
        AuditService.registrar(
            "pdv.sale_created",
            tenant_id=tenant_id,
            empresa_id=venda.get("empresa_id"),
            actor_scope="tenant",
            actor_id=funcionario_id,
            entity_type="venda",
            entity_id=venda.get("id"),
            details=f"Total: {venda.get('total')}",
            commit=True,
        )
        return jsonify({
            "success": True,
            "message": "Venda registrada com sucesso.",
            "data": venda,
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@pdv_bp.route("/vendas/<int:venda_id>/cancelar", methods=["POST"])
@permission_required("cancelar_venda")
def cancelar_venda(venda_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}

        venda = PdvService.cancelar_venda(venda_id, data, tenant_id, escopo, funcionario_id)
        AuditService.registrar(
            "pdv.sale_cancelled",
            tenant_id=tenant_id,
            empresa_id=venda.get("empresa_id"),
            actor_scope="tenant",
            actor_id=funcionario_id,
            entity_type="venda",
            entity_id=venda.get("id"),
            details=(data.get("motivo") or "")[:500],
            commit=True,
        )
        return jsonify({
            "success": True,
            "message": "Venda cancelada com sucesso.",
            "data": venda,
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@pdv_bp.route("/vendas/<int:venda_id>/itens/<int:item_id>/cancelar", methods=["POST"])
@permission_required("cancelar_item_venda")
def cancelar_item_venda(venda_id, item_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}

        venda = PdvService.cancelar_item_venda(venda_id, item_id, data, tenant_id, escopo, funcionario_id)
        AuditService.registrar(
            "pdv.sale_item_cancelled",
            tenant_id=tenant_id,
            empresa_id=venda.get("empresa_id"),
            actor_scope="tenant",
            actor_id=funcionario_id,
            entity_type="item_venda",
            entity_id=item_id,
            details=(data.get("motivo") or "")[:500],
            commit=True,
        )
        return jsonify({
            "success": True,
            "message": "Item cancelado com sucesso.",
            "data": venda,
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@pdv_bp.route("/vendas/<int:venda_id>/comprovante", methods=["GET"])
@permission_required("visualizar_pdv")
def comprovante_venda(venda_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        venda = PdvService.obter_venda(venda_id, tenant_id, escopo)
        return render_template("relatorios/comprovante_venda.html", venda=venda)
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
