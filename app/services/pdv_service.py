from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from app.models.db import ItemVenda, ModalidadePrecoVenda, PagamentoVenda, StatusVenda, TipoDesconto, Venda
from app.repositorys.pdv_repository import PdvRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.cliente_service import ClienteService
from app.services.estoque_service import EstoqueService
from app.services.financeiro_service import FinanceiroService
from app.services.tenant_entitlement_service import TenantEntitlementService
from app.services.tenant_bootstrap_service import TenantBootstrapService
from app.services.time_service import TimeService
from app.services.idempotency_service import idempotent
from app.services.cupom_service import CupomService


from app.services.transaction_service import atomic_operation


class PdvService:

    @staticmethod
    def listar_auxiliares(tenant_id, escopo):
        PdvService._garantir_base_operacional(tenant_id)

        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        empresas = PdvRepository.listar_empresas(tenant_id, empresa_ids=empresa_ids)
        formas_pagamento = PdvRepository.listar_formas_pagamento(tenant_id)
        cupons = PdvRepository.listar_cupons_ativos(tenant_id, data_referencia=TimeService.today_br())
        clientes = ClienteService.listar_para_pdv(tenant_id)

        return {
            "empresas": [
                {
                    "id": empresa.id,
                    "nome": empresa.nome_fantasia,
                    "configuracao_cliente": ClienteService.serializar_configuracao_empresa(
                        ClienteService.obter_modelo_configuracao_empresa(empresa.id, tenant_id)
                    ),
                }
                for empresa in empresas
            ],
            "formas_pagamento": [
                {"id": forma.id, "nome": forma.nome}
                for forma in formas_pagamento
            ],
            "cupons": [CupomService.serializar(cupom) for cupom in cupons],
            "limite_desconto_percentual": PdvService.limite_desconto(escopo),
            "clientes": clientes,
        }

    @staticmethod
    def listar_produtos(tenant_id, escopo, empresa_id, busca=None):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        produtos = PdvRepository.listar_produtos_para_pdv(tenant_id, empresa_id)
        termo = (busca or "").strip().lower()

        if termo:
            produtos = [
                item for item in produtos
                if any(
                    termo in str(valor or "").lower()
                    for valor in (
                        item.produto.nome,
                        item.produto.descricao,
                        item.produto.codigo_barras,
                        item.produto.categoria.nome if item.produto.categoria else "",
                    )
                )
            ]

        return [PdvService.serializar_produto(item) for item in produtos]

    @staticmethod
    def buscar_produto_por_codigo_barras(tenant_id, escopo, empresa_id, codigo_barras):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        codigo_normalizado = "".join(char for char in str(codigo_barras or "").strip() if not char.isspace())
        if not codigo_normalizado:
            raise ValueError("Informe o codigo de barras para localizar o produto.")

        produto_empresa = PdvRepository.buscar_produto_empresa_por_codigo_barras(
            codigo_barras=codigo_normalizado,
            empresa_id=empresa_id,
            tenant_id=tenant_id,
        )
        if not produto_empresa:
            raise ValueError("Produto nao encontrado para o codigo de barras informado.")

        return PdvService.serializar_produto(produto_empresa)

    @staticmethod
    def listar_vendas(tenant_id, escopo, empresa_id=None, status=None, limite=30):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        status_enum = PdvService._to_optional_status(status)
        vendas = PdvRepository.listar_vendas(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            status=status_enum,
            limite=limite,
        )
        return [PdvService.serializar_venda(item) for item in vendas]

    @staticmethod
    def obter_venda(venda_id, tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        venda = PdvRepository.buscar_venda_por_id(venda_id, tenant_id, empresa_ids=empresa_ids)
        if not venda:
            raise ValueError("Venda nao encontrada.")
        return PdvService.serializar_venda(venda)

    @staticmethod
    @atomic_operation
    @idempotent
    def criar_venda(data, tenant_id, escopo, funcionario_id):
        try:
            PdvService._garantir_base_operacional(tenant_id)
            TenantEntitlementService.validar_limite_vendas_mes(tenant_id)

            empresa_id = PdvService._to_int(data.get("empresa_id"), "Empresa")
            cliente_id = PdvService._to_optional_int(data.get("cliente_id"), "Cliente")
            modalidade_preco = PdvService._to_modalidade_preco(data.get("modalidade_preco"))
            desconto_manual = PdvService._to_optional_decimal(data.get("desconto_manual"), "desconto manual")
            cashback_ativado = PdvService._to_bool(data.get("cashback_ativado", True), default=True)
            cashback_utilizado = PdvService._to_optional_decimal(data.get("cashback_utilizado"), "cashback utilizado") or Decimal("0.00")
            observacao = (data.get("observacao") or "").strip() or None
            cupom_codigo = (data.get("cupom_codigo") or "").strip().upper() or None
            itens_payload = data.get("itens") or []
            pagamentos_payload = data.get("pagamentos") or []

            if not itens_payload:
                raise ValueError("Adicione ao menos um item ao carrinho.")

            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

            tipo_operacao = PdvRepository.buscar_tipo_operacao_por_codigo("VENDA_PADRAO", tenant_id)
            if not tipo_operacao:
                raise ValueError("Tipo de operacao padrao de venda nao encontrado.")

            itens_compilados = []
            subtotal = Decimal("0.00")
            quantidades_produto = {}
            itens_normalizados = []
            for item_data in itens_payload:
                produto_id = PdvService._to_int(item_data.get("produto_id"), "Produto")
                quantidade = PdvService._to_positive_int(item_data.get("quantidade"), "quantidade")
                itens_normalizados.append((produto_id, quantidade))
                quantidades_produto[produto_id] = quantidades_produto.get(produto_id, 0) + quantidade

            for produto_id, quantidade in itens_normalizados:
                produto_empresa = PdvRepository.buscar_produto_empresa(produto_id, empresa_id, tenant_id)
                if not produto_empresa or not produto_empresa.ativo or not produto_empresa.produto.ativo:
                    raise ValueError("Um dos produtos informados nao esta disponivel para venda.")

                precificacao_item = PdvService._resolver_precificacao_item(
                    produto_empresa=produto_empresa,
                    quantidade=quantidades_produto[produto_id],
                    modalidade_solicitada=modalidade_preco,
                )
                valor_unitario = precificacao_item["valor_unitario"]

                valor_total = (valor_unitario * quantidade).quantize(Decimal("0.01"))
                subtotal += valor_total

                itens_compilados.append({
                    "produto_id": produto_empresa.produto_id,
                    "quantidade": quantidade,
                    "valor_unitario": valor_unitario,
                    "valor_total": valor_total,
                    "modalidade_preco_aplicada": precificacao_item["modalidade_aplicada"],
                })

            limite_desconto = PdvService.limite_desconto(escopo)
            if desconto_manual > (subtotal * Decimal(limite_desconto) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
                raise PermissionError(f"Desconto manual excede a autorizacao de {limite_desconto}%.")
            cupom = PdvService._validar_cupom(cupom_codigo, tenant_id)
            if cupom:
                CupomService.validar_uso(cupom, tenant_id, empresa_id, cliente_id, subtotal)
            desconto_cupom = PdvService._calcular_desconto_cupom(cupom, subtotal)
            desconto_total = (desconto_manual + desconto_cupom).quantize(Decimal("0.01"))

            if desconto_total > subtotal:
                raise ValueError("O desconto total nao pode ser maior que o subtotal.")

            total_sem_cashback = (subtotal - desconto_total).quantize(Decimal("0.01"))
            if not cashback_ativado:
                cashback_utilizado = Decimal("0.00")
            if cashback_utilizado > Decimal("0.00") and not cliente_id:
                raise ValueError("Informe o cliente para utilizar cashback.")
            if cashback_utilizado > total_sem_cashback:
                raise ValueError("O cashback utilizado nao pode ser maior que o total liquido da venda.")

            if cliente_id and cashback_ativado and cashback_utilizado > Decimal("0.00"):
                ClienteService.preparar_uso_cashback(
                    cliente_id=cliente_id,
                    empresa_id=empresa_id,
                    valor_solicitado=cashback_utilizado,
                    tenant_id=tenant_id,
                    valor_base_venda=total_sem_cashback,
                )

            total = (total_sem_cashback - cashback_utilizado).quantize(Decimal("0.01"))

            pagamentos_compilados = PdvService._validar_pagamentos(
                pagamentos_payload=pagamentos_payload,
                tenant_id=tenant_id,
                total_esperado=total,
            )

            venda = Venda(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=funcionario_id,
                tipo_operacao_id=tipo_operacao.id,
                cupom_id=cupom.id if cupom else None,
                numero_unico=PdvService._gerar_numero_unico(empresa_id),
                status=StatusVenda.FINALIZADA,
                modalidade_preco=modalidade_preco,
                subtotal=subtotal,
                desconto=desconto_total,
                cashback_ativado=cashback_ativado,
                cashback_utilizado=cashback_utilizado,
                cashback_gerado=Decimal("0.00"),
                total=total,
                data_venda=TimeService.now_utc_naive(),
                observacao=observacao,
            )
            PdvRepository.adicionar(venda)
            PdvRepository.flush()

            itens_registrados = []
            for item in itens_compilados:
                item_obj = ItemVenda(
                    tenant_id=tenant_id,
                    venda_id=venda.id,
                    produto_id=item["produto_id"],
                    modalidade_preco_aplicada=item["modalidade_preco_aplicada"],
                    quantidade=item["quantidade"],
                    valor_unitario=item["valor_unitario"],
                    valor_total=item["valor_total"],
                )
                PdvRepository.adicionar(item_obj)
                itens_registrados.append(item_obj)

            pagamentos_registrados = []
            for pagamento in pagamentos_compilados:
                pagamento_obj = PagamentoVenda(
                    tenant_id=tenant_id,
                    venda_id=venda.id,
                    forma_pagamento_id=pagamento["forma_pagamento"].id,
                    valor=pagamento["valor"],
                    comprovante=pagamento["comprovante"],
                )
                pagamento_obj.forma_pagamento = pagamento["forma_pagamento"]
                PdvRepository.adicionar(pagamento_obj)
                pagamentos_registrados.append(pagamento_obj)

            PdvRepository.flush()

            EstoqueService.registrar_saida_por_venda(
                venda_id=venda.id,
                empresa_id=empresa_id,
                itens=[
                    {
                        "item_venda_id": item_obj.id,
                        "produto_id": item["produto_id"],
                        "quantidade": item["quantidade"],
                        "valor_unitario": item["valor_unitario"],
                    }
                    for item, item_obj in zip(itens_compilados, itens_registrados)
                ],
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                escopo=escopo,
                persistir=False,
            )
            FinanceiroService.registrar_entradas_da_venda(
                venda=venda,
                pagamentos=pagamentos_registrados,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                persistir=False,
            )
            ClienteService.processar_cashback_da_venda(
                venda=venda,
                cliente_id=cliente_id,
                empresa_id=empresa_id,
                valor_cashback_utilizado=cashback_utilizado,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                cashback_ativado=cashback_ativado,
            )

            PdvRepository.salvar()
            EstoqueService.processar_alertas_por_produtos(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                produto_ids=[item["produto_id"] for item in itens_compilados],
            )

            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            venda = PdvRepository.buscar_venda_por_id(venda.id, tenant_id, empresa_ids=empresa_ids)
            dados_venda = PdvService.serializar_venda(venda)
            dados_venda["email_venda"] = ClienteService.enviar_email_venda_automatica(
                venda=venda, tenant_id=tenant_id, funcionario_id=funcionario_id,
            )
            return dados_venda
        except Exception:
            PdvRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    @idempotent
    def cancelar_venda(venda_id, data, tenant_id, escopo, funcionario_id):
        try:
            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            venda = PdvRepository.buscar_venda_por_id(venda_id, tenant_id, empresa_ids=empresa_ids)
            if not venda:
                raise ValueError("Venda nao encontrada.")

            if venda.status == StatusVenda.CANCELADA:
                return PdvService.serializar_venda(venda)
            if venda.status != StatusVenda.FINALIZADA:
                raise ValueError("Somente vendas finalizadas podem ser canceladas.")

            configuracao = ClienteService.obter_modelo_configuracao_empresa(venda.empresa_id, tenant_id)
            PdvService._validar_janela_cancelamento(
                data_base=venda.data_venda,
                limite_horas=configuracao.cancelamento_venda_limite_horas,
                mensagem="A janela de cancelamento da venda expirou para esta empresa.",
            )

            if any(int(item.quantidade_cancelada or 0) > 0 for item in venda.itens):
                for item in sorted(venda.itens, key=lambda record: record.id):
                    restante = int(item.quantidade) - int(item.quantidade_cancelada or 0)
                    if restante:
                        PdvService.cancelar_item_venda(venda.id, item.id,
                            {"quantidade": restante, "motivo": data.get("motivo")}, tenant_id, escopo, funcionario_id)
                return PdvService.serializar_venda(venda)

            motivo = (data.get("motivo") or "").strip() or "Cancelamento manual realizado pelo operador."
            venda.cancelado_em = TimeService.now_utc_naive()
            venda.cancelado_por_funcionario_id = funcionario_id
            venda.valor_cancelado = (
                PdvService._to_decimal_value(venda.total) + PdvService._to_decimal_value(getattr(venda, "cashback_utilizado", 0))
            ).quantize(Decimal("0.01"))
            venda.status = StatusVenda.CANCELADA
            venda.observacao = PdvService._mesclar_observacao(venda.observacao, motivo)

            EstoqueService.registrar_entrada_por_cancelamento_venda(
                venda_id=venda.id,
                empresa_id=venda.empresa_id,
                itens=[
                    {
                        "item_venda_id": item.id,
                        "produto_id": item.produto_id,
                        "quantidade": item.quantidade,
                        "valor_unitario": item.valor_unitario,
                    }
                    for item in venda.itens
                ],
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                escopo=escopo,
                persistir=False,
            )
            FinanceiroService.registrar_estorno_da_venda(
                venda=venda,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                persistir=False,
            )
            ClienteService.reverter_cashback_venda(venda, tenant_id, funcionario_id)

            PdvRepository.salvar()
            EstoqueService.processar_alertas_por_produtos(
                tenant_id=tenant_id,
                empresa_id=venda.empresa_id,
                produto_ids=[item.produto_id for item in venda.itens],
            )

            venda = PdvRepository.buscar_venda_por_id(venda.id, tenant_id, empresa_ids=empresa_ids)
            return PdvService.serializar_venda(venda)
        except Exception:
            PdvRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    @idempotent
    def cancelar_item_venda(venda_id, item_id, data, tenant_id, escopo, funcionario_id):
        try:
            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            item = PdvRepository.buscar_item_venda(venda_id, item_id, tenant_id)
            if not item or not item.venda or (empresa_ids is not None and item.venda.empresa_id not in empresa_ids):
                raise ValueError("Item da venda nao encontrado.")

            venda = item.venda
            if venda.status != StatusVenda.FINALIZADA:
                raise ValueError("Somente vendas finalizadas podem ter itens cancelados.")

            configuracao = ClienteService.obter_modelo_configuracao_empresa(venda.empresa_id, tenant_id)
            PdvService._validar_janela_cancelamento(
                data_base=venda.data_venda,
                limite_horas=configuracao.cancelamento_item_limite_horas,
                mensagem="A janela de cancelamento de itens expirou para esta empresa.",
            )

            quantidade_informada = data.get("quantidade")
            if quantidade_informada in (None, ""):
                quantidade_informada = 1
            quantidade_cancelar = PdvService._to_positive_int(quantidade_informada, "quantidade")
            quantidade_cancelada_atual = int(getattr(item, "quantidade_cancelada", 0) or 0)
            quantidade_disponivel = int(item.quantidade) - quantidade_cancelada_atual
            if quantidade_disponivel <= 0:
                raise ValueError("Este item ja foi cancelado integralmente.")
            if quantidade_cancelar > quantidade_disponivel:
                raise ValueError("A quantidade informada ultrapassa o saldo disponivel para cancelamento do item.")

            motivo = (data.get("motivo") or "").strip() or "Cancelamento parcial do item solicitado pelo operador."
            valor_bruto_cancelado = (
                PdvService._to_decimal_value(item.valor_unitario) * quantidade_cancelar
            ).quantize(Decimal("0.01"))
            base_pos_desconto = (
                PdvService._to_decimal_value(venda.total) + PdvService._to_decimal_value(getattr(venda, "cashback_utilizado", 0))
            ).quantize(Decimal("0.01"))
            bruto_acumulado = valor_bruto_cancelado + sum(
                (PdvService._to_decimal_value(record.valor_unitario) * int(record.quantidade_cancelada or 0)
                 for record in venda.itens), Decimal("0.00")
            )
            cancelado_anterior = PdvService._to_decimal_value(venda.valor_cancelado)
            cancelado_alvo = Decimal("0.00")
            if venda.subtotal > 0:
                cancelado_alvo = (base_pos_desconto * bruto_acumulado / venda.subtotal).quantize(Decimal("0.01"))
            valor_cancelamento_liquido = cancelado_alvo - cancelado_anterior
            cashback_restaurar = Decimal("0.00")
            if base_pos_desconto > Decimal("0.00") and PdvService._to_decimal_value(getattr(venda, "cashback_utilizado", 0)) > Decimal("0.00"):
                cashback_restaurar = (cancelado_alvo * venda.cashback_utilizado / base_pos_desconto).quantize(Decimal("0.01")) - (
                    cancelado_anterior * venda.cashback_utilizado / base_pos_desconto
                ).quantize(Decimal("0.01"))

            valor_estorno_financeiro = (valor_cancelamento_liquido - cashback_restaurar).quantize(Decimal("0.01"))

            item.quantidade_cancelada = quantidade_cancelada_atual + quantidade_cancelar
            item.valor_cancelado = (
                PdvService._to_decimal_value(getattr(item, "valor_cancelado", 0)) + valor_cancelamento_liquido
            ).quantize(Decimal("0.01"))
            item.cancelado_em = TimeService.now_utc_naive()
            item.cancelado_por_funcionario_id = funcionario_id
            item.motivo_cancelamento = PdvService._mesclar_observacao(item.motivo_cancelamento, motivo)

            venda.valor_cancelado = (
                PdvService._to_decimal_value(getattr(venda, "valor_cancelado", 0)) + valor_cancelamento_liquido
            ).quantize(Decimal("0.01"))
            venda.observacao = PdvService._mesclar_observacao(venda.observacao, f"Item cancelado: {motivo}")

            EstoqueService.registrar_entrada_por_cancelamento_item_venda(
                venda_id=venda.id,
                empresa_id=venda.empresa_id,
                item_venda=item,
                quantidade=quantidade_cancelar,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                escopo=escopo,
                persistir=False,
            )
            FinanceiroService.registrar_estorno_parcial_da_venda(
                venda=venda,
                item_venda=item,
                valor_estorno=valor_estorno_financeiro,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                persistir=False,
            )
            ClienteService.restaurar_cashback_parcial_da_venda(
                venda=venda,
                valor_restaurar=cashback_restaurar,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
            )
            ClienteService.ajustar_cashback_gerado_por_cancelamento_item(
                venda=venda,
                valor_cancelamento_liquido=valor_cancelamento_liquido,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
            )

            if all(int(item_venda.quantidade_cancelada or 0) >= int(item_venda.quantidade) for item_venda in venda.itens):
                venda.status = StatusVenda.CANCELADA
                venda.cancelado_em = TimeService.now_utc_naive()
                venda.cancelado_por_funcionario_id = funcionario_id

            PdvRepository.salvar()
            EstoqueService.processar_alertas_por_produtos(
                tenant_id=tenant_id,
                empresa_id=venda.empresa_id,
                produto_ids=[item.produto_id],
            )
            venda = PdvRepository.buscar_venda_por_id(venda.id, tenant_id, empresa_ids=empresa_ids)
            return PdvService.serializar_venda(venda)
        except Exception:
            PdvRepository.rollback()
            raise

    @staticmethod
    def serializar_produto(item):
        return {
            "id": item.produto.id,
            "produto_empresa_id": item.id,
            "empresa_id": item.empresa_id,
            "empresa_nome": item.empresa.nome_fantasia if item.empresa else None,
            "categoria_nome": item.produto.categoria.nome if item.produto.categoria else None,
            "nome": item.produto.nome,
            "descricao": item.produto.descricao,
            "codigo_barras": item.produto.codigo_barras,
            "estoque_atual": int(item.estoque_atual),
            "estoque_minimo": int(item.estoque_minimo),
            "valor_venda": str(PdvService._obter_valor_varejo_produto(item)),
            "valor_varejo": str(PdvService._obter_valor_varejo_produto(item)),
            "valor_atacado": str(PdvService._obter_valor_atacado_produto(item)),
            "quantidade_minima_atacado": int(getattr(item, "quantidade_minima_atacado", 1) or 1),
            "valor_compra": str(PdvService._to_decimal_value(item.valor_compra)),
            "ativo": item.ativo,
        }

    @staticmethod
    def serializar_venda(venda):
        configuracao = ClienteService.obter_modelo_configuracao_empresa(venda.empresa_id, venda.tenant_id)
        permite_cancelamento = (
            venda.status == StatusVenda.FINALIZADA
            and PdvService._esta_dentro_janela_cancelamento(venda.data_venda, configuracao.cancelamento_venda_limite_horas)
        )
        permite_cancelar_itens = (
            venda.status == StatusVenda.FINALIZADA
            and PdvService._esta_dentro_janela_cancelamento(venda.data_venda, configuracao.cancelamento_item_limite_horas)
            and any(int(item.quantidade) > int(getattr(item, "quantidade_cancelada", 0) or 0) for item in venda.itens)
        )

        return {
            "id": venda.id,
            "empresa_id": venda.empresa_id,
            "empresa_nome": venda.empresa.nome_fantasia if venda.empresa else None,
            "funcionario_nome": venda.funcionario.nome if venda.funcionario else None,
            "cliente_id": venda.cliente_id,
            "cliente_nome": venda.cliente.nome if venda.cliente else None,
            "cliente_documento": venda.cliente.documento if venda.cliente else None,
            "numero_unico": venda.numero_unico,
            "status": venda.status.value,
            "modalidade_preco": getattr(venda.modalidade_preco, "value", ModalidadePrecoVenda.VAREJO.value),
            "subtotal": str(PdvService._to_decimal_value(venda.subtotal)),
            "desconto": str(PdvService._to_decimal_value(venda.desconto)),
            "cashback_ativado": bool(getattr(venda, "cashback_ativado", True)),
            "cashback_utilizado": str(PdvService._to_decimal_value(getattr(venda, "cashback_utilizado", 0))),
            "cashback_gerado": str(PdvService._to_decimal_value(getattr(venda, "cashback_gerado", 0))),
            "cashback_percentual_aplicado": str(PdvService._to_decimal_value(getattr(venda, "cashback_percentual_aplicado", 0))),
            "valor_cancelado": str(PdvService._to_decimal_value(getattr(venda, "valor_cancelado", 0))),
            "total": str(PdvService._to_decimal_value(venda.total)),
            "data_venda": TimeService.serialize_utc_iso(venda.data_venda),
            "cancelado_em": TimeService.serialize_utc_iso(getattr(venda, "cancelado_em", None)),
            "observacao": venda.observacao,
            "cupom_codigo": venda.cupom.codigo if venda.cupom else None,
            "itens_quantidade": sum(int(item.quantidade) for item in venda.itens),
            "itens": [
                {
                    "id": item.id,
                    "produto_id": item.produto_id,
                    "produto_nome": item.produto.nome if item.produto else None,
                    "quantidade": int(item.quantidade),
                    "quantidade_cancelada": int(getattr(item, "quantidade_cancelada", 0) or 0),
                    "quantidade_disponivel_cancelamento": int(item.quantidade) - int(getattr(item, "quantidade_cancelada", 0) or 0),
                    "modalidade_preco_aplicada": getattr(
                        item.modalidade_preco_aplicada,
                        "value",
                        ModalidadePrecoVenda.VAREJO.value,
                    ),
                    "valor_unitario": str(PdvService._to_decimal_value(item.valor_unitario)),
                    "valor_total": str(PdvService._to_decimal_value(item.valor_total)),
                    "valor_cancelado": str(PdvService._to_decimal_value(getattr(item, "valor_cancelado", 0))),
                    "motivo_cancelamento": getattr(item, "motivo_cancelamento", None),
                    "cancelado_em": TimeService.serialize_utc_iso(getattr(item, "cancelado_em", None)),
                    "permite_cancelamento": (
                        venda.status == StatusVenda.FINALIZADA
                        and PdvService._esta_dentro_janela_cancelamento(venda.data_venda, configuracao.cancelamento_item_limite_horas)
                        and int(item.quantidade) > int(getattr(item, "quantidade_cancelada", 0) or 0)
                    ),
                }
                for item in venda.itens
            ],
            "pagamentos": [
                {
                    "id": pagamento.id,
                    "forma_pagamento_id": pagamento.forma_pagamento_id,
                    "forma_pagamento_nome": pagamento.forma_pagamento.nome if pagamento.forma_pagamento else None,
                    "valor": str(PdvService._to_decimal_value(pagamento.valor)),
                    "comprovante": pagamento.comprovante,
                }
                for pagamento in venda.pagamentos
            ],
            "permite_cancelamento": permite_cancelamento,
            "permite_cancelar_itens": permite_cancelar_itens,
        }

    @staticmethod
    def _garantir_base_operacional(tenant_id):
        try:
            TenantBootstrapService.garantir_cadastros_operacionais(tenant_id)
            PdvRepository.salvar()
        except Exception:
            PdvRepository.rollback()
            raise

    @staticmethod
    def _validar_cupom(codigo, tenant_id):
        if not codigo:
            return None

        cupom = PdvRepository.buscar_cupom_por_codigo(codigo, tenant_id)
        if not cupom or not cupom.ativo:
            raise ValueError("Cupom nao encontrado.")

        if cupom.data_validade < TimeService.today_br():
            raise ValueError("Cupom expirado.")

        return cupom

    @staticmethod
    def _calcular_desconto_cupom(cupom, subtotal):
        if not cupom:
            return Decimal("0.00")

        valor_desconto = PdvService._to_decimal_value(cupom.valor_desconto)
        if cupom.tipo_desconto == TipoDesconto.PERCENTUAL:
            valor_desconto = ((subtotal * valor_desconto) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return min(valor_desconto, subtotal, cupom.desconto_maximo if cupom.desconto_maximo is not None else subtotal)

    @staticmethod
    def limite_desconto(escopo):
        if AcessoEmpresaService.possui_permissao(escopo, "autorizar_desconto"):
            return 100
        return 10 if AcessoEmpresaService.possui_permissao(escopo, "aplicar_desconto") else 0

    @staticmethod
    def _validar_pagamentos(pagamentos_payload, tenant_id, total_esperado):
        if PdvService._to_decimal_value(total_esperado) <= Decimal("0.00"):
            if pagamentos_payload:
                raise ValueError("Venda com total zero nao deve receber pagamentos.")
            return []

        if not pagamentos_payload:
            raise ValueError("Informe ao menos uma forma de pagamento.")

        formas_ids = [
            PdvService._to_int(item.get("forma_pagamento_id"), "Forma de pagamento")
            for item in pagamentos_payload
        ]
        formas = {
            forma.id: forma
            for forma in PdvRepository.buscar_formas_pagamento_por_ids(formas_ids, tenant_id)
        }

        if len(formas) != len(set(formas_ids)):
            raise ValueError("Uma ou mais formas de pagamento nao foram encontradas.")

        pagamentos_compilados = []
        total_pagamentos = Decimal("0.00")

        for pagamento in pagamentos_payload:
            forma_pagamento_id = PdvService._to_int(pagamento.get("forma_pagamento_id"), "Forma de pagamento")
            valor = PdvService._to_decimal(pagamento.get("valor"), "valor do pagamento")
            if valor <= 0:
                raise ValueError("Pagamento deve representar pelo menos um centavo.")
            comprovante = (pagamento.get("comprovante") or "").strip() or None

            pagamentos_compilados.append({
                "forma_pagamento": formas[forma_pagamento_id],
                "valor": valor,
                "comprovante": comprovante,
            })
            total_pagamentos += valor

        if total_pagamentos.quantize(Decimal("0.01")) != total_esperado.quantize(Decimal("0.01")):
            raise ValueError("A soma dos pagamentos deve ser igual ao total da venda.")

        return pagamentos_compilados

    @staticmethod
    def _mesclar_observacao(observacao_atual, observacao_nova):
        if observacao_atual and observacao_nova:
            return f"{observacao_atual}\n{observacao_nova}"
        return observacao_nova or observacao_atual

    @staticmethod
    def _gerar_numero_unico(empresa_id):
        timestamp = TimeService.now_utc_naive().strftime("%Y%m%d%H%M%S")
        return f"VEN-{empresa_id}-{timestamp}-{uuid4().hex[:6].upper()}"

    @staticmethod
    def _resolver_precificacao_item(produto_empresa, quantidade, modalidade_solicitada):
        valor_varejo = PdvService._obter_valor_varejo_produto(produto_empresa)
        valor_atacado = PdvService._obter_valor_atacado_produto(produto_empresa)
        quantidade_minima_atacado = int(getattr(produto_empresa, "quantidade_minima_atacado", 1) or 1)
        possui_regra_atacado = (
            valor_atacado > Decimal("0.00")
            and valor_atacado < valor_varejo
            and quantidade_minima_atacado >= 1
        )

        if modalidade_solicitada == ModalidadePrecoVenda.ATACADO:
            if not possui_regra_atacado:
                raise ValueError(
                    f"O produto '{produto_empresa.produto.nome}' nao possui preco de atacado configurado."
                )
            if int(quantidade) < quantidade_minima_atacado:
                raise ValueError(
                    "A quantidade informada nao atinge o minimo para venda em atacado "
                    f"do produto '{produto_empresa.produto.nome}' ({quantidade_minima_atacado})."
                )
            return {
                "valor_unitario": valor_atacado,
                "modalidade_aplicada": ModalidadePrecoVenda.ATACADO,
            }

        if modalidade_solicitada == ModalidadePrecoVenda.AUTOMATICO:
            if possui_regra_atacado and int(quantidade) >= quantidade_minima_atacado:
                return {
                    "valor_unitario": valor_atacado,
                    "modalidade_aplicada": ModalidadePrecoVenda.ATACADO,
                }

        return {
            "valor_unitario": valor_varejo,
            "modalidade_aplicada": ModalidadePrecoVenda.VAREJO,
        }

    @staticmethod
    def _obter_valor_varejo_produto(produto_empresa):
        valor_varejo = getattr(produto_empresa, "valor_varejo", None)
        valor_venda_legado = getattr(produto_empresa, "valor_venda", 0)
        valor_varejo_decimal = PdvService._to_decimal_value(valor_varejo)
        if valor_varejo is None or (
            valor_varejo_decimal <= Decimal("0.00")
            and PdvService._to_decimal_value(valor_venda_legado) > Decimal("0.00")
        ):
            return PdvService._to_decimal_value(valor_venda_legado)
        return valor_varejo_decimal

    @staticmethod
    def _obter_valor_atacado_produto(produto_empresa):
        valor_atacado = getattr(produto_empresa, "valor_atacado", None)
        if valor_atacado is None:
            valor_atacado = getattr(produto_empresa, "valor_venda", 0)
        return PdvService._to_decimal_value(valor_atacado)

    @staticmethod
    def _to_optional_status(value):
        if value in (None, ""):
            return None

        try:
            return StatusVenda[(value or "").strip().upper()]
        except KeyError:
            raise ValueError("Status de venda invalido.")

    @staticmethod
    def _to_modalidade_preco(value):
        raw_value = (value or "").strip().upper()
        if not raw_value:
            return ModalidadePrecoVenda.VAREJO

        try:
            return ModalidadePrecoVenda[raw_value]
        except KeyError:
            raise ValueError("Modalidade de preco invalida.")

    @staticmethod
    def _to_int(value, field_name):
        if value in (None, ""):
            raise ValueError(f"{field_name} e obrigatorio.")
        return PdvService._to_positive_int(value, field_name)

    @staticmethod
    def _to_positive_int(value, field_name):
        if value in (None, ""):
            raise ValueError(f"Informe {field_name}.")

        try:
            valor = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if valor <= 0:
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")

        return valor

    @staticmethod
    def _to_decimal(value, field_name):
        if value in (None, ""):
            raise ValueError(f"Informe {field_name}.")

        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if not valor.is_finite() or valor <= 0 or valor >= Decimal("10000000000"):
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")

        return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _to_optional_decimal(value, field_name):
        if value in (None, ""):
            return Decimal("0.00") if field_name == "desconto manual" else None

        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if not valor.is_finite() or valor < 0 or valor >= Decimal("10000000000"):
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")

        return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _to_decimal_value(value):
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.01"))

        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _to_optional_int(value, field_name):
        if value in (None, ""):
            return None
        return PdvService._to_positive_int(value, field_name)

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "t", "sim", "yes", "on"}

    @staticmethod
    def _esta_dentro_janela_cancelamento(data_base, limite_horas):
        try:
            limite = int(limite_horas or 0)
        except (TypeError, ValueError):
            limite = 0
        if limite <= 0:
            return True
        agora = TimeService.now_utc_naive()
        return agora <= (data_base + PdvService._timedelta_hours(limite))

    @staticmethod
    def _validar_janela_cancelamento(data_base, limite_horas, mensagem):
        if not PdvService._esta_dentro_janela_cancelamento(data_base, limite_horas):
            raise ValueError(mensagem)

    @staticmethod
    def _timedelta_hours(hours):
        from datetime import timedelta
        return timedelta(hours=max(int(hours or 0), 0))
