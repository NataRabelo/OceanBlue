from app.security.errors import public_error
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import permission_required, ui_permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.estoque_service import EstoqueService
from app.services.time_service import TimeService

estoque_bp = Blueprint("estoque", __name__)


@estoque_bp.route("/notificacoes/historico", methods=["GET"])
@permission_required("gerenciar_alerta_estoque")
def historico_alertas():
    from app.services.alerta_service import AlertaService
    try:
        tenant_id = get_jwt()["tenant_id"]
        escopo = AcessoEmpresaService.obter_escopo(int(get_jwt_identity()), tenant_id)
        empresa_id = request.args.get("empresa_id", type=int)
        return jsonify(success=True, data=AlertaService.historico(tenant_id, escopo, empresa_id))
    except Exception as error:
        return jsonify(success=False, message=public_error(error)), 400


@estoque_bp.route("/notificacoes/processar", methods=["POST"])
@permission_required("gerenciar_alerta_estoque")
def processar_alertas():
    from app.services.alerta_service import AlertaService
    try:
        tenant_id = get_jwt()["tenant_id"]
        escopo = AcessoEmpresaService.obter_escopo(int(get_jwt_identity()), tenant_id)
        data = request.get_json(silent=True) or {}
        empresa_id = int(data.get("empresa_id") or 0)
        return jsonify(success=True, data=AlertaService.rotina(tenant_id, empresa_id, escopo))
    except Exception as error:
        return jsonify(success=False, message=public_error(error)), 400


@estoque_bp.route("/notificacoes/<int:entrega_id>/retentar", methods=["POST"])
@permission_required("gerenciar_alerta_estoque")
def retentar_alerta(entrega_id):
    from app.services.alerta_service import AlertaService
    try:
        tenant_id = get_jwt()["tenant_id"]
        escopo = AcessoEmpresaService.obter_escopo(int(get_jwt_identity()), tenant_id)
        return jsonify(success=True, data=AlertaService.retentar(entrega_id, tenant_id, escopo))
    except Exception as error:
        return jsonify(success=False, message=public_error(error)), 400


def _serializar_movimento(item):
    return {
        "id": item.id,
        "empresa_id": item.empresa.id,
        "empresa_nome": item.empresa.nome_fantasia,
        "produto_id": item.produto.id,
        "produto_nome": item.produto.nome,
        "funcionario_nome": item.funcionario.nome if item.funcionario else None,
        "tipo_movimento": item.tipo_movimento.value,
        "motivo": item.motivo.value,
        "quantidade": int(item.quantidade),
        "valor_unitario": str(item.valor_unitario) if item.valor_unitario is not None else None,
        "valor_total": str(item.valor_total) if item.valor_total is not None else None,
        "observacao": item.observacao,
        "venda_id": item.venda_id,
        "item_venda_id": getattr(item, "item_venda_id", None),
        "movimento_origem_id": getattr(item, "movimento_origem_id", None),
        "revertido": bool(getattr(item, "revertido", False)),
        "cancelado_em": TimeService.serialize_utc_iso(getattr(item, "cancelado_em", None)),
        "cancelado_por_nome": item.cancelado_por.nome if getattr(item, "cancelado_por", None) else None,
        "motivo_cancelamento": getattr(item, "motivo_cancelamento", None),
        "origem": "VALE" if getattr(item, "adiantamentos", None) else ("PDV" if item.venda_id else "MANUAL"),
        "data_movimento": TimeService.serialize_utc_iso(item.data_movimento),
    }


@estoque_bp.route("/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_produto")
def pagina():
    return render_template("modulos/estoque/estoque.html")


@estoque_bp.route("/alertas/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_notificacao")
def pagina_alertas():
    return render_template("modulos/estoque/estoque_alertas.html")


