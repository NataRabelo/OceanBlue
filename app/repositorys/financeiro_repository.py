from datetime import datetime, time, timedelta

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.models.db import (
    CategoriaFinanceira,
    Empresa,
    FechamentoCaixa,
    FormaPagamento,
    ItemVenda,
    LancamentoFinanceiro,
    PagamentoVenda,
    TipoFinanceiro,
    Venda,
)
from app.services.time_service import TimeService


def _local_date_range_to_utc_naive(data_inicio=None, data_fim=None):
    start_utc = None
    end_utc = None

    if data_inicio is not None:
        start_local = datetime.combine(data_inicio, time.min, tzinfo=TimeService.TZ_BR)
        start_utc = start_local.astimezone(TimeService.TZ_UTC).replace(tzinfo=None)

    if data_fim is not None:
        end_local = datetime.combine(data_fim + timedelta(days=1), time.min, tzinfo=TimeService.TZ_BR)
        end_utc = end_local.astimezone(TimeService.TZ_UTC).replace(tzinfo=None)

    return start_utc, end_utc


class FinanceiroRepository:

    @staticmethod
    def listar_empresas(tenant_id, empresa_ids=None):
        query = (
            Empresa.query
            .filter(
                Empresa.tenant_id == tenant_id,
                Empresa.ativo.is_(True),
            )
            .order_by(Empresa.nome_fantasia.asc())
        )

        if empresa_ids is not None:
            query = query.filter(Empresa.id.in_(empresa_ids))

        return query.all()

    @staticmethod
    def listar_formas_pagamento(tenant_id):
        return (
            FormaPagamento.query
            .filter(
                FormaPagamento.tenant_id == tenant_id,
                FormaPagamento.ativo.is_(True),
            )
            .order_by(FormaPagamento.nome.asc())
            .all()
        )

    @staticmethod
    def listar_categorias(tenant_id):
        return (
            CategoriaFinanceira.query
            .filter(
                CategoriaFinanceira.tenant_id == tenant_id,
                CategoriaFinanceira.ativo.is_(True),
            )
            .order_by(CategoriaFinanceira.tipo_categoria.asc(), CategoriaFinanceira.nome.asc())
            .all()
        )

    @staticmethod
    def buscar_categoria_por_id(categoria_id, tenant_id):
        return (
            CategoriaFinanceira.query
            .filter(
                CategoriaFinanceira.id == categoria_id,
                CategoriaFinanceira.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_categoria_por_nome(nome, tipo, tenant_id):
        return (
            CategoriaFinanceira.query
            .filter(
                CategoriaFinanceira.nome == nome,
                CategoriaFinanceira.tipo_categoria == tipo,
                CategoriaFinanceira.tenant_id == tenant_id,
                CategoriaFinanceira.ativo.is_(True),
            )
            .first()
        )

    @staticmethod
    def buscar_forma_pagamento_por_id(forma_pagamento_id, tenant_id):
        return (
            FormaPagamento.query
            .filter(
                FormaPagamento.id == forma_pagamento_id,
                FormaPagamento.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_forma_pagamento_por_nome(nome, tenant_id):
        return (
            FormaPagamento.query
            .filter(
                FormaPagamento.nome == nome,
                FormaPagamento.tenant_id == tenant_id,
                FormaPagamento.ativo.is_(True),
            )
            .first()
        )

    @staticmethod
    def listar_lancamentos(
        tenant_id,
        empresa_ids=None,
        empresa_id=None,
        tipo=None,
        data_inicio=None,
        data_fim=None,
        limite=100,
    ):
        query = FinanceiroRepository.query_lancamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        query = query.options(
            joinedload(LancamentoFinanceiro.empresa),
            joinedload(LancamentoFinanceiro.funcionario),
            joinedload(LancamentoFinanceiro.categoria),
            joinedload(LancamentoFinanceiro.forma_pagamento),
            joinedload(LancamentoFinanceiro.venda),
            joinedload(LancamentoFinanceiro.adiantamentos),
        )
        query = query.order_by(
            LancamentoFinanceiro.data_lancamento.desc(),
            LancamentoFinanceiro.id.desc(),
        )
        return query.limit(max(limite, 1)).all() if limite is not None else query.all()

    @staticmethod
    def query_lancamentos(
        tenant_id,
        empresa_ids=None,
        empresa_id=None,
        tipo=None,
        data_inicio=None,
        data_fim=None,
    ):
        query = LancamentoFinanceiro.query.filter(LancamentoFinanceiro.tenant_id == tenant_id)

        if empresa_ids is not None:
            query = query.filter(LancamentoFinanceiro.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(LancamentoFinanceiro.empresa_id == empresa_id)

        if tipo is not None:
            query = query.filter(LancamentoFinanceiro.tipo == tipo)

        if data_inicio is not None:
            query = query.filter(db.func.date(LancamentoFinanceiro.data_lancamento) >= data_inicio)

        if data_fim is not None:
            query = query.filter(db.func.date(LancamentoFinanceiro.data_lancamento) <= data_fim)

        return query

    @staticmethod
    def listar_fechamentos(tenant_id, empresa_ids=None, empresa_id=None, limite=30):
        query = (
            FechamentoCaixa.query
            .options(
                joinedload(FechamentoCaixa.empresa),
                joinedload(FechamentoCaixa.funcionario),
            )
            .filter(FechamentoCaixa.tenant_id == tenant_id)
            .order_by(FechamentoCaixa.data_fechamento.desc(), FechamentoCaixa.id.desc())
        )

        if empresa_ids is not None:
            query = query.filter(FechamentoCaixa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(FechamentoCaixa.empresa_id == empresa_id)

        return query.limit(max(limite, 1)).all()

    @staticmethod
    def buscar_fechamento_existente(tenant_id, empresa_id, funcionario_id, data_fechamento):
        return (
            FechamentoCaixa.query
            .filter(
                FechamentoCaixa.tenant_id == tenant_id,
                FechamentoCaixa.empresa_id == empresa_id,
                FechamentoCaixa.funcionario_id == funcionario_id,
                FechamentoCaixa.data_fechamento == data_fechamento,
            )
            .first()
        )

    @staticmethod
    def query_vendas(tenant_id, empresa_ids=None, empresa_id=None, data_inicio=None, data_fim=None):
        query = Venda.query.filter(Venda.tenant_id == tenant_id)
        data_inicio_utc, data_fim_utc = _local_date_range_to_utc_naive(data_inicio, data_fim)

        if empresa_ids is not None:
            query = query.filter(Venda.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(Venda.empresa_id == empresa_id)

        if data_inicio_utc is not None:
            query = query.filter(Venda.data_venda >= data_inicio_utc)

        if data_fim_utc is not None:
            query = query.filter(Venda.data_venda < data_fim_utc)

        return query

    @staticmethod
    def listar_vendas(tenant_id, empresa_ids=None, empresa_id=None, data_inicio=None, data_fim=None, limite=30):
        return (
            FinanceiroRepository.query_vendas(
                tenant_id=tenant_id,
                empresa_ids=empresa_ids,
                empresa_id=empresa_id,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )
            .options(
                joinedload(Venda.empresa),
                joinedload(Venda.funcionario),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.pagamentos).joinedload(PagamentoVenda.forma_pagamento),
            )
            .order_by(Venda.data_venda.desc(), Venda.id.desc())
            .limit(max(limite, 1))
            .all()
        )

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def flush():
        db.session.flush()

    @staticmethod
    def salvar():
        save()

    @staticmethod
    def rollback():
        db.session.rollback()
