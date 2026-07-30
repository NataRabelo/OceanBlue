from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.boleto_service import BoletoService
from app.services.banco_emissor_service import BancoEmissorService

boleto_bp = Blueprint("boleto", __name__)


@boleto_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_financeiro")
def pagina():
    return render_template("modulos/financeiro/boletos.html")


@boleto_bp.route("/bancos-emissores", methods=["GET"])
@jwt_required()
@permission_required("visualizar_financeiro")
def listar_bancos_emissores():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        empresa_id = request.args.get("empresa_id", type=int)
        ativo = request.args.get("ativo", default=None, type=lambda v: v.lower() == "true") if request.args.get("ativo") is not None else None
        dados = BoletoService.listar_bancos_emissores(tenant_id, escopo, empresa_id=empresa_id, ativo=ativo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/configuracoes-parcelamento", methods=["GET"])
@jwt_required()
@permission_required("visualizar_financeiro")
def listar_configuracoes_parcelamento():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        empresa_id = request.args.get("empresa_id", type=int)
        ativo = request.args.get("ativo", default=None, type=lambda v: v.lower() == "true") if request.args.get("ativo") is not None else None
        dados = BoletoService.listar_configuracoes_parcelamento(tenant_id, escopo, empresa_id=empresa_id, ativo=ativo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/regras-juros-multa", methods=["GET"])
@jwt_required()
@permission_required("visualizar_financeiro")
def listar_regras_juros_multa():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        empresa_id = request.args.get("empresa_id", type=int)
        dados = BoletoService.listar_regras_juros_multa(tenant_id, escopo, empresa_id=empresa_id)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("", methods=["GET"])
@jwt_required()
@permission_required("visualizar_financeiro")
def listar_boletos():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        empresa_id = request.args.get("empresa_id", type=int)
        status = request.args.get("status", type=str)
        banco_emissor_id = request.args.get("banco_emissor_id", type=int)
        limite = request.args.get("limite", default=100, type=int)
        dados = BoletoService.listar_boletos(tenant_id, escopo, empresa_id=empresa_id, status=status, banco_emissor_id=banco_emissor_id, limite=limite)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def criar_boleto():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        boleto = BoletoService.criar_boleto(data, tenant_id, escopo, funcionario_id)
        return jsonify({"success": True, "message": "Boleto criado com sucesso.", "data": boleto}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/<int:boleto_id>", methods=["GET"])
@jwt_required()
@permission_required("visualizar_financeiro")
def buscar_boleto(boleto_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        empresa_id = request.args.get("empresa_id", type=int)
        boleto = BoletoService.buscar_boleto(tenant_id, escopo, boleto_id, empresa_id=empresa_id)
        return jsonify({"success": True, "data": boleto})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/<int:boleto_id>/baixar", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def baixar_boleto(boleto_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        boleto = BoletoService.baixar_boleto(tenant_id, escopo, boleto_id, data, funcionario_id)
        return jsonify({"success": True, "message": "Baixa registrada.", "data": boleto})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/configuracao-asaas", methods=["GET"])
@jwt_required()
@permission_required("visualizar_financeiro")
def obter_configuracao_asaas():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        empresa_id = request.args.get("empresa_id", type=int)
        if not empresa_id:
            return jsonify({"success": False, "message": "Informe a empresa para consultar Asaas."}), 400
        dados = BoletoService.obter_configuracao_asaas(tenant_id, escopo, empresa_id)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/configuracao-asaas/<int:empresa_id>", methods=["PUT"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def atualizar_configuracao_asaas(empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        dados = BoletoService.atualizar_configuracao_asaas(tenant_id, escopo, empresa_id, data)
        return jsonify({"success": True, "message": "Configuracao Asaas atualizada.", "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/<int:boleto_id>/registrar", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def registrar_boleto(boleto_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        boleto = BoletoService.registrar_boleto(tenant_id, escopo, boleto_id, funcionario_id)
        return jsonify({"success": True, "message": "Registro bancario homologado processado.", "data": boleto})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/<int:boleto_id>/consultar-status", methods=["POST"])
@jwt_required()
@permission_required("visualizar_financeiro")
def consultar_status_boleto(boleto_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        boleto = BoletoService.consultar_status_bancario(tenant_id, escopo, boleto_id, funcionario_id)
        return jsonify({"success": True, "message": "Status bancario consultado.", "data": boleto})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/<int:boleto_id>/retorno", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def processar_retorno_boleto(boleto_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        boleto = BoletoService.processar_retorno_bancario(tenant_id, escopo, boleto_id, data, funcionario_id)
        return jsonify({"success": True, "message": "Retorno bancario processado de forma idempotente.", "data": boleto})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/webhook/asaas/<int:tenant_id>/<int:empresa_id>", methods=["POST"])
def webhook_asaas(tenant_id, empresa_id):
    try:
        from app.models.db import ConfiguracaoAsaasEmpresa, Boleto
        from app.security.field_crypto import FieldCrypto

        config = ConfiguracaoAsaasEmpresa.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id, ativo=True).first()
        if not config or not config.webhook_ativo:
            return jsonify({"success": False, "message": "Webhook Asaas nao configurado."}), 404
        expected = FieldCrypto.decrypt(config.webhook_auth_token)
        received = request.headers.get("asaas-access-token")
        if expected and received != expected:
            return jsonify({"success": False, "message": "Webhook Asaas nao autorizado."}), 401

        payload = request.get_json(silent=True) or {}
        payment = payload.get("payment") or {}
        payment_id = payment.get("id")
        boleto = Boleto.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id, registro_bancario_id=payment_id).first()
        if not boleto:
            return jsonify({"success": True, "message": "Evento recebido, cobranca nao vinculada."})
        escopo = {"empresa_ids": [empresa_id], "permission_codes": set(), "is_admin": False}
        dados = BoletoService.processar_retorno_bancario(tenant_id, escopo, boleto.id, payload, funcionario_id=None)
        return jsonify({"success": True, "message": "Webhook Asaas processado.", "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/<int:boleto_id>/recalcular-juros", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def recalcular_juros(boleto_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        boleto = BoletoService.recalcular_juros_multa(tenant_id, escopo, boleto_id, data_referencia=data.get("data_referencia"), funcionario_id=funcionario_id)
        return jsonify({"success": True, "message": "Juros e multa recalculados.", "data": boleto})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


# ============= CONFIGURAÇÃO DE BANCOS EMISSORES =============

@boleto_bp.route("/bancos-emissores", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def criar_banco_emissor():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        banco = BancoEmissorService.criar_banco_emissor(data, tenant_id, escopo, funcionario_id)
        return jsonify({"success": True, "message": "Banco emissor criado com sucesso.", "data": banco}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/configuracoes-parcelamento", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def criar_configuracao_parcelamento():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        config = BancoEmissorService.criar_configuracao_parcelamento(data, tenant_id, escopo)
        return jsonify({"success": True, "message": "Configuração de parcelamento criada com sucesso.", "data": config}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@boleto_bp.route("/regras-juros-multa", methods=["POST"])
@jwt_required()
@permission_required("criar_lancamento_financeiro")
def criar_regra_juros_multa():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        regra = BancoEmissorService.criar_regra_juros_multa(data, tenant_id, escopo)
        return jsonify({"success": True, "message": "Regra de juros e multa criada com sucesso.", "data": regra}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