@estoque_bp.route("/indicadores/view", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_produto")
def pagina_indicadores():
    return render_template("modulos/estoque/estoque_indicadores.html")


@estoque_bp.route("/", methods=["GET"])
@permission_required("visualizar_produto")
def listar_saldos():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        registros = EstoqueService.listar_saldos(tenant_id, escopo, empresa_id=empresa_id)

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
                    "estoque_atual": int(item.estoque_atual),
                    "estoque_minimo": int(item.estoque_minimo),
                    "valor_compra": str(item.valor_compra),
                    "valor_venda": str(item.valor_venda),
                    "data_validade": item.data_validade.isoformat() if item.data_validade else None,
                    "ativo": item.ativo,
                    "abaixo_minimo": item.estoque_atual <= item.estoque_minimo,
                }
                for item in registros
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@estoque_bp.route("/movimentos", methods=["GET"])
@permission_required("visualizar_produto")
def listar_movimentos():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        limite = request.args.get("limite", default=50, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        movimentos = EstoqueService.listar_movimentos(tenant_id, escopo, empresa_id=empresa_id, limite=limite)

        return jsonify({
            "success": True,
            "data": [_serializar_movimento(item) for item in movimentos]
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@estoque_bp.route("/auxiliares", methods=["GET"])
@permission_required("visualizar_produto")
def auxiliares():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = EstoqueService.listar_auxiliares(tenant_id, escopo)

        return jsonify({
            "success": True,
            "data": dados
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@estoque_bp.route("/notificacoes", methods=["GET"])
@permission_required("visualizar_notificacao")
def listar_notificacoes():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        dias_vencimento = request.args.get("dias_vencimento", default=30, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = EstoqueService.listar_notificacoes(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            dias_vencimento=dias_vencimento,
        )

        return jsonify({
            "success": True,
            "data": dados
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@estoque_bp.route("/notificacoes/popup", methods=["GET"])
@permission_required("visualizar_notificacao")
def popup_notificacoes():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = EstoqueService.obter_popup_alertas(tenant_id, escopo)

        return jsonify({
            "success": True,
            "data": dados
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 500


@estoque_bp.route("/notificacoes/configuracao", methods=["GET"])
@permission_required("gerenciar_alerta_estoque")
def obter_configuracao_alerta():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = EstoqueService.obter_configuracao_alerta(tenant_id, escopo)

        return jsonify({
            "success": True,
            "data": dados
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@estoque_bp.route("/notificacoes/configuracao", methods=["PUT"])
@permission_required("gerenciar_alerta_estoque")
def atualizar_configuracao_alerta():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        dados = EstoqueService.atualizar_configuracao_alerta(data, tenant_id, escopo)

        return jsonify({
            "success": True,
            "message": "Configuracoes de alerta atualizadas com sucesso.",
            "data": dados
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@estoque_bp.route("/indicadores/produtos-mais-vendidos", methods=["GET"])
@permission_required("visualizar_produto")
def listar_produtos_mais_vendidos():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        empresa_id = request.args.get("empresa_id", type=int)
        periodo = request.args.get("periodo", default="mes", type=str)
        data_inicio = request.args.get("data_inicio", type=str)
        data_fim = request.args.get("data_fim", type=str)
        limite = request.args.get("limite", default=12, type=int)
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        dados = EstoqueService.listar_produtos_mais_vendidos(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            periodo=periodo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limite=limite,
        )

        return jsonify({
            "success": True,
            "data": dados
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@estoque_bp.route("/movimentos/manual", methods=["POST"])
@permission_required("editar_produto")
def criar_movimento_manual():
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        movimento = EstoqueService.registrar_movimentacao_manual(data, tenant_id, escopo, funcionario_id)

        return jsonify({
            "success": True,
            "message": "Movimentacao registrada com sucesso.",
            "data": _serializar_movimento(movimento)
        }), 201
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400


@estoque_bp.route("/movimentos/<int:movimento_id>/cancelar", methods=["POST"])
@permission_required("cancelar_movimentacao_estoque")
def cancelar_movimento(movimento_id):
    try:
        tenant_id = get_jwt().get("tenant_id")
        funcionario_id = int(get_jwt_identity())
        escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        data = request.get_json(silent=True) or {}
        movimento = EstoqueService.cancelar_movimento(movimento_id, data, tenant_id, escopo, funcionario_id)

        return jsonify({
            "success": True,
            "message": "Movimentacao cancelada com sucesso.",
            "data": _serializar_movimento(movimento),
        })
    except Exception as e:
        return jsonify({"success": False, "message": public_error(e)}), 400
