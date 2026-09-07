from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.models.db import Produto, ProdutoEmpresa, CategoriaProduto, Empresa


class ProdutoRepository:

    @staticmethod
    def listar(tenant_id, empresa_ids=None):
        query = (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa)
            )
            .filter(ProdutoEmpresa.tenant_id == tenant_id)
            .order_by(ProdutoEmpresa.id.desc())
        )

        if empresa_ids is not None:
            query = query.filter(ProdutoEmpresa.empresa_id.in_(empresa_ids))

        return query.all()

    @staticmethod
    def buscar_produto_empresa_por_id(produto_empresa_id, tenant_id, empresa_ids=None):
        query = (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
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
    def buscar_categoria_por_id(categoria_id, tenant_id):
        if not categoria_id:
            return None

        return (
            CategoriaProduto.query
            .filter(
                CategoriaProduto.id == categoria_id,
                CategoriaProduto.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def buscar_empresa_por_id(empresa_id, tenant_id):
        return (
            Empresa.query
            .filter(
                Empresa.id == empresa_id,
                Empresa.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def listar_categorias(tenant_id, empresa_ids=None):
        query = CategoriaProduto.query.filter(
            CategoriaProduto.tenant_id == tenant_id,
            CategoriaProduto.ativo.is_(True)
        )

        return query.order_by(CategoriaProduto.nome.asc()).all()

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
    def buscar_produto_por_nome(nome, tenant_id, ignorar_produto_id=None):
        query = Produto.query.filter(
            Produto.nome == nome,
            Produto.tenant_id == tenant_id
        )

        if ignorar_produto_id:
            query = query.filter(Produto.id != ignorar_produto_id)

        return query.first()

    @staticmethod
    def buscar_produto_por_codigo_barras(codigo_barras, tenant_id, ignorar_produto_id=None):
        if not codigo_barras:
            return None

        query = Produto.query.filter(
            Produto.codigo_barras == codigo_barras,
            Produto.tenant_id == tenant_id
        )

        if ignorar_produto_id:
            query = query.filter(Produto.id != ignorar_produto_id)

        return query.first()

    @staticmethod
    def existe_produto_empresa(produto_id, empresa_id, tenant_id, ignorar_produto_empresa_id=None):
        query = ProdutoEmpresa.query.filter(
            ProdutoEmpresa.produto_id == produto_id,
            ProdutoEmpresa.empresa_id == empresa_id,
            ProdutoEmpresa.tenant_id == tenant_id
        )

        if ignorar_produto_empresa_id:
            query = query.filter(ProdutoEmpresa.id != ignorar_produto_empresa_id)

        return query.first() is not None

    @staticmethod
    def salvar():
        save()

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def deletar(obj):
        db.session.delete(obj)

    @staticmethod
    def contar_vinculos_produto(produto_id, tenant_id):
        return (
            ProdutoEmpresa.query
            .filter(
                ProdutoEmpresa.produto_id == produto_id,
                ProdutoEmpresa.tenant_id == tenant_id
            )
            .count()
        )

    @staticmethod
    def contar_produtos(tenant_id):
        return (
            Produto.query
            .filter(Produto.tenant_id == tenant_id)
            .count()
        )
