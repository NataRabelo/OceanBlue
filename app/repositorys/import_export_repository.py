from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.repositorys.funcionario_repository import _digits_only_expression
from app.services.transaction_service import save
from app.models.db import (
    CategoriaFinanceira,
    CategoriaProduto,
    Cupom,
    Empresa,
    FormaPagamento,
    Funcionario,
    FuncionarioEmpresa,
    Produto,
    ProdutoEmpresa,
    Role,
)


class ImportExportRepository:
    @staticmethod
    def listar_empresas(tenant_id, empresa_ids=None):
        query = (
            Empresa.query
            .filter(Empresa.tenant_id == tenant_id)
            .order_by(Empresa.nome_fantasia.asc())
        )

        if empresa_ids is not None:
            query = query.filter(Empresa.id.in_(empresa_ids))

        return query.all()

    @staticmethod
    def buscar_empresa_por_identificador(tenant_id, identificador, empresa_ids=None):
        valor = (identificador or "").strip()
        if not valor:
            return None

        query = Empresa.query.filter(Empresa.tenant_id == tenant_id)
        if empresa_ids is not None:
            query = query.filter(Empresa.id.in_(empresa_ids))

        return (
            query.filter(
                (func.lower(Empresa.nome_fantasia) == valor.lower())
                | (func.lower(Empresa.razao_social) == valor.lower())
                | (Empresa.cnpj == valor)
            )
            .first()
        )

    @staticmethod
    def listar_categorias_produto(tenant_id):
        return (
            CategoriaProduto.query
            .filter(CategoriaProduto.tenant_id == tenant_id)
            .order_by(CategoriaProduto.nome.asc())
            .all()
        )

    @staticmethod
    def buscar_categoria_produto_por_nome(tenant_id, nome):
        valor = (nome or "").strip()
        if not valor:
            return None

        return (
            CategoriaProduto.query
            .filter(
                CategoriaProduto.tenant_id == tenant_id,
                func.lower(CategoriaProduto.nome) == valor.lower(),
            )
            .first()
        )

    @staticmethod
    def listar_roles(tenant_id):
        return (
            Role.query
            .filter(Role.tenant_id == tenant_id)
            .order_by(Role.nome.asc())
            .all()
        )

    @staticmethod
    def buscar_role_por_identificador(tenant_id, identificador):
        valor = (identificador or "").strip()
        if not valor:
            return None

        return (
            Role.query
            .filter(
                Role.tenant_id == tenant_id,
                (
                    (func.lower(Role.nome) == valor.lower())
                    | (func.lower(Role.codigo) == valor.lower())
                )
            )
            .first()
        )

    @staticmethod
    def listar_produtos_empresa(tenant_id, empresa_ids=None, empresa_id=None):
        query = (
            ProdutoEmpresa.query
            .options(
                joinedload(ProdutoEmpresa.produto).joinedload(Produto.categoria),
                joinedload(ProdutoEmpresa.empresa),
            )
            .filter(ProdutoEmpresa.tenant_id == tenant_id)
            .order_by(ProdutoEmpresa.id.asc())
        )

        if empresa_ids is not None:
            query = query.filter(ProdutoEmpresa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(ProdutoEmpresa.empresa_id == empresa_id)

        return query.all()

    @staticmethod
    def buscar_produto_por_nome(tenant_id, nome):
        valor = (nome or "").strip()
        if not valor:
            return None

        return (
            Produto.query
            .options(joinedload(Produto.categoria))
            .filter(
                Produto.tenant_id == tenant_id,
                func.lower(Produto.nome) == valor.lower(),
            )
            .first()
        )

    @staticmethod
    def buscar_produto_por_codigo_barras(tenant_id, codigo_barras):
        valor = (codigo_barras or "").strip()
        if not valor:
            return None

        return (
            Produto.query
            .options(joinedload(Produto.categoria))
            .filter(
                Produto.tenant_id == tenant_id,
                Produto.codigo_barras == valor,
            )
            .first()
        )

    @staticmethod
    def buscar_produto_empresa(tenant_id, produto_id, empresa_id):
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
            )
            .first()
        )

    @staticmethod
    def listar_funcionarios_empresa(tenant_id, empresa_ids=None, empresa_id=None):
        query = (
            FuncionarioEmpresa.query
            .options(
                joinedload(FuncionarioEmpresa.funcionario).joinedload(Funcionario.role),
                joinedload(FuncionarioEmpresa.empresa),
            )
            .filter(FuncionarioEmpresa.tenant_id == tenant_id)
            .order_by(FuncionarioEmpresa.id.asc())
        )

        if empresa_ids is not None:
            query = query.filter(FuncionarioEmpresa.empresa_id.in_(empresa_ids))

        if empresa_id is not None:
            query = query.filter(FuncionarioEmpresa.empresa_id == empresa_id)

        return query.all()

    @staticmethod
    def buscar_funcionario_por_cpf(tenant_id, cpf):
        valor = (cpf or "").strip()
        if not valor:
            return None

        return (
            Funcionario.query
            .options(joinedload(Funcionario.role))
            .filter(
                Funcionario.tenant_id == tenant_id,
                _digits_only_expression(Funcionario.cpf) == valor,
            )
            .first()
        )

    @staticmethod
    def buscar_funcionario_por_usuario(tenant_id, usuario):
        valor = (usuario or "").strip()
        if not valor:
            return None

        return (
            Funcionario.query
            .options(joinedload(Funcionario.role))
            .filter(
                Funcionario.tenant_id == tenant_id,
                func.lower(Funcionario.usuario) == valor.lower(),
            )
            .first()
        )

    @staticmethod
    def buscar_funcionario_empresa(tenant_id, funcionario_id, empresa_id):
        return (
            FuncionarioEmpresa.query
            .options(
                joinedload(FuncionarioEmpresa.funcionario).joinedload(Funcionario.role),
                joinedload(FuncionarioEmpresa.empresa),
            )
            .filter(
                FuncionarioEmpresa.tenant_id == tenant_id,
                FuncionarioEmpresa.funcionario_id == funcionario_id,
                FuncionarioEmpresa.empresa_id == empresa_id,
            )
            .first()
        )

    @staticmethod
    def listar_cupons(tenant_id):
        return (
            Cupom.query
            .options(joinedload(Cupom.criado_por))
            .filter(Cupom.tenant_id == tenant_id)
            .order_by(Cupom.codigo.asc())
            .all()
        )

    @staticmethod
    def buscar_cupom_por_codigo(tenant_id, codigo):
        valor = (codigo or "").strip().upper()
        if not valor:
            return None

        return (
            Cupom.query
            .filter(
                Cupom.tenant_id == tenant_id,
                Cupom.codigo == valor,
            )
            .first()
        )

    @staticmethod
    def listar_formas_pagamento(tenant_id):
        return (
            FormaPagamento.query
            .filter(FormaPagamento.tenant_id == tenant_id)
            .order_by(FormaPagamento.nome.asc())
            .all()
        )

    @staticmethod
    def buscar_forma_pagamento_por_nome(tenant_id, nome):
        valor = (nome or "").strip()
        if not valor:
            return None

        return (
            FormaPagamento.query
            .filter(
                FormaPagamento.tenant_id == tenant_id,
                func.lower(FormaPagamento.nome) == valor.lower(),
            )
            .first()
        )

    @staticmethod
    def listar_categorias_financeiras(tenant_id):
        return (
            CategoriaFinanceira.query
            .filter(CategoriaFinanceira.tenant_id == tenant_id)
            .order_by(CategoriaFinanceira.tipo_categoria.asc(), CategoriaFinanceira.nome.asc())
            .all()
        )

    @staticmethod
    def buscar_categoria_financeira_por_nome_tipo(tenant_id, nome, tipo_categoria):
        valor = (nome or "").strip()
        if not valor or not tipo_categoria:
            return None

        return (
            CategoriaFinanceira.query
            .filter(
                CategoriaFinanceira.tenant_id == tenant_id,
                func.lower(CategoriaFinanceira.nome) == valor.lower(),
                CategoriaFinanceira.tipo_categoria == tipo_categoria,
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
