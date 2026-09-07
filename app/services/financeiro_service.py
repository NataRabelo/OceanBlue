from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.db import (
    CategoriaFinanceira,
    FechamentoCaixa,
    FormaPagamento,
    ItemVenda,
    LancamentoFinanceiro,
    Produto,
    ProdutoEmpresa,
    StatusVenda,
    TipoCategoriaFinanceira,
    TipoFinanceiro,
    Venda,
)
from app.repositorys.financeiro_repository import FinanceiroRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.tenant_bootstrap_service import TenantBootstrapService
from app.services.time_service import TimeService
from app.services.money_service import allocate_money
from app.services.transaction_service import atomic_operation
from app.services.idempotency_service import idempotent


class FinanceiroService:
    CATEGORIA_VENDA = "Vendas PDV"
    CATEGORIA_ESTORNO = "Estorno de vendas"
    CATEGORIA_ADIANTAMENTO = "Adiantamento (Vale)"
    FORMA_DINHEIRO = "Dinheiro"

    @staticmethod
    def listar_auxiliares(tenant_id, escopo):
        FinanceiroService._garantir_base_operacional(tenant_id)

        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        empresas = FinanceiroRepository.listar_empresas(tenant_id, empresa_ids=empresa_ids)
        formas = FinanceiroRepository.listar_formas_pagamento(tenant_id)
        categorias = FinanceiroRepository.listar_categorias(tenant_id)

        return {
            "empresas": [
                {"id": empresa.id, "nome": empresa.nome_fantasia}
                for empresa in empresas
            ],
            "formas_pagamento": [
                {"id": forma.id, "nome": forma.nome}
                for forma in formas
            ],
            "categorias": {
                "ENTRADA": [
                    {"id": categoria.id, "nome": categoria.nome}
                    for categoria in categorias
                    if categoria.tipo_categoria == TipoCategoriaFinanceira.ENTRADA
                ],
                "SAIDA": [
                    {"id": categoria.id, "nome": categoria.nome}
                    for categoria in categorias
                    if categoria.tipo_categoria == TipoCategoriaFinanceira.SAIDA
                ],
            },
        }

    @staticmethod
    def listar_lancamentos(tenant_id, escopo, empresa_id=None, tipo=None, data_inicio=None, data_fim=None, limite=100):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        tipo_enum = FinanceiroService._to_optional_tipo_financeiro(tipo)
        data_inicio_obj = FinanceiroService._to_optional_date(data_inicio)
        data_fim_obj = FinanceiroService._to_optional_date(data_fim)

        lancamentos = FinanceiroRepository.listar_lancamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            tipo=tipo_enum,
            data_inicio=data_inicio_obj,
            data_fim=data_fim_obj,
            limite=limite,
        )

        return [FinanceiroService.serializar_lancamento(item) for item in lancamentos]

    @staticmethod
    def listar_fechamentos(tenant_id, escopo, empresa_id=None, limite=30):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        fechamentos = FinanceiroRepository.listar_fechamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            limite=limite,
        )

        dados = []
        for fechamento in fechamentos:
            resumo = FinanceiroService.calcular_resumo_caixa(
                tenant_id=tenant_id,
                escopo=escopo,
                empresa_id=fechamento.empresa_id,
                data_referencia=fechamento.data_fechamento,
                valor_inicial=fechamento.valor_inicial,
            )
            dados.append(FinanceiroService.serializar_fechamento(fechamento, resumo))

        return dados

    @staticmethod
    def obter_dashboard(tenant_id, escopo, empresa_id=None, periodo_dias=30):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        periodo = max(int(periodo_dias or 30), 1)
        data_fim = TimeService.today_br()
        data_inicio = data_fim - timedelta(days=periodo - 1)
        inicio_utc = TimeService.local_date_start_to_utc_naive(data_inicio)
        fim_utc = TimeService.local_date_start_to_utc_naive(data_fim + timedelta(days=1))
        data_lancamento_local = db.func.timezone(TimeService.TZ_BR.key,
            db.func.timezone("UTC", LancamentoFinanceiro.data_lancamento))

        base_lancamentos = FinanceiroRepository.query_lancamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        total_entradas = FinanceiroService._to_decimal_value(
            base_lancamentos
            .filter(LancamentoFinanceiro.tipo == TipoFinanceiro.ENTRADA)
            .with_entities(db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0))
            .scalar()
        )
        total_saidas = FinanceiroService._to_decimal_value(
            base_lancamentos
            .filter(LancamentoFinanceiro.tipo == TipoFinanceiro.SAIDA)
            .with_entities(db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0))
            .scalar()
        )

        base_vendas = (
            FinanceiroRepository.query_vendas(
                tenant_id=tenant_id,
                empresa_ids=empresa_ids,
                empresa_id=empresa_id,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )
            .filter(Venda.status == StatusVenda.FINALIZADA)
        )

        quantidade_vendas = base_vendas.count()
        base_cashback = Venda.total + Venda.cashback_utilizado
        cashback_restaurado = sa.case((base_cashback > 0,
            db.func.round(Venda.valor_cancelado * Venda.cashback_utilizado / base_cashback, 2)), else_=0)
        total_vendas = FinanceiroService._to_decimal_value(
            base_vendas.with_entities(db.func.coalesce(db.func.sum(
                Venda.total - Venda.valor_cancelado + cashback_restaurado), 0)).scalar()
        )
        ticket_medio = (
            (total_vendas / Decimal(quantidade_vendas)).quantize(Decimal("0.01"))
            if quantidade_vendas
            else Decimal("0.00")
        )
        saldo = (total_entradas - total_saidas).quantize(Decimal("0.01"))

        valor_estoque = FinanceiroService._to_decimal_value(
            db.session.query(
                db.func.coalesce(
                    db.func.sum(ProdutoEmpresa.estoque_atual * ProdutoEmpresa.valor_compra),
                    0,
                )
            )
            .filter(
                ProdutoEmpresa.tenant_id == tenant_id,
                ProdutoEmpresa.ativo.is_(True),
                ProdutoEmpresa.estoque_atual > 0,
                ProdutoEmpresa.empresa_id == empresa_id if empresa_id is not None else sa.true(),
                ProdutoEmpresa.empresa_id.in_(empresa_ids) if empresa_ids is not None else sa.true(),
            )
            .scalar()
        )

        custo_produtos_vendidos = FinanceiroService._to_decimal_value(
            db.session.query(
                db.func.coalesce(db.func.sum((ItemVenda.quantidade - ItemVenda.quantidade_cancelada) * ProdutoEmpresa.valor_compra), 0)
            )
            .select_from(ItemVenda)
            .join(Venda, Venda.id == ItemVenda.venda_id)
            .join(
                ProdutoEmpresa,
                db.and_(
                    ProdutoEmpresa.produto_id == ItemVenda.produto_id,
                    ProdutoEmpresa.empresa_id == Venda.empresa_id,
                    ProdutoEmpresa.tenant_id == tenant_id,
                ),
            )
            .filter(
                Venda.tenant_id == tenant_id,
                Venda.status == StatusVenda.FINALIZADA,
                Venda.data_venda >= inicio_utc,
                Venda.data_venda < fim_utc,
                Venda.empresa_id == empresa_id if empresa_id is not None else sa.true(),
                Venda.empresa_id.in_(empresa_ids) if empresa_ids is not None else sa.true(),
            )
            .scalar()
        )
        lucro_bruto = (total_vendas - custo_produtos_vendidos).quantize(Decimal("0.01"))
        margem_bruta = (
            ((lucro_bruto / total_vendas) * Decimal("100")).quantize(Decimal("0.01"))
            if total_vendas > 0
            else Decimal("0.00")
        )

        serie_query = (
            base_lancamentos
            .with_entities(
                db.func.date(data_lancamento_local).label("dia"),
                LancamentoFinanceiro.tipo.label("tipo"),
                db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0).label("valor"),
            )
            .group_by(
                db.func.date(data_lancamento_local),
                LancamentoFinanceiro.tipo,
            )
            .all()
        )

        serie_por_dia = {
            dia: {"data": dia.isoformat(), "entradas": Decimal("0.00"), "saidas": Decimal("0.00")}
            for dia in (data_inicio + timedelta(days=offset) for offset in range(periodo))
        }
        for item in serie_query:
            valor = FinanceiroService._to_decimal_value(item.valor)
            if item.tipo == TipoFinanceiro.ENTRADA:
                serie_por_dia[item.dia]["entradas"] = valor
            else:
                serie_por_dia[item.dia]["saidas"] = valor

        categorias_top = (
            base_lancamentos
            .join(LancamentoFinanceiro.categoria)
            .with_entities(
                db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0).label("valor"),
                LancamentoFinanceiro.tipo.label("tipo"),
                CategoriaFinanceira.nome.label("categoria_nome"),
            )
            .group_by(CategoriaFinanceira.nome, LancamentoFinanceiro.tipo)
            .order_by(db.desc("valor"))
            .limit(6)
            .all()
        )

        formas_pagamento = (
            base_lancamentos
            .join(LancamentoFinanceiro.forma_pagamento)
            .filter(LancamentoFinanceiro.tipo == TipoFinanceiro.ENTRADA)
            .with_entities(
                db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0).label("valor"),
                FormaPagamento.nome.label("forma_nome"),
            )
            .group_by(FormaPagamento.nome)
            .order_by(db.desc("valor"))
            .all()
        )

        mensal_query = (
            base_lancamentos
            .with_entities(
                db.extract("year", data_lancamento_local).label("ano"),
                db.extract("month", data_lancamento_local).label("mes"),
                LancamentoFinanceiro.tipo.label("tipo"),
                db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0).label("valor"),
            )
            .group_by(
                db.extract("year", data_lancamento_local),
                db.extract("month", data_lancamento_local),
                LancamentoFinanceiro.tipo,
            )
            .all()
        )
        mensal_map = {}
        for item in mensal_query:
            chave = f"{int(item.ano):04d}-{int(item.mes):02d}"
            if chave not in mensal_map:
                mensal_map[chave] = {
                    "competencia": chave,
                    "entradas": Decimal("0.00"),
                    "saidas": Decimal("0.00"),
                }
            if item.tipo == TipoFinanceiro.ENTRADA:
                mensal_map[chave]["entradas"] = FinanceiroService._to_decimal_value(item.valor)
            else:
                mensal_map[chave]["saidas"] = FinanceiroService._to_decimal_value(item.valor)

        mensal_resumo = []
        for chave in sorted(mensal_map.keys(), reverse=True)[:6]:
            entradas = mensal_map[chave]["entradas"]
            saidas = mensal_map[chave]["saidas"]
            mensal_resumo.append(
                {
                    "competencia": chave,
                    "entradas": str(entradas),
                    "saidas": str(saidas),
                    "saldo": str((entradas - saidas).quantize(Decimal("0.01"))),
                }
            )

        saldo_medio_diario = (saldo / Decimal(periodo)).quantize(Decimal("0.01")) if periodo else Decimal("0.00")
        projecoes = []
        for dias in (30, 60, 90):
            variacao = (saldo_medio_diario * Decimal(dias)).quantize(Decimal("0.01"))
            projecoes.append(
                {
                    "dias": dias,
                    "saldo_medio_diario": str(saldo_medio_diario),
                    "variacao_prevista": str(variacao),
                    "saldo_projetado": str((saldo + variacao).quantize(Decimal("0.01"))),
                }
            )

        vendas_30_dias = (
            db.session.query(
                Produto.id.label("produto_id"),
                Produto.nome.label("produto_nome"),
                db.func.coalesce(db.func.sum(ItemVenda.quantidade - ItemVenda.quantidade_cancelada), 0).label("quantidade"),
                ProdutoEmpresa.estoque_atual.label("estoque_atual"),
                ProdutoEmpresa.estoque_minimo.label("estoque_minimo"),
                ProdutoEmpresa.valor_compra.label("valor_compra"),
                ProdutoEmpresa.valor_venda.label("valor_venda"),
            )
            .join(ItemVenda, ItemVenda.produto_id == Produto.id)
            .join(Venda, Venda.id == ItemVenda.venda_id)
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
                Venda.data_venda >= TimeService.local_date_start_to_utc_naive(data_fim - timedelta(days=29)),
                Venda.data_venda < fim_utc,
                ItemVenda.quantidade > ItemVenda.quantidade_cancelada,
                Venda.empresa_id == empresa_id if empresa_id is not None else sa.true(),
                Venda.empresa_id.in_(empresa_ids) if empresa_ids is not None else sa.true(),
            )
            .group_by(
                Produto.id,
                Produto.nome,
                ProdutoEmpresa.estoque_atual,
                ProdutoEmpresa.estoque_minimo,
                ProdutoEmpresa.valor_compra,
                ProdutoEmpresa.valor_venda,
            )
            .order_by(db.desc("quantidade"))
            .limit(8)
            .all()
        )
        recomendacoes_compra = []
        necessidade_compra = Decimal("0.00")
        for item in vendas_30_dias:
            quantidade_vendida = int(item.quantidade or 0)
            media_diaria = Decimal(quantidade_vendida) / Decimal("30")
            estoque_atual = int(item.estoque_atual or 0)
            estoque_minimo = int(item.estoque_minimo or 0)
            estoque_ideal = max(int((media_diaria * Decimal("30")).quantize(Decimal("1"))), estoque_minimo)
            quantidade_sugerida = max(estoque_ideal - estoque_atual, 0)
            cobertura_dias = (
                Decimal(estoque_atual) / media_diaria
                if media_diaria > 0
                else Decimal("0.00")
            ).quantize(Decimal("0.01"))
            valor_compra_sugerido = (Decimal(quantidade_sugerida) * FinanceiroService._to_decimal_value(item.valor_compra)).quantize(Decimal("0.01"))
            necessidade_compra += valor_compra_sugerido
            recomendacoes_compra.append(
                {
                    "produto_id": item.produto_id,
                    "produto_nome": item.produto_nome,
                    "quantidade_vendida": quantidade_vendida,
                    "media_diaria": str(media_diaria.quantize(Decimal("0.01"))),
                    "estoque_atual": estoque_atual,
                    "cobertura_dias": str(cobertura_dias),
                    "quantidade_sugerida": quantidade_sugerida,
                    "valor_compra_sugerido": str(valor_compra_sugerido),
                }
            )

        caixa_hoje = FinanceiroService.calcular_resumo_caixa(
            tenant_id=tenant_id,
            escopo=escopo,
            empresa_id=empresa_id,
            data_referencia=data_fim,
            valor_inicial=Decimal("0.00"),
        )

        return {
            "periodo": {
                "dias": periodo,
                "data_inicio": data_inicio.isoformat(),
                "data_fim": data_fim.isoformat(),
            },
            "kpis": {
                "entradas": str(total_entradas),
                "saidas": str(total_saidas),
                "saldo": str(saldo),
                "vendas": quantidade_vendas,
                "faturamento": str(total_vendas),
                "ticket_medio": str(ticket_medio),
                "valor_estoque": str(valor_estoque),
                "lucro_bruto": str(lucro_bruto),
                "margem_bruta": str(margem_bruta),
                "necessidade_compra": str(necessidade_compra.quantize(Decimal("0.01"))),
            },
            "serie_diaria": [
                {
                    "data": item["data"],
                    "entradas": str(item["entradas"]),
                    "saidas": str(item["saidas"]),
                }
                for item in serie_por_dia.values()
            ],
            "categorias_top": [
                {
                    "categoria_nome": item.categoria_nome,
                    "tipo": item.tipo.value,
                    "valor": str(FinanceiroService._to_decimal_value(item.valor)),
                }
                for item in categorias_top
            ],
            "formas_pagamento": [
                {
                    "forma_nome": item.forma_nome,
                    "valor": str(FinanceiroService._to_decimal_value(item.valor)),
                }
                for item in formas_pagamento
            ],
            "mensal_resumo": mensal_resumo,
            "projecoes": projecoes,
            "recomendacoes_compra": recomendacoes_compra,
            "caixa_hoje": {
                "data": data_fim.isoformat(),
                "entradas_dinheiro": str(caixa_hoje["entradas_dinheiro"]),
                "saidas_dinheiro": str(caixa_hoje["saidas_dinheiro"]),
                "saldo_dinheiro": str(caixa_hoje["saldo_dinheiro"]),
                "saldo_esperado": str(caixa_hoje["saldo_esperado"]),
            },
        }

    @staticmethod
    @atomic_operation
    @idempotent
    def criar_lancamento_manual(data, tenant_id, escopo, funcionario_id):
        try:
            FinanceiroService._garantir_base_operacional(tenant_id)

            empresa_id = FinanceiroService._to_int(data.get("empresa_id"), "Empresa")
            tipo = FinanceiroService._to_tipo_financeiro(data.get("tipo"))
            categoria_id = FinanceiroService._to_int(data.get("categoria_id"), "Categoria")
            forma_pagamento_id = FinanceiroService._to_int(data.get("forma_pagamento_id"), "Forma de pagamento")
            descricao = (data.get("descricao") or "").strip()
            valor = FinanceiroService._to_decimal(data.get("valor"), "valor")
            observacao = (data.get("observacao") or "").strip() or None
            data_competencia = FinanceiroService._to_optional_date(data.get("data_competencia"))

            if not descricao:
                raise ValueError("Descricao e obrigatoria.")

            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

            categoria = FinanceiroRepository.buscar_categoria_por_id(categoria_id, tenant_id)
            if not categoria or not categoria.ativo:
                raise ValueError("Categoria financeira nao encontrada.")

            if categoria.tipo_categoria.value != tipo.value:
                raise ValueError("A categoria informada nao corresponde ao tipo do lancamento.")

            forma_pagamento = FinanceiroRepository.buscar_forma_pagamento_por_id(forma_pagamento_id, tenant_id)
            if not forma_pagamento or not forma_pagamento.ativo:
                raise ValueError("Forma de pagamento nao encontrada.")

            lancamento = LancamentoFinanceiro(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=funcionario_id,
                categoria_id=categoria.id,
                forma_pagamento_id=forma_pagamento.id,
                tipo=tipo,
                descricao=descricao,
                valor=valor,
                data_lancamento=TimeService.now_utc_naive(),
                data_competencia=data_competencia,
                observacao=observacao,
            )
            FinanceiroRepository.adicionar(lancamento)
            FinanceiroRepository.salvar()
            return FinanceiroService.serializar_lancamento(lancamento)
        except Exception:
            FinanceiroRepository.rollback()
            raise

    @staticmethod
    def registrar_entradas_da_venda(venda, pagamentos, tenant_id, funcionario_id=None, persistir=True):
        try:
            categoria = FinanceiroRepository.buscar_categoria_por_nome(
                FinanceiroService.CATEGORIA_VENDA,
                TipoCategoriaFinanceira.ENTRADA,
                tenant_id,
            )
            if not categoria:
                raise ValueError("Categoria padrao de vendas nao encontrada.")

            for pagamento in pagamentos:
                descricao = f"Venda {venda.numero_unico}"
                if getattr(pagamento, "forma_pagamento", None):
                    descricao = f"{descricao} - {pagamento.forma_pagamento.nome}"

                FinanceiroRepository.adicionar(
                    LancamentoFinanceiro(
                        tenant_id=tenant_id,
                        empresa_id=venda.empresa_id,
                        funcionario_id=funcionario_id,
                        categoria_id=categoria.id,
                        forma_pagamento_id=pagamento.forma_pagamento_id,
                        venda_id=venda.id,
                        tipo=TipoFinanceiro.ENTRADA,
                        descricao=descricao,
                        valor=FinanceiroService._to_decimal_value(pagamento.valor),
                        data_lancamento=TimeService.now_utc_naive(),
                        data_competencia=TimeService.today_br(),
                        observacao="Entrada automatica gerada pelo fechamento da venda no PDV.",
                    )
                )

            if persistir:
                FinanceiroRepository.salvar()
        except Exception:
            if persistir:
                FinanceiroRepository.rollback()
            raise

    @staticmethod
    def registrar_estorno_da_venda(venda, tenant_id, funcionario_id=None, persistir=True):
        try:
            categoria = FinanceiroRepository.buscar_categoria_por_nome(
                FinanceiroService.CATEGORIA_ESTORNO,
                TipoCategoriaFinanceira.SAIDA,
                tenant_id,
            )
            if not categoria:
                raise ValueError("Categoria padrao de estorno nao encontrada.")

            lancamentos_origem = (
                FinanceiroRepository.query_lancamentos(tenant_id=tenant_id, empresa_id=venda.empresa_id)
                .options(joinedload(LancamentoFinanceiro.forma_pagamento))
                .filter(
                    LancamentoFinanceiro.venda_id == venda.id,
                    LancamentoFinanceiro.tipo == TipoFinanceiro.ENTRADA,
                )
                .all()
            )

            for pagamento, lancamento_origem in zip(venda.pagamentos, lancamentos_origem):
                descricao = f"Estorno da venda {venda.numero_unico}"
                forma_pagamento = pagamento.forma_pagamento or getattr(lancamento_origem, "forma_pagamento", None)
                if forma_pagamento:
                    descricao = f"{descricao} - {forma_pagamento.nome}"

                if lancamento_origem:
                    lancamento_origem.revertido = True

                FinanceiroRepository.adicionar(
                    LancamentoFinanceiro(
                        tenant_id=tenant_id,
                        empresa_id=venda.empresa_id,
                        funcionario_id=funcionario_id,
                        categoria_id=categoria.id,
                        forma_pagamento_id=pagamento.forma_pagamento_id,
                        venda_id=venda.id,
                        lancamento_origem_id=lancamento_origem.id if lancamento_origem else None,
                        tipo=TipoFinanceiro.SAIDA,
                        descricao=descricao,
                        valor=FinanceiroService._to_decimal_value(pagamento.valor),
                        data_lancamento=TimeService.now_utc_naive(),
                        data_competencia=TimeService.today_br(),
                        observacao="Saida automatica gerada pelo cancelamento da venda no PDV.",
                    )
                )

            if persistir:
                FinanceiroRepository.salvar()
        except Exception:
            if persistir:
                FinanceiroRepository.rollback()
            raise

    @staticmethod
    def registrar_estorno_parcial_da_venda(venda, item_venda, valor_estorno, tenant_id, funcionario_id=None, persistir=True):
        try:
            valor_total_estorno = FinanceiroService._to_non_negative_decimal(valor_estorno, "valor de estorno")
            if valor_total_estorno <= Decimal("0.00"):
                return []

            categoria = FinanceiroRepository.buscar_categoria_por_nome(
                FinanceiroService.CATEGORIA_ESTORNO,
                TipoCategoriaFinanceira.SAIDA,
                tenant_id,
            )
            if not categoria:
                raise ValueError("Categoria padrao de estorno nao encontrada.")

            lancamentos_origem = (
                FinanceiroRepository.query_lancamentos(tenant_id=tenant_id, empresa_id=venda.empresa_id)
                .options(joinedload(LancamentoFinanceiro.forma_pagamento))
                .filter(
                    LancamentoFinanceiro.venda_id == venda.id,
                    LancamentoFinanceiro.tipo == TipoFinanceiro.ENTRADA,
                )
                .order_by(LancamentoFinanceiro.id.asc())
                .all()
            )
            if not lancamentos_origem:
                raise ValueError("Nao foi possivel localizar os lancamentos financeiros da venda.")

            balances = []
            for source in lancamentos_origem:
                refunded = sum((record.valor for record in LancamentoFinanceiro.query.filter_by(
                    tenant_id=tenant_id, lancamento_origem_id=source.id, tipo=TipoFinanceiro.SAIDA
                ).all()), Decimal("0.00"))
                balances.append(source.valor - refunded)
            portions = allocate_money(valor_total_estorno, balances)
            estornos = []
            for lancamento_origem, valor_lancamento in zip(lancamentos_origem, portions):
                if valor_lancamento <= Decimal("0.00"):
                    continue

                descricao = f"Estorno parcial da venda {venda.numero_unico}"
                if lancamento_origem.forma_pagamento:
                    descricao = f"{descricao} - {lancamento_origem.forma_pagamento.nome}"

                estorno = LancamentoFinanceiro(
                    tenant_id=tenant_id,
                    empresa_id=venda.empresa_id,
                    funcionario_id=funcionario_id,
                    categoria_id=categoria.id,
                    forma_pagamento_id=lancamento_origem.forma_pagamento_id,
                    venda_id=venda.id,
                    item_venda_id=item_venda.id if item_venda else None,
                    lancamento_origem_id=lancamento_origem.id,
                    tipo=TipoFinanceiro.SAIDA,
                    descricao=descricao,
                    valor=valor_lancamento,
                    data_lancamento=TimeService.now_utc_naive(),
                    data_competencia=TimeService.today_br(),
                    observacao="Saida automatica gerada pelo cancelamento parcial de item no PDV.",
                )
                FinanceiroRepository.adicionar(estorno)
                estornos.append(estorno)

            if persistir:
                FinanceiroRepository.salvar()
            return estornos
        except Exception:
            if persistir:
                FinanceiroRepository.rollback()
            raise

    @staticmethod
    def registrar_saida_adiantamento(
        tenant_id,
        empresa_id,
        funcionario_id,
        forma_pagamento_id,
        valor,
        descricao,
        data_competencia=None,
        observacao=None,
        persistir=True,
    ):
        try:
            categoria = FinanceiroRepository.buscar_categoria_por_nome(
                FinanceiroService.CATEGORIA_ADIANTAMENTO,
                TipoCategoriaFinanceira.SAIDA,
                tenant_id,
            )
            if not categoria:
                raise ValueError("Categoria padrao de adiantamento nao encontrada.")

            forma_pagamento = FinanceiroRepository.buscar_forma_pagamento_por_id(forma_pagamento_id, tenant_id)
            if not forma_pagamento or not forma_pagamento.ativo:
                raise ValueError("Forma de pagamento nao encontrada.")

            lancamento = LancamentoFinanceiro(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=funcionario_id,
                categoria_id=categoria.id,
                forma_pagamento_id=forma_pagamento.id,
                tipo=TipoFinanceiro.SAIDA,
                descricao=descricao,
                valor=FinanceiroService._to_decimal_value(valor),
                data_lancamento=TimeService.now_utc_naive(),
                data_competencia=data_competencia,
                observacao=observacao,
            )
            FinanceiroRepository.adicionar(lancamento)
            FinanceiroRepository.flush()

            if persistir:
                FinanceiroRepository.salvar()

            return lancamento
        except Exception:
            if persistir:
                FinanceiroRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def criar_fechamento(data, tenant_id, escopo, funcionario_id):
        try:
            FinanceiroService._garantir_base_operacional(tenant_id)

            empresa_id = FinanceiroService._to_int(data.get("empresa_id"), "Empresa")
            data_fechamento = FinanceiroService._to_optional_date(data.get("data_fechamento")) or TimeService.today_br()
            valor_inicial = FinanceiroService._to_non_negative_decimal(data.get("valor_inicial"), "valor inicial")
            valor_final = FinanceiroService._to_non_negative_decimal(data.get("valor_final"), "valor final")
            observacao = (data.get("observacao") or "").strip() or None

            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

            if FinanceiroRepository.buscar_fechamento_existente(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=funcionario_id,
                data_fechamento=data_fechamento,
            ):
                raise ValueError("Ja existe um fechamento de caixa para esse operador nesta data.")

            fechamento = FechamentoCaixa(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=funcionario_id,
                data_fechamento=data_fechamento,
                valor_inicial=valor_inicial,
                valor_final=valor_final,
                observacao=observacao,
            )
            FinanceiroRepository.adicionar(fechamento)
            FinanceiroRepository.salvar()

            resumo = FinanceiroService.calcular_resumo_caixa(
                tenant_id=tenant_id,
                escopo=escopo,
                empresa_id=empresa_id,
                data_referencia=data_fechamento,
                valor_inicial=valor_inicial,
            )
            from app.services.financeiro_ciclo_service import FinanceiroCicloService, audit
            reconciliation = FinanceiroCicloService.conciliar(tenant_id, escopo, empresa_id,
                data_fechamento.isoformat(), data_fechamento.isoformat())
            if not reconciliation["conciliado"]:
                raise ValueError("Divergencia PDV e financeiro impede fechar o caixa.")
            fechamento.conciliacao = {"caixa": {key: str(value) for key, value in resumo.items()}, "pdv": reconciliation}
            audit("CAIXA_CRIADO", fechamento, funcionario_id, {"conciliacao": fechamento.conciliacao})
            return FinanceiroService.serializar_fechamento(fechamento, resumo)
        except Exception:
            FinanceiroRepository.rollback()
            raise

    @staticmethod
    def calcular_resumo_caixa(tenant_id, escopo, empresa_id=None, data_referencia=None, valor_inicial=None):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        data_ref = data_referencia or TimeService.today_br()
        valor_inicial_decimal = FinanceiroService._to_decimal_value(valor_inicial or 0)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        forma_dinheiro = FinanceiroRepository.buscar_forma_pagamento_por_nome(
            FinanceiroService.FORMA_DINHEIRO,
            tenant_id,
        )
        if not forma_dinheiro:
            return {
                "entradas_dinheiro": Decimal("0.00"),
                "saidas_dinheiro": Decimal("0.00"),
                "saldo_dinheiro": Decimal("0.00"),
                "saldo_esperado": valor_inicial_decimal,
            }

        base = FinanceiroRepository.query_lancamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            data_inicio=data_ref,
            data_fim=data_ref,
        ).filter(LancamentoFinanceiro.forma_pagamento_id == forma_dinheiro.id)

        entradas = FinanceiroService._to_decimal_value(
            base.filter(LancamentoFinanceiro.tipo == TipoFinanceiro.ENTRADA)
            .with_entities(db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0))
            .scalar()
        )
        saidas = FinanceiroService._to_decimal_value(
            base.filter(LancamentoFinanceiro.tipo == TipoFinanceiro.SAIDA)
            .with_entities(db.func.coalesce(db.func.sum(LancamentoFinanceiro.valor), 0))
            .scalar()
        )
        saldo_dinheiro = (entradas - saidas).quantize(Decimal("0.01"))

        return {
            "entradas_dinheiro": entradas,
            "saidas_dinheiro": saidas,
            "saldo_dinheiro": saldo_dinheiro,
            "saldo_esperado": (valor_inicial_decimal + saldo_dinheiro).quantize(Decimal("0.01")),
        }

    @staticmethod
    def serializar_lancamento(lancamento):
        if getattr(lancamento, "adiantamentos", None):
            origem = "VALE"
        elif lancamento.venda_id:
            origem = "PDV"
        else:
            origem = "MANUAL"

        return {
            "id": lancamento.id,
            "empresa_id": lancamento.empresa_id,
            "empresa_nome": lancamento.empresa.nome_fantasia if lancamento.empresa else None,
            "funcionario_nome": lancamento.funcionario.nome if lancamento.funcionario else None,
            "categoria_id": lancamento.categoria_id,
            "categoria_nome": lancamento.categoria.nome if lancamento.categoria else None,
            "forma_pagamento_id": lancamento.forma_pagamento_id,
            "forma_pagamento_nome": lancamento.forma_pagamento.nome if lancamento.forma_pagamento else None,
            "venda_id": lancamento.venda_id,
            "item_venda_id": getattr(lancamento, "item_venda_id", None),
            "lancamento_origem_id": getattr(lancamento, "lancamento_origem_id", None),
            "tipo": lancamento.tipo.value,
            "descricao": lancamento.descricao,
            "valor": str(FinanceiroService._to_decimal_value(lancamento.valor)),
            "revertido": bool(getattr(lancamento, "revertido", False)),
            "data_lancamento": TimeService.serialize_utc_iso(lancamento.data_lancamento),
            "data_competencia": lancamento.data_competencia.isoformat() if lancamento.data_competencia else None,
            "observacao": lancamento.observacao,
            "origem": origem,
        }

    @staticmethod
    def serializar_fechamento(fechamento, resumo):
        valor_final = FinanceiroService._to_decimal_value(fechamento.valor_final)
        saldo_esperado = FinanceiroService._to_decimal_value(resumo["saldo_esperado"])

        return {
            "status": fechamento.status,
            "revisao": fechamento.revisao,
            "conciliacao": fechamento.conciliacao,
            "id": fechamento.id,
            "empresa_id": fechamento.empresa_id,
            "empresa_nome": fechamento.empresa.nome_fantasia if fechamento.empresa else None,
            "funcionario_id": fechamento.funcionario_id,
            "funcionario_nome": fechamento.funcionario.nome if fechamento.funcionario else None,
            "data_fechamento": fechamento.data_fechamento.isoformat(),
            "valor_inicial": str(FinanceiroService._to_decimal_value(fechamento.valor_inicial)),
            "valor_final": str(valor_final),
            "valor_sistema": str(saldo_esperado),
            "diferenca": str((valor_final - saldo_esperado).quantize(Decimal("0.01"))),
            "observacao": fechamento.observacao,
        }

    @staticmethod
    def obter_relatorio_fluxo_caixa(tenant_id, escopo, empresa_id=None, data_inicio=None, data_fim=None):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        data_inicio_obj, data_fim_obj = FinanceiroService._resolver_periodo_relatorio(data_inicio, data_fim)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        lancamentos = FinanceiroRepository.listar_lancamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            data_inicio=data_inicio_obj,
            data_fim=data_fim_obj,
            limite=None,
        )

        total_entradas = Decimal("0.00")
        total_saidas = Decimal("0.00")

        linhas = []
        for lancamento in lancamentos:
            valor = FinanceiroService._to_decimal_value(lancamento.valor)
            if lancamento.tipo == TipoFinanceiro.ENTRADA:
                total_entradas += valor
            else:
                total_saidas += valor

            linhas.append(FinanceiroService.serializar_lancamento(lancamento))

        return {
            "periodo": {
                "data_inicio": data_inicio_obj.isoformat(),
                "data_fim": data_fim_obj.isoformat(),
            },
            "totais": {
                "entradas": str(total_entradas.quantize(Decimal("0.01"))),
                "saidas": str(total_saidas.quantize(Decimal("0.01"))),
                "saldo": str((total_entradas - total_saidas).quantize(Decimal("0.01"))),
                "registros": len(linhas),
            },
            "lancamentos": linhas,
        }

    @staticmethod
    def obter_relatorio_produtos_vendidos(tenant_id, escopo, empresa_id=None, data_inicio=None, data_fim=None, limite=30):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        data_inicio_obj, data_fim_obj = FinanceiroService._resolver_periodo_relatorio(data_inicio, data_fim)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        base_vendas = (
            FinanceiroRepository.query_vendas(
                tenant_id=tenant_id,
                empresa_ids=empresa_ids,
                empresa_id=empresa_id,
                data_inicio=data_inicio_obj,
                data_fim=data_fim_obj,
            )
            .filter(Venda.status == StatusVenda.FINALIZADA)
        )

        itens = (
            base_vendas
            .join(ItemVenda, ItemVenda.venda_id == Venda.id)
            .join(Produto, Produto.id == ItemVenda.produto_id)
            .filter(ItemVenda.quantidade > ItemVenda.quantidade_cancelada)
            .with_entities(
                Produto.id.label("produto_id"),
                Produto.nome.label("produto_nome"),
                db.func.coalesce(db.func.sum(ItemVenda.quantidade - ItemVenda.quantidade_cancelada), 0).label("quantidade"),
                db.func.coalesce(db.func.sum((ItemVenda.quantidade - ItemVenda.quantidade_cancelada) * ItemVenda.valor_unitario), 0).label("faturamento"),
            )
            .group_by(Produto.id, Produto.nome)
            .order_by(db.desc("quantidade"), db.desc("faturamento"))
            .limit(max(int(limite or 30), 1))
            .all()
        )

        total_quantidade = 0
        total_faturamento = Decimal("0.00")
        linhas = []

        for item in itens:
            quantidade = int(item.quantidade or 0)
            faturamento = FinanceiroService._to_decimal_value(item.faturamento)
            total_quantidade += quantidade
            total_faturamento += faturamento
            linhas.append(
                {
                    "produto_id": item.produto_id,
                    "produto_nome": item.produto_nome,
                    "quantidade": quantidade,
                    "faturamento": str(faturamento),
                }
            )

        return {
            "periodo": {
                "data_inicio": data_inicio_obj.isoformat(),
                "data_fim": data_fim_obj.isoformat(),
            },
            "totais": {
                "quantidade": total_quantidade,
                "faturamento": str(total_faturamento.quantize(Decimal("0.01"))),
                "produtos": len(linhas),
            },
            "itens": linhas,
        }

    @staticmethod
    def _garantir_base_operacional(tenant_id):
        try:
            TenantBootstrapService.garantir_cadastros_operacionais(tenant_id)
            FinanceiroRepository.salvar()
        except Exception:
            FinanceiroRepository.rollback()
            raise

    @staticmethod
    def _to_tipo_financeiro(value):
        try:
            return TipoFinanceiro[(value or "").strip().upper()]
        except KeyError:
            raise ValueError("Tipo de lancamento invalido.")

    @staticmethod
    def _to_optional_tipo_financeiro(value):
        if value in (None, ""):
            return None
        return FinanceiroService._to_tipo_financeiro(value)

    @staticmethod
    def _to_int(value, field_name):
        from app.services.money_service import positive_integer
        return positive_integer(value, field_name)

    @staticmethod
    def _to_decimal(value, field_name):
        from app.services.money_service import money
        return money(value, field_name)

    @staticmethod
    def _to_non_negative_decimal(value, field_name):
        from app.services.money_service import money
        return money(0 if value in (None, "") else value, field_name, allow_zero=True)

    @staticmethod
    def _to_optional_date(value):
        if value in (None, ""):
            return None

        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data invalida. Use o formato YYYY-MM-DD.")

    @staticmethod
    def _to_decimal_value(value):
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.01"))

        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _resolver_periodo_relatorio(data_inicio, data_fim):
        hoje = TimeService.today_br()
        inicio = FinanceiroService._to_optional_date(data_inicio) or date(hoje.year, hoje.month, 1)
        fim = FinanceiroService._to_optional_date(data_fim) or hoje

        if fim < inicio:
            raise ValueError("A data final nao pode ser menor que a data inicial.")

        return inicio, fim
