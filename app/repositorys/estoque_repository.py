from datetime import timedelta

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.services.time_service import TimeService
from app.models.db import (
    ConfiguracaoNotificacaoEstoque,
    Empresa,
    ItemVenda,
    MovimentoEstoque,
    Produto,
    ProdutoEmpresa,
    StatusVenda,
    TipoMovimentoEstoque,
    Venda,
)


class EstoqueRepository:

    @staticmethod
    def listar_saldos(tenant_id, empresa_ids=None, empresa_id=None):
        query = (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa)
            )
            .filter(ProdutoEmpresa.tenant_id == tenant_id)
            .order_by(ProdutoEmpresa.estoque_atual.asc(), ProdutoEmpresa.id.desc())
        )

        if empresa_ids is not None:
            query = query.filter(ProdutoEmpresa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(ProdutoEmpresa.empresa_id == empresa_id)

        return query.all()

    @staticmethod
    def listar_movimentos(tenant_id, empresa_ids=None, empresa_id=None, limite=50):
        query = (
            MovimentoEstoque.query
            .options(
                joinedload(MovimentoEstoque.empresa),
                joinedload(MovimentoEstoque.produto),
                joinedload(MovimentoEstoque.funcionario),
                joinedload(MovimentoEstoque.cancelado_por),
                joinedload(MovimentoEstoque.item_venda),
                joinedload(MovimentoEstoque.adiantamentos),
            )
            .filter(MovimentoEstoque.tenant_id == tenant_id)
            .order_by(MovimentoEstoque.data_movimento.desc(), MovimentoEstoque.id.desc())
        )

        if empresa_ids is not None:
            query = query.filter(MovimentoEstoque.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(MovimentoEstoque.empresa_id == empresa_id)

        return query.limit(max(limite, 1)).all()

    @staticmethod
    def buscar_movimento_por_id(movimento_id, tenant_id, empresa_ids=None):
        query = (
            MovimentoEstoque.query
            .options(
                joinedload(MovimentoEstoque.empresa),
                joinedload(MovimentoEstoque.produto),
                joinedload(MovimentoEstoque.funcionario),
                joinedload(MovimentoEstoque.cancelado_por),
                joinedload(MovimentoEstoque.item_venda),
                joinedload(MovimentoEstoque.adiantamentos),
            )
            .filter(
                MovimentoEstoque.id == movimento_id,
                MovimentoEstoque.tenant_id == tenant_id,
            )
        )

        if empresa_ids is not None:
            query = query.filter(MovimentoEstoque.empresa_id.in_(empresa_ids))

        return query.first()

    @staticmethod
    def buscar_movimento_venda_por_item(item_venda_id, tenant_id):
        return (
            MovimentoEstoque.query
            .options(
                joinedload(MovimentoEstoque.empresa),
                joinedload(MovimentoEstoque.produto),
                joinedload(MovimentoEstoque.funcionario),
                joinedload(MovimentoEstoque.item_venda),
            )
            .filter(
                MovimentoEstoque.tenant_id == tenant_id,
                MovimentoEstoque.item_venda_id == item_venda_id,
                MovimentoEstoque.venda_id.is_not(None),
                MovimentoEstoque.tipo_movimento == TipoMovimentoEstoque.SAIDA,
            )
            .order_by(MovimentoEstoque.id.asc())
            .first()
        )

    @staticmethod
    def listar_empresas(tenant_id, empresa_ids=None):
        query = (
            Empresa.query
            .filter(
                Empresa.tenant_id == tenant_id,
                Empresa.ativo.is_(True)
            )
            .order_by(Empresa.nome_fantasia.asc())
        )

        if empresa_ids is not None:
            query = query.filter(Empresa.id.in_(empresa_ids))

        return query.all()

    @staticmethod
    def listar_produtos_empresa_disponiveis(tenant_id, empresa_ids=None, empresa_id=None):
        query = (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto),
                joinedload(ProdutoEmpresa.empresa)
            )
            .join(Produto, Produto.id == ProdutoEmpresa.produto_id)
            .filter(
                ProdutoEmpresa.tenant_id == tenant_id,
                ProdutoEmpresa.ativo.is_(True),
                Produto.ativo.is_(True)
            )
            .order_by(ProdutoEmpresa.empresa_id.asc(), Produto.nome.asc())
        )

        if empresa_ids is not None:
            query = query.filter(ProdutoEmpresa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(ProdutoEmpresa.empresa_id == empresa_id)

        return query.all()

    @staticmethod
    def buscar_produto_empresa_por_id(produto_empresa_id, tenant_id, empresa_ids=None):
        query = (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto),
                joinedload(ProdutoEmpresa.empresa)
            )
            .filter(
                ProdutoEmpresa.id == produto_empresa_id,
                ProdutoEmpresa.tenant_id == tenant_id
            )
        )

        if empresa_ids is not None:
            query = query.filter(ProdutoEmpresa.empresa_id.in_(empresa_ids))

        return query.first()

    @staticmethod
    def buscar_produto_empresa(produto_id, empresa_id, tenant_id):
        return (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto),
                joinedload(ProdutoEmpresa.empresa)
            )
            .filter(
                ProdutoEmpresa.produto_id == produto_id,
                ProdutoEmpresa.empresa_id == empresa_id,
                ProdutoEmpresa.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def obter_configuracao_notificacao(tenant_id):
        return (
            ConfiguracaoNotificacaoEstoque.query
            .filter(ConfiguracaoNotificacaoEstoque.tenant_id == tenant_id)
            .first()
        )

    @staticmethod
    def listar_produtos_mais_vendidos(tenant_id, empresa_ids=None, empresa_id=None, data_inicio=None, data_fim=None, limite=20):
        query = (
            db.session.query(
                Produto.id.label("produto_id"),
                Produto.nome.label("produto_nome"),
                ProdutoEmpresa.empresa_id.label("empresa_id"),
                Empresa.nome_fantasia.label("empresa_nome"),
                db.func.coalesce(db.func.sum(ItemVenda.quantidade - ItemVenda.quantidade_cancelada), 0).label("quantidade"),
                db.func.coalesce(db.func.sum((ItemVenda.quantidade - ItemVenda.quantidade_cancelada) * ItemVenda.valor_unitario), 0).label("faturamento"),
            )
            .join(ItemVenda, ItemVenda.produto_id == Produto.id)
            .join(Venda, Venda.id == ItemVenda.venda_id)
            .join(Empresa, Empresa.id == Venda.empresa_id)
            .join(
                ProdutoEmpresa,
                db.and_(
                    ProdutoEmpresa.produto_id == Produto.id,
                    ProdutoEmpresa.empresa_id == Venda.empresa_id,
                    ProdutoEmpresa.tenant_id == tenant_id,
                ),
            )
            .filter(
                Venda.tenant_id == tenant_id,
                Venda.status == StatusVenda.FINALIZADA,
                ItemVenda.quantidade > ItemVenda.quantidade_cancelada,
                Produto.tenant_id == tenant_id,
            )
            .group_by(Produto.id, Produto.nome, ProdutoEmpresa.empresa_id, Empresa.nome_fantasia)
            .order_by(db.desc("quantidade"), db.desc("faturamento"))
        )

        if empresa_ids is not None:
            query = query.filter(Venda.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(Venda.empresa_id == empresa_id)

        if data_inicio is not None:
            query = query.filter(Venda.data_venda >= TimeService.local_date_start_to_utc_naive(data_inicio))

        if data_fim is not None:
            query = query.filter(Venda.data_venda < TimeService.local_date_start_to_utc_naive(data_fim + timedelta(days=1)))

        return query.limit(max(limite, 1)).all()

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def salvar():
        save()

    @staticmethod
    def rollback():
        db.session.rollback()
