from app.extensions import db
from app.models.db import AdiantamentoFuncionario, ProdutoEmpresa, TipoAdiantamentoFuncionario, TipoMovimentoEstoque, MotivoMovimentoEstoque
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.adiantamento_service import AdiantamentoService
from app.repositorys.adiantamento_repository import AdiantamentoRepository
from app.services.estoque_service import EstoqueService
from app.services.financeiro_service import FinanceiroService
from app.services.financeiro_ciclo_service import FinanceiroCicloService, audit, motivo
from app.services.idempotency_service import idempotent
from app.services.money_service import positive_integer
from app.services.transaction_service import atomic_operation


class AdiantamentoCicloService:
    @staticmethod
    @atomic_operation
    @idempotent
    def solicitar(data, tenant_id, escopo, funcionario_id):
        record = AdiantamentoService.criar({**data, "solicitar": True}, tenant_id, escopo, funcionario_id)
        return AdiantamentoService.serializar(record)

    @staticmethod
    @atomic_operation
    @idempotent
    def transicionar(adiantamento_id, data, tenant_id, escopo, funcionario_id):
        record = AdiantamentoFuncionario.query.filter_by(id=adiantamento_id, tenant_id=tenant_id).with_for_update().first()
        if record is None:
            raise ValueError("Adiantamento nao encontrado.")
        AcessoEmpresaService.validar_empresa(record.empresa_id, escopo)
        reason = motivo(data)
        if positive_integer(data.get("revisao"), "Revisao") != record.revisao:
            raise ValueError("Adiantamento alterado; atualize os dados.")
        before = record.status
        action = data.get("acao")
        if action == "autorizar" and before == "PENDENTE":
            if not AdiantamentoRepository.buscar_vinculo_funcionario(record.funcionario_id, tenant_id, record.empresa_id):
                raise ValueError("Funcionario inativo ou sem vinculo ativo com a empresa.")
            if record.tipo_adiantamento == TipoAdiantamentoFuncionario.PRODUTO:
                movement = EstoqueService.registrar_saida_por_adiantamento(tenant_id=tenant_id,
                    empresa_id=record.empresa_id, produto_id=record.produto_id, quantidade=record.quantidade,
                    funcionario_id=funcionario_id, valor_unitario=record.valor_unitario,
                    observacao=reason, escopo=escopo, persistir=False)
                db.session.flush()
                record.movimento_estoque_id = movement.id
            entry = FinanceiroService.registrar_saida_adiantamento(tenant_id=tenant_id,
                empresa_id=record.empresa_id, funcionario_id=record.funcionario_id,
                forma_pagamento_id=record.forma_pagamento_id, valor=record.valor_total,
                descricao=record.descricao, data_competencia=record.competencia, observacao=reason, persistir=False)
            record.lancamento_financeiro_id = entry.id
            record.status = "AUTORIZADO"
        elif action == "baixar" and before == "AUTORIZADO":
            record.status = "BAIXADO"
        elif action == "reverter_baixa" and before == "BAIXADO":
            record.status = "AUTORIZADO"
        elif action == "cancelar" and before == "PENDENTE":
            record.status = "CANCELADO"
        elif action == "estornar" and before == "AUTORIZADO":
            FinanceiroCicloService.reverter_origem(record.lancamento_financeiro, reason, funcionario_id)
            if record.movimento_estoque_id:
                source = record.movimento_estoque
                stock = ProdutoEmpresa.query.filter_by(tenant_id=tenant_id, empresa_id=record.empresa_id, produto_id=record.produto_id).one()
                EstoqueService._registrar_movimento(tenant_id, stock, TipoMovimentoEstoque.ENTRADA,
                    MotivoMovimentoEstoque.DEVOLUCAO, record.quantidade, funcionario_id=funcionario_id,
                    movimento_origem_id=source.id, valor_unitario=record.valor_unitario, observacao=reason)
                source.revertido = True
            record.status = "ESTORNADO"
        else:
            raise ValueError("Transicao invalida; reverta a baixa antes de estornar.")
        record.revisao += 1
        audit("ADIANTAMENTO_" + action.upper(), record, funcionario_id,
            {"antes": before, "depois": record.status, "revisao": record.revisao, "motivo": reason, "valor": str(record.valor_total)})
        return AdiantamentoService.serializar(record)
