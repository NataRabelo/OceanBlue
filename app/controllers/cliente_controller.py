from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.cliente_service import ClienteService

cliente_bp = Blueprint("cliente", __name__)


@cliente_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_cliente")
def pagina():
    return render_template("modulos/cliente/cliente.html")


@cliente_bp.route("/auxiliares", methods=["GET"])
@permission_required("visualizar_cliente")
def auxiliares():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = ClienteService.listar_auxiliares(tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/", methods=["GET"])
@permission_required("visualizar_cliente")
def listar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        busca = request.args.get("busca", type=str)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = ClienteService.listar(tenant_id, escopo, busca=busca)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/", methods=["POST"])
@permission_required("criar_cliente")
def criar():
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        cliente = ClienteService.criar(data, tenant_id)
        return jsonify({
            "success": True,
            "message": "Cliente cadastrado com sucesso.",
            "data": ClienteService.serializar_cliente(cliente),
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/<int:cliente_id>", methods=["PUT"])
@permission_required("editar_cliente")
def atualizar(cliente_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        data = request.get_json(silent=True) or {}
        cliente = ClienteService.atualizar(cliente_id, data, tenant_id)
        return jsonify({
            "success": True,
            "message": "Cliente atualizado com sucesso.",
            "data": ClienteService.serializar_cliente(cliente),
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/<int:cliente_id>", methods=["DELETE"])
@permission_required("excluir_cliente")
def deletar(cliente_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        ClienteService.deletar(cliente_id, tenant_id)
        return jsonify({"success": True, "message": "Cliente inativado com sucesso."})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/<int:cliente_id>/carteira", methods=["GET"])
@permission_required("visualizar_cliente")
def obter_carteira(cliente_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = ClienteService.obter_carteira(cliente_id, tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/<int:cliente_id>/historico-vendas", methods=["GET"])
@permission_required("visualizar_cliente")
def historico_vendas(cliente_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        limite = request.args.get("limite", default=100, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = ClienteService.obter_historico_vendas(cliente_id, tenant_id, escopo, limite=limite)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/<int:cliente_id>/mensagens", methods=["GET"])
@permission_required("visualizar_cliente")
def listar_mensagens(cliente_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        dados = ClienteService.listar_mensagens(cliente_id, tenant_id)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/<int:cliente_id>/mensagens", methods=["POST"])
@permission_required("enviar_mensagem_cliente")
def enviar_mensagem(cliente_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        mensagem = ClienteService.enviar_mensagem(cliente_id, data, tenant_id, escopo, funcionario_id)
        return jsonify({
            "success": True,
            "message": "Mensagem registrada na fila; entrega ainda nao confirmada.",
            "data": mensagem,
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/mensagens/disparo-coletivo", methods=["POST"])
@permission_required("enviar_mensagem_cliente")
def enviar_mensagem_coletiva():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        resumo = ClienteService.enviar_mensagem_coletiva(data, tenant_id, escopo, funcionario_id)
        return jsonify({
            "success": True,
            "message": (
                "Fila coletiva registrada. "
                f"{resumo['enfileirados']} pendentes, {resumo['ignorados']} ignorados e {resumo['erros']} com erro."
            ),
            "data": resumo,
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/configuracoes", methods=["GET"])
@permission_required("gerenciar_configuracao_cliente")
def listar_configuracoes():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = ClienteService.listar_configuracoes_empresa(tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/configuracoes/<int:empresa_id>", methods=["GET"])
@permission_required("gerenciar_configuracao_cliente")
def obter_configuracao(empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = ClienteService.obter_configuracao_empresa(empresa_id, tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/configuracoes/<int:empresa_id>", methods=["PUT"])
@permission_required("gerenciar_configuracao_cliente")
def atualizar_configuracao(empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        dados = ClienteService.atualizar_configuracao_empresa(empresa_id, data, tenant_id, escopo)
        return jsonify({
            "success": True,
            "message": "Configuracoes atualizadas com sucesso.",
            "data": dados,
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@cliente_bp.route("/configuracoes/<int:empresa_id>/testar", methods=["POST"])
@permission_required("gerenciar_configuracao_cliente")
def testar_configuracao(empresa_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        dados = ClienteService.testar_configuracao_empresa(empresa_id, data, tenant_id, escopo, funcionario_id)
        return jsonify({
            "success": True,
            "message": "Teste de comunicacao executado com sucesso.",
            "data": dados,
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
