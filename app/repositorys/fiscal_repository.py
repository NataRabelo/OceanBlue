from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.db import ConfiguracaoFiscalEmpresa, Empresa, ItemVenda, NotaFiscalVenda, PagamentoVenda, Produto, ProdutoEmpresa, Venda


class FiscalRepository:

    @staticmethod
    def listar_empresas(tenant_id, empresa_ids=None):
        query = (
            Empresa.query
            .options(joinedload(Empresa.configuracao_fiscal))
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
    def buscar_empresa(empresa_id, tenant_id):
        return (
            Empresa.query
            .options(joinedload(Empresa.configuracao_fiscal))
            .filter(
                Empresa.id == empresa_id,
                Empresa.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_configuracao_por_empresa(empresa_id, tenant_id):
        return (
            ConfiguracaoFiscalEmpresa.query
            .filter(
                ConfiguracaoFiscalEmpresa.empresa_id == empresa_id,
                ConfiguracaoFiscalEmpresa.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_venda(venda_id, tenant_id, empresa_ids=None):
        query = (
            Venda.query
            .options(
                joinedload(Venda.empresa),
                joinedload(Venda.cliente),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.nota_fiscal),
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
    def buscar_produtos_empresa(produto_ids, empresa_id, tenant_id):
        if not produto_ids:
            return []

        return (
            ProdutoEmpresa.query
            .options(joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria))
            .join(Produto, Produto.id == ProdutoEmpresa.produto_id)
            .filter(
                ProdutoEmpresa.tenant_id == tenant_id,
                ProdutoEmpresa.empresa_id == empresa_id,
                ProdutoEmpresa.produto_id.in_(produto_ids),
            )
            .all()
        )

    @staticmethod
    def buscar_nota_por_venda(venda_id, tenant_id):
        return (
            NotaFiscalVenda.query
            .filter(
                NotaFiscalVenda.venda_id == venda_id,
                NotaFiscalVenda.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_nota_por_id(nota_id, tenant_id, empresa_ids=None):
        query = (
            NotaFiscalVenda.query
            .options(
                joinedload(NotaFiscalVenda.empresa),
                joinedload(NotaFiscalVenda.configuracao_fiscal),
                joinedload(NotaFiscalVenda.venda).joinedload(Venda.empresa),
                joinedload(NotaFiscalVenda.venda).joinedload(Venda.cliente),
                joinedload(NotaFiscalVenda.venda).joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(NotaFiscalVenda.venda).joinedload(Venda.pagamentos).joinedload(PagamentoVenda.forma_pagamento),
            )
            .filter(
                NotaFiscalVenda.id == nota_id,
                NotaFiscalVenda.tenant_id == tenant_id,
            )
        )

        if empresa_ids is not None:
            query = query.filter(NotaFiscalVenda.empresa_id.in_(empresa_ids))

        return query.first()

    @staticmethod
    def listar_notas(tenant_id, empresa_ids=None, limite=50):
        query = (
            NotaFiscalVenda.query
            .options(
                joinedload(NotaFiscalVenda.empresa),
                joinedload(NotaFiscalVenda.venda),
            )
            .filter(NotaFiscalVenda.tenant_id == tenant_id)
            .order_by(NotaFiscalVenda.atualizado_em.desc(), NotaFiscalVenda.id.desc())
        )

        if empresa_ids is not None:
            query = query.filter(NotaFiscalVenda.empresa_id.in_(empresa_ids))

        return query.limit(max(int(limite or 50), 1)).all()

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def flush():
        db.session.flush()

    @staticmethod
    def salvar():
        db.session.commit()

    @staticmethod
    def rollback():
        db.session.rollback()
