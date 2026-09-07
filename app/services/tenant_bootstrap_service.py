from app.extensions import db
from app.models.db import (
    CategoriaFinanceira,
    ConfiguracaoNotificacaoEstoque,
    FormaPagamento,
    Permission,
    Role,
    RolePermission,
    TipoCategoriaFinanceira,
    TipoOperacao,
    TipoOperacaoEnum,
)
from app.security.permissions import DEFAULT_PERMISSION_DEFINITIONS, DEFAULT_ROLE_DEFINITIONS


class TenantBootstrapService:
    DEFAULT_FORMAS_PAGAMENTO = (
        "Dinheiro",
        "Pix",
        "Cartao de debito",
        "Cartao de credito",
        "Boleto",
        "Crediario",
        "Vale em folha",
    )

    DEFAULT_CATEGORIAS_FINANCEIRAS = (
        {"nome": "Vendas PDV", "tipo": TipoCategoriaFinanceira.ENTRADA},
        {"nome": "Aporte de caixa", "tipo": TipoCategoriaFinanceira.ENTRADA},
        {"nome": "Outras entradas", "tipo": TipoCategoriaFinanceira.ENTRADA},
        {"nome": "Compras de mercadorias", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Despesas operacionais", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Funcionarios", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Aluguel", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Contas", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Gastos pessoais", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Contador", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Adiantamento (Vale)", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Estorno de vendas", "tipo": TipoCategoriaFinanceira.SAIDA},
        {"nome": "Sangria de caixa", "tipo": TipoCategoriaFinanceira.SAIDA},
    )

    DEFAULT_TIPOS_OPERACAO = (
        {
            "nome": "Venda PDV",
            "codigo": "VENDA_PADRAO",
            "tipo_operacao": TipoOperacaoEnum.VENDA,
        },
        {
            "nome": "Entrada manual de estoque",
            "codigo": "ENTRADA_ESTOQUE_PADRAO",
            "tipo_operacao": TipoOperacaoEnum.ENTRADA_ESTOQUE,
        },
        {
            "nome": "Ajuste de estoque",
            "codigo": "AJUSTE_ESTOQUE_PADRAO",
            "tipo_operacao": TipoOperacaoEnum.AJUSTE_ESTOQUE,
        },
        {
            "nome": "Transferencia interna",
            "codigo": "TRANSFERENCIA_PADRAO",
            "tipo_operacao": TipoOperacaoEnum.TRANSFERENCIA,
        },
    )

    @staticmethod
    def garantir_permissoes_e_roles(tenant_id):
        permissions_by_code = {}

        for definicao in DEFAULT_PERMISSION_DEFINITIONS:
            permission = Permission.query.filter_by(
                tenant_id=tenant_id,
                codigo=definicao["codigo"],
            ).first()
            if not permission:
                permission = Permission(
                    tenant_id=tenant_id,
                    nome=definicao["nome"],
                    codigo=definicao["codigo"],
                    descricao=definicao.get("descricao"),
                    ativo=True,
                )
                db.session.add(permission)
                db.session.flush()

            permissions_by_code[permission.codigo] = permission

        roles_por_codigo = {}

        for definicao in DEFAULT_ROLE_DEFINITIONS:
            role = Role.query.filter_by(
                tenant_id=tenant_id,
                codigo=definicao["codigo"],
            ).first()
            role_criada = False
            if not role:
                role = Role(
                    tenant_id=tenant_id,
                    nome=definicao["nome"],
                    codigo=definicao["codigo"],
                    descricao=definicao.get("descricao"),
                    ativo=True,
                )
                db.session.add(role)
                db.session.flush()
                role_criada = True

            roles_por_codigo[role.codigo] = role

            if role_criada:
                for permission_code in definicao["permissoes"]:
                    permission = permissions_by_code[permission_code]
                    vinculo = RolePermission.query.filter_by(
                        tenant_id=tenant_id,
                        role_id=role.id,
                        permission_id=permission.id,
                    ).first()

                    if not vinculo:
                        db.session.add(
                            RolePermission(
                                tenant_id=tenant_id,
                                role_id=role.id,
                                permission_id=permission.id,
                            )
                        )

        db.session.flush()
        return roles_por_codigo

    @staticmethod
    def garantir_cadastros_operacionais(tenant_id):
        formas_pagamento = {}
        categorias_financeiras = {}
        tipos_operacao = {}
        configuracao_alerta = (
            ConfiguracaoNotificacaoEstoque.query
            .filter_by(tenant_id=tenant_id)
            .first()
        )

        for nome in TenantBootstrapService.DEFAULT_FORMAS_PAGAMENTO:
            forma = FormaPagamento.query.filter_by(tenant_id=tenant_id, nome=nome).first()
            if not forma:
                forma = FormaPagamento(
                    tenant_id=tenant_id,
                    nome=nome,
                    ativo=True,
                )
                db.session.add(forma)
                db.session.flush()
            formas_pagamento[forma.nome] = forma

        for definicao in TenantBootstrapService.DEFAULT_CATEGORIAS_FINANCEIRAS:
            categoria = CategoriaFinanceira.query.filter_by(
                tenant_id=tenant_id,
                nome=definicao["nome"],
                tipo_categoria=definicao["tipo"],
            ).first()
            if not categoria:
                categoria = CategoriaFinanceira(
                    tenant_id=tenant_id,
                    nome=definicao["nome"],
                    tipo_categoria=definicao["tipo"],
                    ativo=True,
                )
                db.session.add(categoria)
                db.session.flush()
            categorias_financeiras[(categoria.nome, categoria.tipo_categoria.value)] = categoria

        for definicao in TenantBootstrapService.DEFAULT_TIPOS_OPERACAO:
            tipo_operacao = TipoOperacao.query.filter_by(
                tenant_id=tenant_id,
                codigo=definicao["codigo"],
            ).first()
            if not tipo_operacao:
                tipo_operacao = TipoOperacao(
                    tenant_id=tenant_id,
                    nome=definicao["nome"],
                    codigo=definicao["codigo"],
                    tipo_operacao=definicao["tipo_operacao"],
                    ativo=True,
                )
                db.session.add(tipo_operacao)
                db.session.flush()
            else:
                tipo_operacao.nome = definicao["nome"]
                tipo_operacao.tipo_operacao = definicao["tipo_operacao"]
                tipo_operacao.ativo = True

            tipos_operacao[tipo_operacao.codigo] = tipo_operacao

        if not configuracao_alerta:
            configuracao_alerta = ConfiguracaoNotificacaoEstoque(
                tenant_id=tenant_id,
                popup_ao_entrar=True,
                alertar_estoque_baixo=True,
                alertar_sem_estoque=True,
                alertar_validade=True,
                dias_vencimento_alerta=30,
                email_habilitado=False,
                whatsapp_habilitado=False,
                resumo_diario=False,
            )
            db.session.add(configuracao_alerta)
            db.session.flush()

        db.session.flush()
        return {
            "formas_pagamento": formas_pagamento,
            "categorias_financeiras": categorias_financeiras,
            "tipos_operacao": tipos_operacao,
            "configuracao_alerta": configuracao_alerta,
        }
