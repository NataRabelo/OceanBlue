from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from app.security.decorators import permission_required
from app.security.errors import public_error
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.adiantamento_ciclo_service import AdiantamentoCicloService
from app.services.cliente_privacidade_service import ClientePrivacidadeService
from app.services.financeiro_ciclo_service import FinanceiroCicloService
from app.services.mensagem_fila_service import MensagemFilaService
from app.services.money_service import positive_integer


ciclos_bp = Blueprint("ciclos", __name__)


def context():
    tenant = get_jwt()["tenant_id"]
    actor = int(get_jwt_identity())
    return {"tenant_id": tenant, "escopo": AcessoEmpresaService.obter_escopo(actor, tenant), "funcionario_id": actor}


def respond(operation):
    try:
        return jsonify(success=True, data=operation())
    except PermissionError as error:
        return jsonify(success=False, message=public_error(error)), 403
    except Exception as error:
        return jsonify(success=False, message=public_error(error)), 400


@ciclos_bp.get("/operacoes/view")
@permission_required("visualizar_financeiro")
def pagina():
    return render_template("modulos/financeiro/ciclos.html")


@ciclos_bp.post("/financeiro/lancamentos/<int:lancamento_id>/estornar")
@permission_required("estornar_financeiro")
def estornar(lancamento_id):
    return respond(lambda: FinanceiroCicloService.estornar(lancamento_id, request.get_json(silent=True) or {}, **context()))


@ciclos_bp.post("/financeiro/fechamentos/<int:fechamento_id>/ajustar")
@permission_required("reabrir_caixa")
def ajustar(fechamento_id):
    return respond(lambda: FinanceiroCicloService.ajustar_fechamento(fechamento_id, request.get_json(silent=True) or {}, **context()))


@ciclos_bp.get("/financeiro/conciliacao")
@permission_required("visualizar_relatorio_financeiro")
def conciliar():
    def operation():
        arguments = context()
        arguments.pop("funcionario_id")
        return FinanceiroCicloService.conciliar(**arguments, empresa_id=positive_integer(request.args.get("empresa_id"), "Empresa"),
            data_inicio=request.args.get("data_inicio"), data_fim=request.args.get("data_fim"))
    return respond(operation)


@ciclos_bp.post("/adiantamentos/solicitar")
@permission_required("criar_adiantamento")
def solicitar():
    return respond(lambda: AdiantamentoCicloService.solicitar(request.get_json(silent=True) or {}, **context()))


@ciclos_bp.post("/adiantamentos/<int:adiantamento_id>/transicao")
@permission_required("autorizar_adiantamento")
def transicionar(adiantamento_id):
    return respond(lambda: AdiantamentoCicloService.transicionar(adiantamento_id, request.get_json(silent=True) or {}, **context()))


@ciclos_bp.post("/clientes/<int:cliente_id>/consentimento")
@permission_required("gerenciar_privacidade_cliente")
def consentir(cliente_id):
    return respond(lambda: ClientePrivacidadeService.consentir(cliente_id, request.get_json(silent=True) or {}, **context()))


@ciclos_bp.get("/clientes/<int:cliente_id>/exportar")
@permission_required("gerenciar_privacidade_cliente")
def exportar(cliente_id):
    return respond(lambda: ClientePrivacidadeService.exportar(cliente_id, **context()))


@ciclos_bp.post("/clientes/<int:cliente_id>/anonimizar")
@permission_required("gerenciar_privacidade_cliente")
def anonimizar(cliente_id):
    return respond(lambda: ClientePrivacidadeService.anonimizar(cliente_id, request.get_json(silent=True) or {}, **context()))


@ciclos_bp.post("/clientes/mensagens/processar")
@permission_required("enviar_mensagem_cliente")
def processar():
    return respond(lambda: MensagemFilaService.processar(**context(), limite=(request.get_json(silent=True) or {}).get("limite", 100)))


@ciclos_bp.post("/clientes/cashback/expirar")
@permission_required("gerenciar_configuracao_cliente")
def expirar():
    def operation():
        arguments = context()
        if AcessoEmpresaService.filtrar_empresa_ids(arguments["escopo"]) is not None:
            raise PermissionError("Rotina global exige acesso a todas as empresas.")
        return ClientePrivacidadeService.expirar(arguments["tenant_id"])
    return respond(operation)
