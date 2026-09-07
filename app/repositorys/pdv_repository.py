from datetime import date

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.models.db import (
    CategoriaFinanceira,
    Cupom,
    Empresa,
    FormaPagamento,
    ItemVenda,
    PagamentoVenda,
    Produto,
    ProdutoEmpresa,
    StatusVenda,
    TipoCategoriaFinanceira,
    TipoOperacao,
    Venda,
)


class PdvRepository:

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
    def listar_cupons_ativos(tenant_id, data_referencia=None):
        data_referencia = data_referencia or date.today()
        return (
            Cupom.query
            .filter(
                Cupom.tenant_id == tenant_id,
                Cupom.ativo.is_(True),
                Cupom.data_validade >= data_referencia,
            )
            .order_by(Cupom.data_validade.asc(), Cupom.nome.asc())
            .all()
        )

    @staticmethod
    def listar_produtos_para_pdv(tenant_id, empresa_id):
        return (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa),
            )
            .join(Produto, Produto.id == ProdutoEmpresa.produto_id)
            .filter(
                ProdutoEmpresa.tenant_id == tenant_id,
                ProdutoEmpresa.empresa_id == empresa_id,
                ProdutoEmpresa.ativo.is_(True),
                Produto.ativo.is_(True),
            )
            .order_by(Produto.nome.asc())
            .all()
        )

    @staticmethod
    def buscar_produto_empresa(produto_id, empresa_id, tenant_id):
        return (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa),
            )
            .filter(
                ProdutoEmpresa.produto_id == produto_id,
                ProdutoEmpresa.empresa_id == empresa_id,
                ProdutoEmpresa.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_produto_empresa_por_codigo_barras(codigo_barras, empresa_id, tenant_id):
        if not codigo_barras:
            return None

        return (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa),
            )
            .join(Produto, Produto.id == ProdutoEmpresa.produto_id)
            .filter(
                ProdutoEmpresa.tenant_id == tenant_id,
                ProdutoEmpresa.empresa_id == empresa_id,
                ProdutoEmpresa.ativo.is_(True),
                Produto.ativo.is_(True),
                Produto.codigo_barras == codigo_barras,
            )
            .first()
        )

    @staticmethod
    def buscar_formas_pagamento_por_ids(ids_formas, tenant_id):
        if not ids_formas:
            return []

        return (
            FormaPagamento.query
            .filter(
                FormaPagamento.tenant_id == tenant_id,
                FormaPagamento.id.in_(ids_formas),
                FormaPagamento.ativo.is_(True),
            )
            .all()
        )

    @staticmethod
    def buscar_cupom_por_codigo(codigo, tenant_id):
        if not codigo:
            return None

        return (
            Cupom.query
            .filter(
                Cupom.tenant_id == tenant_id,
                Cupom.codigo == codigo,
            )
            .first()
        )

    @staticmethod
    def buscar_tipo_operacao_por_codigo(codigo, tenant_id):
        return (
            TipoOperacao.query
            .filter(
                TipoOperacao.tenant_id == tenant_id,
                TipoOperacao.codigo == codigo,
                TipoOperacao.ativo.is_(True),
            )
            .first()
        )

    @staticmethod
    def buscar_categoria_financeira_por_nome(nome, tipo, tenant_id):
        return (
            CategoriaFinanceira.query
            .filter(
                CategoriaFinanceira.tenant_id == tenant_id,
                CategoriaFinanceira.nome == nome,
                CategoriaFinanceira.tipo_categoria == tipo,
                CategoriaFinanceira.ativo.is_(True),
            )
            .first()
        )

    @staticmethod
    def listar_vendas(tenant_id, empresa_ids=None, empresa_id=None, status=None, limite=30):
        query = (
            Venda.query
            .options(
                joinedload(Venda.empresa),
                joinedload(Venda.cliente),
                joinedload(Venda.funcionario),
                joinedload(Venda.tipo_operacao),
                joinedload(Venda.cupom),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.itens).joinedload(ItemVenda.cancelado_por),
                joinedload(Venda.pagamentos).joinedload(PagamentoVenda.forma_pagamento),
            )
            .filter(Venda.tenant_id == tenant_id)
            .order_by(Venda.data_venda.desc(), Venda.id.desc())
        )

        if empresa_ids is not None:
            query = query.filter(Venda.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(Venda.empresa_id == empresa_id)

        if status is not None:
            if isinstance(status, (list, tuple, set)):
                query = query.filter(Venda.status.in_(list(status)))
            else:
                query = query.filter(Venda.status == status)

        return query.limit(max(limite, 1)).all()

    @staticmethod
    def buscar_venda_por_id(venda_id, tenant_id, empresa_ids=None):
        query = (
            Venda.query
            .options(
                joinedload(Venda.empresa),
                joinedload(Venda.cliente),
                joinedload(Venda.funcionario),
                joinedload(Venda.tipo_operacao),
                joinedload(Venda.cupom),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.itens).joinedload(ItemVenda.cancelado_por),
                joinedload(Venda.pagamentos).joinedload(PagamentoVenda.forma_pagamento),
            )
            .filter(
                Venda.id == venda_id,
                Venda.tenant_id == tenant_id,
            )
        )

        if empresa_ids is not None:
            query = query.filter(Venda.empresa_id.in_(empresa_ids))

        return query.first()

    @staticmethod
    def contar_vendas_do_dia(tenant_id, empresa_id, data_referencia):
        return (
            Venda.query
            .filter(
                Venda.tenant_id == tenant_id,
                Venda.empresa_id == empresa_id,
                db.func.date(Venda.data_venda) == data_referencia,
                Venda.status != StatusVenda.CANCELADA,
            )
            .count()
        )

    @staticmethod
    def buscar_item_venda(venda_id, item_id, tenant_id):
        return (
            ItemVenda.query
            .options(
                joinedload(ItemVenda.venda).joinedload(Venda.empresa),
                joinedload(ItemVenda.venda).joinedload(Venda.cliente),
                joinedload(ItemVenda.produto),
                joinedload(ItemVenda.cancelado_por),
            )
            .filter(
                ItemVenda.id == item_id,
                ItemVenda.venda_id == venda_id,
                ItemVenda.tenant_id == tenant_id,
            )
            .first()
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
