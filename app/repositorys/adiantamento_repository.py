from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.models.db import (
    AdiantamentoFuncionario,
    CategoriaFinanceira,
    Empresa,
    FormaPagamento,
    Funcionario,
    FuncionarioEmpresa,
    Produto,
    ProdutoEmpresa,
)


class AdiantamentoRepository:

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
    def listar_funcionarios_vinculados(tenant_id, empresa_ids=None, empresa_id=None):
        query = (
            FuncionarioEmpresa.query
            .options(
                joinedload(FuncionarioEmpresa.funcionario),
                joinedload(FuncionarioEmpresa.empresa),
            )
            .join(Funcionario, Funcionario.id == FuncionarioEmpresa.funcionario_id)
            .filter(
                FuncionarioEmpresa.tenant_id == tenant_id,
                FuncionarioEmpresa.ativo.is_(True),
                Funcionario.ativo.is_(True),
            )
            .order_by(Funcionario.nome.asc(), FuncionarioEmpresa.id.asc())
        )

        if empresa_ids is not None:
            query = query.filter(FuncionarioEmpresa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(FuncionarioEmpresa.empresa_id == empresa_id)

        return query.all()

    @staticmethod
    def buscar_vinculo_funcionario(funcionario_id, tenant_id, empresa_id=None, empresa_ids=None):
        query = (
            FuncionarioEmpresa.query
            .options(
                joinedload(FuncionarioEmpresa.funcionario),
                joinedload(FuncionarioEmpresa.empresa),
            )
            .join(Funcionario, Funcionario.id == FuncionarioEmpresa.funcionario_id)
            .filter(
                FuncionarioEmpresa.tenant_id == tenant_id,
                FuncionarioEmpresa.funcionario_id == funcionario_id,
                FuncionarioEmpresa.ativo.is_(True),
                Funcionario.ativo.is_(True),
            )
        )

        if empresa_ids is not None:
            query = query.filter(FuncionarioEmpresa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(FuncionarioEmpresa.empresa_id == empresa_id)

        return query.first()

    @staticmethod
    def listar_produtos_empresa(tenant_id, empresa_ids=None, empresa_id=None):
        query = (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa),
            )
            .join(Produto, Produto.id == ProdutoEmpresa.produto_id)
            .filter(
                ProdutoEmpresa.tenant_id == tenant_id,
                ProdutoEmpresa.ativo.is_(True),
                Produto.ativo.is_(True),
            )
            .order_by(Produto.nome.asc())
        )

        if empresa_ids is not None:
            query = query.filter(ProdutoEmpresa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(ProdutoEmpresa.empresa_id == empresa_id)

        return query.all()

    @staticmethod
    def buscar_produto_empresa(produto_id, tenant_id, empresa_id):
        return (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa),
            )
            .filter(
                ProdutoEmpresa.tenant_id == tenant_id,
                ProdutoEmpresa.produto_id == produto_id,
                ProdutoEmpresa.empresa_id == empresa_id,
                ProdutoEmpresa.ativo.is_(True),
            )
            .first()
        )

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
    def listar_adiantamentos(tenant_id, empresa_ids=None, empresa_id=None, funcionario_id=None, competencia=None, limite=100):
        query = (
            AdiantamentoFuncionario.query
            .options(
                joinedload(AdiantamentoFuncionario.empresa),
                joinedload(AdiantamentoFuncionario.funcionario),
                joinedload(AdiantamentoFuncionario.produto),
                joinedload(AdiantamentoFuncionario.forma_pagamento),
                joinedload(AdiantamentoFuncionario.lancamento_financeiro),
                joinedload(AdiantamentoFuncionario.movimento_estoque),
            )
            .filter(AdiantamentoFuncionario.tenant_id == tenant_id)
            .order_by(
                AdiantamentoFuncionario.data_adiantamento.desc(),
                AdiantamentoFuncionario.id.desc(),
            )
        )

        if empresa_ids is not None:
            query = query.filter(AdiantamentoFuncionario.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(AdiantamentoFuncionario.empresa_id == empresa_id)

        if funcionario_id is not None:
            query = query.filter(AdiantamentoFuncionario.funcionario_id == funcionario_id)

        if competencia is not None:
            query = query.filter(AdiantamentoFuncionario.competencia == competencia)

        return query.limit(max(limite, 1)).all()

    @staticmethod
    def buscar_por_id(adiantamento_id, tenant_id, empresa_ids=None):
        query = (
            AdiantamentoFuncionario.query
            .options(
                joinedload(AdiantamentoFuncionario.empresa),
                joinedload(AdiantamentoFuncionario.funcionario),
                joinedload(AdiantamentoFuncionario.produto),
                joinedload(AdiantamentoFuncionario.forma_pagamento),
                joinedload(AdiantamentoFuncionario.lancamento_financeiro),
                joinedload(AdiantamentoFuncionario.movimento_estoque),
            )
            .filter(
                AdiantamentoFuncionario.id == adiantamento_id,
                AdiantamentoFuncionario.tenant_id == tenant_id,
            )
        )

        if empresa_ids is not None:
            query = query.filter(AdiantamentoFuncionario.empresa_id.in_(empresa_ids))

        return query.first()

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
