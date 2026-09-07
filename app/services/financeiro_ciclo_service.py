from decimal import Decimal
import json

from app.extensions import db
from app.models.db import AdiantamentoFuncionario, CategoriaFinanceira, FechamentoCaixa, LancamentoFinanceiro, TipoCategoriaFinanceira, TipoFinanceiro
from app.repositorys.financeiro_repository import FinanceiroRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.audit_service import AuditService
from app.services.financeiro_service import FinanceiroService
from app.services.idempotency_service import idempotent
from app.services.money_service import positive_integer
from app.services.time_service import TimeService
from app.services.transaction_service import atomic_operation


def motivo(data):
    value = data.get("motivo")
    if not isinstance(value, str) or not 5 <= len(value.strip()) <= 500:
        raise ValueError("Informe um motivo de 5 a 500 caracteres.")
    return value.strip()


def audit(action, record, actor, details):
    AuditService.registrar(action, tenant_id=record.tenant_id, empresa_id=record.empresa_id,
        actor_scope="tenant", actor_id=actor, entity_type=record.__tablename__, entity_id=record.id, details=json.dumps(details, ensure_ascii=True))


class FinanceiroCicloService:
    @staticmethod
    def reverter_origem(source, reason, actor):
        if source.revertido:
            return LancamentoFinanceiro.query.filter_by(tenant_id=source.tenant_id, lancamento_origem_id=source.id).one()
        tipo = TipoFinanceiro.SAIDA if source.tipo == TipoFinanceiro.ENTRADA else TipoFinanceiro.ENTRADA
        category = CategoriaFinanceira.query.filter_by(tenant_id=source.tenant_id,
            nome="Reversoes formais", tipo_categoria=TipoCategoriaFinanceira[tipo.name]).first()
        if category is None:
            category = CategoriaFinanceira(tenant_id=source.tenant_id, nome="Reversoes formais",
                tipo_categoria=TipoCategoriaFinanceira[tipo.name], ativo=True)
            db.session.add(category)
            db.session.flush()
        reversal = LancamentoFinanceiro(tenant_id=source.tenant_id, empresa_id=source.empresa_id,
            funcionario_id=actor, categoria_id=category.id, forma_pagamento_id=source.forma_pagamento_id,
            lancamento_origem_id=source.id, tipo=tipo, descricao=f"Reversao do lancamento {source.id}",
            valor=source.valor, data_competencia=TimeService.today_br(), observacao=reason)
        source.revertido = True
        db.session.add(reversal)
        db.session.flush()
        audit("FINANCEIRO_ESTORNO", source, actor, {"motivo": reason, "estorno_id": reversal.id, "valor": str(source.valor)})
        return reversal

    @staticmethod
    @atomic_operation
    @idempotent
    def estornar(lancamento_id, data, tenant_id, escopo, funcionario_id):
        source = LancamentoFinanceiro.query.filter_by(id=lancamento_id, tenant_id=tenant_id).with_for_update().first()
        if source is None:
            raise ValueError("Lancamento nao encontrado.")
        AcessoEmpresaService.validar_empresa(source.empresa_id, escopo)
        reason = motivo(data)
        if source.venda_id or source.boleto_id or source.parcela_boleto_id or source.lancamento_origem_id:
            raise ValueError("Use o ciclo de cancelamento da origem.")
        if AdiantamentoFuncionario.query.filter_by(tenant_id=tenant_id, lancamento_financeiro_id=source.id).first():
            raise ValueError("Use o ciclo de estorno do adiantamento.")
        return FinanceiroService.serializar_lancamento(FinanceiroCicloService.reverter_origem(source, reason, funcionario_id))

    @staticmethod
    @atomic_operation
    def conciliar(tenant_id, escopo, empresa_id, data_inicio=None, data_fim=None):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        start, end = FinanceiroService._resolver_periodo_relatorio(data_inicio, data_fim)
        sales = FinanceiroRepository.query_vendas(tenant_id, empresa_id=empresa_id, data_inicio=start, data_fim=end).all()
        rows = []
        for sale in sales:
            entries = LancamentoFinanceiro.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id, venda_id=sale.id).order_by(LancamentoFinanceiro.id).all()
            signed = sum((entry.valor if entry.tipo == TipoFinanceiro.ENTRADA else -entry.valor for entry in entries), Decimal("0.00"))
            canceled = sale.valor_cancelado or Decimal("0.00")
            cashback = sale.cashback_utilizado or Decimal("0.00")
            base = sale.total + cashback
            restored = (canceled * cashback / base).quantize(Decimal("0.01")) if base else Decimal("0.00")
            expected = sale.total - canceled + restored
            rows.append({"venda_id": sale.id, "pdv_liquido": str(expected), "financeiro_liquido": str(signed),
                "diferenca": str(signed - expected), "lancamento_ids": [entry.id for entry in entries]})
        return {"empresa_id": empresa_id, "data_inicio": start.isoformat(), "data_fim": end.isoformat(),
            "conciliado": all(Decimal(row["diferenca"]) == 0 for row in rows), "vendas": rows,
            "pdv_liquido": str(sum((Decimal(row["pdv_liquido"]) for row in rows), Decimal("0.00"))),
            "financeiro_liquido": str(sum((Decimal(row["financeiro_liquido"]) for row in rows), Decimal("0.00")))}

    @staticmethod
    @atomic_operation
    @idempotent
    def ajustar_fechamento(fechamento_id, data, tenant_id, escopo, funcionario_id):
        record = FechamentoCaixa.query.filter_by(id=fechamento_id, tenant_id=tenant_id).with_for_update().first()
        if record is None:
            raise ValueError("Fechamento nao encontrado.")
        AcessoEmpresaService.validar_empresa(record.empresa_id, escopo)
        reason = motivo(data)
        if positive_integer(data.get("revisao"), "Revisao") != record.revisao:
            raise ValueError("Fechamento alterado; atualize os dados.")
        before = {"status": record.status, "revisao": record.revisao, "valor_inicial": str(record.valor_inicial),
            "valor_final": str(record.valor_final), "conciliacao": record.conciliacao}
        action = data.get("acao")
        if action == "reabrir" and record.status == "FECHADO":
            record.status = "REABERTO"
        elif action == "fechar" and record.status == "REABERTO":
            record.valor_inicial = FinanceiroService._to_non_negative_decimal(data.get("valor_inicial"), "valor inicial")
            record.valor_final = FinanceiroService._to_non_negative_decimal(data.get("valor_final"), "valor final")
            record.status = "FECHADO"
        else:
            raise ValueError("Transicao de fechamento invalida.")
        record.revisao += 1
        summary = FinanceiroService.calcular_resumo_caixa(tenant_id, escopo, record.empresa_id, record.data_fechamento, record.valor_inicial)
        reconciliation = FinanceiroCicloService.conciliar(tenant_id, escopo, record.empresa_id,
            record.data_fechamento.isoformat(), record.data_fechamento.isoformat())
        if record.status == "FECHADO" and not reconciliation["conciliado"]:
            raise ValueError("Divergencia PDV e financeiro impede fechar o caixa.")
        record.conciliacao = {"caixa": {key: str(value) for key, value in summary.items()}, "pdv": reconciliation}
        audit("CAIXA_" + action.upper(), record, funcionario_id, {"motivo": reason, "antes": before,
            "depois": {"status": record.status, "revisao": record.revisao, "valor_inicial": str(record.valor_inicial),
                "valor_final": str(record.valor_final), "conciliacao": record.conciliacao}})
        return FinanceiroService.serializar_fechamento(record, summary)
