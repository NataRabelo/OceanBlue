from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.fiscal_service import FiscalService

fiscal_bp = Blueprint("fiscal", __name__)


@fiscal_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_fiscal")
def pagina():
    return render_template("modulos/fiscal/fiscal.html")


@fiscal_bp.route("/auxiliares", methods=["GET"])
@permission_required("visualizar_fiscal")
def auxiliares():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = FiscalService.listar_auxiliares(tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/configuracao", methods=["GET"])
@permission_required("visualizar_fiscal")
def obter_configuracao():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)

        if not empresa_id:
            return jsonify({"success": False, "message": "Informe a empresa para consultar a configuracao fiscal."}), 400

        dados = FiscalService.obter_configuracao(empresa_id, tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/configuracao/<int:empresa_id>", methods=["PUT"])
@permission_required("gerenciar_fiscal")
def atualizar_configuracao(empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        configuracao = FiscalService.atualizar_configuracao(empresa_id, data, tenant_id, escopo)
        return jsonify({
            "success": True,
            "message": "Configuracao fiscal atualizada com sucesso.",
            "data": configuracao,
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/notas", methods=["GET"])
@permission_required("visualizar_fiscal")
def listar_notas():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        limite = request.args.get("limite", default=50, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = FiscalService.listar_notas(tenant_id, escopo, limite=limite)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/notas/prevalidar", methods=["POST"])
@permission_required("visualizar_fiscal")
def prevalidar_venda():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        venda_id = data.get("venda_id")
        if not venda_id:
            return jsonify({"success": False, "message": "Informe a venda para prevalidar a preparacao fiscal."}), 400

        resultado = FiscalService.prevalidar_venda(int(venda_id), tenant_id, escopo)
        return jsonify({
            "success": True,
            "message": "Prevalidacao fiscal executada.",
            "data": resultado,
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/notas/emitir", methods=["POST"])
@permission_required("gerenciar_fiscal")
def emitir_nota_venda():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        venda_id = data.get("venda_id")
        if not venda_id:
            return jsonify({"success": False, "message": "Informe a venda para enviar a NFC-e em homologacao."}), 400

        nota = FiscalService.emitir_nota_venda(int(venda_id), tenant_id, escopo)
        return jsonify({
            "success": True,
            "message": "NFC-e processada pelo integrador fiscal de homologacao.",
            "data": nota,
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/notas/<int:nota_id>/xml", methods=["GET"])
@permission_required("visualizar_fiscal")
def baixar_xml_nota(nota_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        nota, path = FiscalService.obter_xml_nota(nota_id, tenant_id, escopo)
        download_name = f"nfce_{nota.serie}_{nota.numero}_{nota.chave_acesso}.xml"
        return send_file(
            path,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/xml",
        )
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/notas/<int:nota_id>/consultar", methods=["POST"])
@permission_required("visualizar_fiscal")
def consultar_nota(nota_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        nota = FiscalService.consultar_nota_venda(nota_id, tenant_id, escopo)
        return jsonify({"success": True, "message": "Status da NFC-e consultado.", "data": nota})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/notas/<int:nota_id>/cancelar", methods=["POST"])
@permission_required("gerenciar_fiscal")
def cancelar_nota(nota_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        nota = FiscalService.cancelar_nota_venda(nota_id, data.get("justificativa"), tenant_id, escopo)
        return jsonify({"success": True, "message": "Cancelamento de NFC-e processado.", "data": nota})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@fiscal_bp.route("/notas/<int:nota_id>/danfe", methods=["GET"])
@permission_required("visualizar_fiscal")
def baixar_danfe_nota(nota_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        nota, path = FiscalService.obter_danfe_nota(nota_id, tenant_id, escopo)
        download_name = f"danfe_nfce_{nota.serie}_{nota.numero}_{nota.chave_acesso}.html"
        return send_file(
            path,
            as_attachment=True,
            download_name=download_name,
            mimetype="text/html",
        )
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
