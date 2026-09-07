from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.models.db import AdiantamentoFuncionario, TipoAdiantamentoFuncionario
from app.repositorys.adiantamento_repository import AdiantamentoRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.estoque_service import EstoqueService
from app.services.financeiro_service import FinanceiroService
from app.services.tenant_bootstrap_service import TenantBootstrapService
from app.services.time_service import TimeService


from app.services.transaction_service import atomic_operation


class AdiantamentoService:
    FORMA_PADRAO = "Vale em folha"

    @staticmethod
    def listar_auxiliares(tenant_id, escopo):
        AdiantamentoService._garantir_base_operacional(tenant_id)

        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        empresas = AdiantamentoRepository.listar_empresas(tenant_id, empresa_ids=empresa_ids)
        vinculos = AdiantamentoRepository.listar_funcionarios_vinculados(tenant_id, empresa_ids=empresa_ids)
        produtos_empresa = AdiantamentoRepository.listar_produtos_empresa(tenant_id, empresa_ids=empresa_ids)
        formas = AdiantamentoRepository.listar_formas_pagamento(tenant_id)

        funcionarios = {}
        for vinculo in vinculos:
            funcionario = vinculo.funcionario
            empresa = vinculo.empresa
            if not funcionario or not empresa:
                continue

            item = funcionarios.setdefault(
                funcionario.id,
                {
                    "id": funcionario.id,
                    "nome": funcionario.nome,
                    "salario": str(AdiantamentoService._to_decimal_value(funcionario.salario)),
                    "meta": str(AdiantamentoService._to_decimal_value(funcionario.meta)),
                    "empresa_ids": [],
                    "empresa_nomes": [],
                },
            )

            item["empresa_ids"].append(empresa.id)
            item["empresa_nomes"].append(empresa.nome_fantasia)

        return {
            "empresas": [{"id": empresa.id, "nome": empresa.nome_fantasia} for empresa in empresas],
            "funcionarios": list(funcionarios.values()),
            "formas_pagamento": [{"id": forma.id, "nome": forma.nome} for forma in formas],
            "produtos": [
                {
                    "id": item.produto.id,
                    "produto_empresa_id": item.id,
                    "empresa_id": item.empresa_id,
                    "empresa_nome": item.empresa.nome_fantasia if item.empresa else None,
                    "nome": item.produto.nome if item.produto else None,
                    "categoria_nome": item.produto.categoria.nome if item.produto and item.produto.categoria else "",
                    "estoque_atual": int(item.estoque_atual),
                    "valor_venda": str(AdiantamentoService._to_decimal_value(item.valor_venda)),
                }
                for item in produtos_empresa
            ],
        }

    @staticmethod
    def listar(tenant_id, escopo, empresa_id=None, funcionario_id=None, competencia=None, limite=100):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        itens = AdiantamentoRepository.listar_adiantamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            funcionario_id=funcionario_id,
            competencia=AdiantamentoService._to_optional_competencia(competencia),
            limite=limite,
        )

        return [AdiantamentoService.serializar(item) for item in itens]

    @staticmethod
    def obter_resumo_folha(tenant_id, escopo, empresa_id=None, competencia=None):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        competencia_date = AdiantamentoService._to_optional_competencia(competencia) or AdiantamentoService._competencia_atual()

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        vinculos = AdiantamentoRepository.listar_funcionarios_vinculados(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
        )
        adiantamentos = AdiantamentoRepository.listar_adiantamentos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            competencia=competencia_date,
            limite=None,
        )

        totais_por_funcionario = {}
        for item in adiantamentos:
            if item.status not in ("AUTORIZADO", "BAIXADO"):
                continue
            atual = totais_por_funcionario.setdefault(
                item.funcionario_id,
                {
                    "total": Decimal("0.00"),
                    "dinheiro": Decimal("0.00"),
                    "produto": Decimal("0.00"),
                    "quantidade": 0,
                },
            )
            valor = AdiantamentoService._to_decimal_value(item.valor_total)
            atual["total"] += valor
            atual["quantidade"] += 1
            if item.tipo_adiantamento == TipoAdiantamentoFuncionario.DINHEIRO:
                atual["dinheiro"] += valor
            else:
                atual["produto"] += valor

        funcionarios = {}
        for vinculo in vinculos:
            funcionario = vinculo.funcionario
            empresa = vinculo.empresa
            if not funcionario or not empresa:
                continue

            resumo = funcionarios.setdefault(
                funcionario.id,
                {
                    "funcionario_id": funcionario.id,
                    "funcionario_nome": funcionario.nome,
                    "salario_base": Decimal("0.00"),
                    "empresa_ids": set(),
                    "empresa_nomes": set(),
                },
            )
            resumo["salario_base"] = AdiantamentoService._to_decimal_value(funcionario.salario)
            resumo["empresa_ids"].add(empresa.id)
            resumo["empresa_nomes"].add(empresa.nome_fantasia)

        linhas = []
        for funcionario_id, item in funcionarios.items():
            totais = totais_por_funcionario.get(
                funcionario_id,
                {
                    "total": Decimal("0.00"),
                    "dinheiro": Decimal("0.00"),
                    "produto": Decimal("0.00"),
                    "quantidade": 0,
                },
            )
            salario_base = item["salario_base"]
            total_adiantado = totais["total"].quantize(Decimal("0.01"))
            saldo_a_pagar = (salario_base - total_adiantado).quantize(Decimal("0.01"))

            linhas.append(
                {
                    "funcionario_id": funcionario_id,
                    "funcionario_nome": item["funcionario_nome"],
                    "empresa_nomes": ", ".join(sorted(item["empresa_nomes"])),
                    "competencia": competencia_date.isoformat(),
                    "salario_base": str(salario_base),
                    "total_adiantado": str(total_adiantado),
                    "adiantamento_dinheiro": str(totais["dinheiro"].quantize(Decimal("0.01"))),
                    "adiantamento_produto": str(totais["produto"].quantize(Decimal("0.01"))),
                    "saldo_a_pagar": str(saldo_a_pagar),
                    "quantidade_registros": totais["quantidade"],
                }
            )

        linhas.sort(key=lambda item: item["funcionario_nome"].lower())
        total_salarios = sum((Decimal(item["salario_base"]) for item in linhas), Decimal("0.00")).quantize(Decimal("0.01"))
        total_adiantado = sum((Decimal(item["total_adiantado"]) for item in linhas), Decimal("0.00")).quantize(Decimal("0.01"))
        total_saldo = sum((Decimal(item["saldo_a_pagar"]) for item in linhas), Decimal("0.00")).quantize(Decimal("0.01"))

        return {
            "competencia": competencia_date.isoformat(),
            "totais": {
                "salarios": str(total_salarios),
                "adiantado": str(total_adiantado),
                "saldo_a_pagar": str(total_saldo),
                "funcionarios": len(linhas),
            },
            "funcionarios": linhas,
        }

    @staticmethod
    @atomic_operation
    def criar(data, tenant_id, escopo, responsavel_id):
        try:
            AdiantamentoService._garantir_base_operacional(tenant_id)

            empresa_id = AdiantamentoService._to_int(data.get("empresa_id"), "Empresa")
            funcionario_id = AdiantamentoService._to_int(data.get("funcionario_id"), "Funcionario")
            tipo = AdiantamentoService._to_tipo_adiantamento(data.get("tipo_adiantamento"))
            forma_pagamento_id = AdiantamentoService._to_optional_int(data.get("forma_pagamento_id"))
            data_adiantamento = AdiantamentoService._to_optional_date(data.get("data_adiantamento")) or TimeService.today_br()
            competencia = AdiantamentoService._to_optional_competencia(data.get("competencia")) or AdiantamentoService._competencia_atual()
            observacao = (data.get("observacao") or "").strip() or None
            pendente = data.get("solicitar") is True

            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            vinculo = AdiantamentoRepository.buscar_vinculo_funcionario(
                funcionario_id=funcionario_id,
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                empresa_ids=empresa_ids,
            )
            if not vinculo or not vinculo.funcionario:
                raise ValueError("Funcionario nao encontrado ou sem vinculo com a empresa informada.")

            forma_pagamento = AdiantamentoService._resolver_forma_pagamento(tenant_id, forma_pagamento_id)
            funcionario = vinculo.funcionario

            produto = None
            quantidade = None
            valor_unitario = None

            if tipo == TipoAdiantamentoFuncionario.DINHEIRO:
                valor_total = AdiantamentoService._to_decimal(data.get("valor_total"), "valor total")
                descricao = (data.get("descricao") or "").strip() or f"Adiantamento em dinheiro - {funcionario.nome}"
                observacao_lancamento = observacao or "Lancamento automatico de adiantamento em folha."
                movimento = None
            else:
                produto_id = AdiantamentoService._to_int(data.get("produto_id"), "Produto")
                quantidade = AdiantamentoService._to_positive_int(data.get("quantidade"), "quantidade")
                produto_empresa = AdiantamentoRepository.buscar_produto_empresa(
                    produto_id=produto_id,
                    tenant_id=tenant_id,
                    empresa_id=empresa_id,
                )
                if not produto_empresa or not produto_empresa.produto:
                    raise ValueError("Produto nao encontrado para a empresa informada.")

                produto = produto_empresa.produto
                valor_unitario = AdiantamentoService._to_decimal_value(produto_empresa.valor_venda)
                valor_total = (valor_unitario * quantidade).quantize(Decimal("0.01"))
                descricao = (data.get("descricao") or "").strip() or f"Vale em produto - {produto.nome}"
                observacao_lancamento = observacao or "Saida automatica de vale em produto para desconto em folha."

                movimento = None if pendente else EstoqueService.registrar_saida_por_adiantamento(
                    tenant_id=tenant_id,
                    empresa_id=empresa_id,
                    produto_id=produto.id,
                    quantidade=quantidade,
                    funcionario_id=responsavel_id,
                    valor_unitario=valor_unitario,
                    observacao=f"Vale em folha para {funcionario.nome}.",
                    escopo=escopo,
                    persistir=False,
                )

            lancamento = None if pendente else FinanceiroService.registrar_saida_adiantamento(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=funcionario.id,
                forma_pagamento_id=forma_pagamento.id,
                valor=valor_total,
                descricao=descricao,
                data_competencia=competencia,
                observacao=observacao_lancamento,
                persistir=False,
            )

            registro = AdiantamentoFuncionario(
                status="PENDENTE" if pendente else "AUTORIZADO",
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=funcionario.id,
                produto_id=produto.id if produto else None,
                forma_pagamento_id=forma_pagamento.id,
                lancamento_financeiro_id=lancamento.id if lancamento else None,
                movimento_estoque_id=movimento.id if movimento else None,
                tipo_adiantamento=tipo,
                descricao=descricao,
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                valor_total=valor_total,
                data_adiantamento=data_adiantamento,
                competencia=competencia,
                observacao=observacao,
            )
            AdiantamentoRepository.adicionar(registro)
            AdiantamentoRepository.flush()
            from app.services.financeiro_ciclo_service import audit
            audit("ADIANTAMENTO_SOLICITADO" if pendente else "ADIANTAMENTO_AUTORIZADO", registro, responsavel_id,
                {"valor": str(registro.valor_total), "status": registro.status})
            AdiantamentoRepository.salvar()

            if movimento and produto:
                EstoqueService.processar_alertas_por_produtos(
                    tenant_id=tenant_id,
                    empresa_id=empresa_id,
                    produto_ids=[produto.id],
                )

            return AdiantamentoRepository.buscar_por_id(
                registro.id,
                tenant_id=tenant_id,
                empresa_ids=empresa_ids,
            )
        except Exception:
            AdiantamentoRepository.rollback()
            raise

    @staticmethod
    def serializar(item):
        return {
            "status": item.status,
            "revisao": item.revisao,
            "id": item.id,
            "empresa_id": item.empresa_id,
            "empresa_nome": item.empresa.nome_fantasia if item.empresa else None,
            "funcionario_id": item.funcionario_id,
            "funcionario_nome": item.funcionario.nome if item.funcionario else None,
            "tipo_adiantamento": item.tipo_adiantamento.value,
            "descricao": item.descricao,
            "produto_id": item.produto_id,
            "produto_nome": item.produto.nome if item.produto else None,
            "quantidade": int(item.quantidade) if item.quantidade is not None else None,
            "valor_unitario": str(AdiantamentoService._to_decimal_value(item.valor_unitario)) if item.valor_unitario is not None else None,
            "valor_total": str(AdiantamentoService._to_decimal_value(item.valor_total)),
            "forma_pagamento_id": item.forma_pagamento_id,
            "forma_pagamento_nome": item.forma_pagamento.nome if item.forma_pagamento else None,
            "data_adiantamento": item.data_adiantamento.isoformat() if item.data_adiantamento else None,
            "competencia": item.competencia.isoformat() if item.competencia else None,
            "observacao": item.observacao,
            "lancamento_financeiro_id": item.lancamento_financeiro_id,
            "movimento_estoque_id": item.movimento_estoque_id,
        }

    @staticmethod
    def _garantir_base_operacional(tenant_id):
        try:
            TenantBootstrapService.garantir_cadastros_operacionais(tenant_id)
            AdiantamentoRepository.salvar()
        except Exception:
            AdiantamentoRepository.rollback()
            raise

    @staticmethod
    def _resolver_forma_pagamento(tenant_id, forma_pagamento_id=None):
        forma = None
        if forma_pagamento_id:
            forma = AdiantamentoRepository.buscar_forma_pagamento_por_id(forma_pagamento_id, tenant_id)
        if not forma:
            forma = AdiantamentoRepository.buscar_forma_pagamento_por_nome(AdiantamentoService.FORMA_PADRAO, tenant_id)
        if not forma or not forma.ativo:
            raise ValueError("Forma de pagamento padrao para vale nao encontrada.")
        return forma

    @staticmethod
    def _competencia_atual():
        hoje = TimeService.today_br()
        return date(hoje.year, hoje.month, 1)

    @staticmethod
    def _to_tipo_adiantamento(value):
        try:
            return TipoAdiantamentoFuncionario[(value or "").strip().upper()]
        except KeyError:
            raise ValueError("Tipo de adiantamento invalido.")

    @staticmethod
    def _to_int(value, field_name):
        from app.services.money_service import positive_integer
        return positive_integer(value, field_name)

    @staticmethod
    def _to_optional_int(value):
        from app.services.money_service import positive_integer
        return None if value in (None, "") else positive_integer(value, "Identificador")

    @staticmethod
    def _to_positive_int(value, field_name):
        from app.services.money_service import positive_integer
        return positive_integer(value, field_name)

    @staticmethod
    def _to_decimal(value, field_name):
        from app.services.money_service import money
        return money(value, field_name)

    @staticmethod
    def _to_optional_date(value):
        if value in (None, ""):
            return None

        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data invalida. Use o formato YYYY-MM-DD.")

    @staticmethod
    def _to_optional_competencia(value):
        if value in (None, ""):
            return None

        texto = str(value).strip()
        try:
            if len(texto) == 7:
                data_competencia = datetime.strptime(texto, "%Y-%m").date()
            else:
                data_competencia = datetime.strptime(texto, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Competencia invalida. Use YYYY-MM.")

        return date(data_competencia.year, data_competencia.month, 1)

    @staticmethod
    def _to_decimal_value(value):
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.01"))

        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")
