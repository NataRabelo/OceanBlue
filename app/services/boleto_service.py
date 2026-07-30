from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models.db import (
    BaseCalculoJurosMulta,
    Boleto,
    ArquivoBoleto,
    CategoriaFinanceira,
    ConfiguracaoAsaasEmpresa,
    ConfiguracaoParcelamento,
    EventoBoleto,
    FormaPagamento,
    LancamentoFinanceiro,
    ParcelaBoleto,
    RegraJurosMulta,
    RetornoBancarioBoleto,
    StatusBancarioBoleto,
    StatusBoleto,
    TipoEventoBoleto,
    TipoFinanceiro,
    TipoJurosBoleto,
    TipoMultaBoleto,
)
from app.security.field_crypto import FieldCrypto
from app.services.boleto_provider import get_boleto_provider
from app.repositorys.boleto_repository import BoletoRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.time_service import TimeService
from app.services.tenant_bootstrap_service import TenantBootstrapService


class BoletoService:
    @staticmethod
    def obter_configuracao_asaas(tenant_id, escopo, empresa_id):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        config = ConfiguracaoAsaasEmpresa.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id).first()
        if not config:
            return {
                "empresa_id": empresa_id,
                "ambiente": "sandbox",
                "api_key_configurada": False,
                "webhook_auth_token_configurado": False,
                "status_configuracao": "PENDENTE",
                "ativo": False,
                "pendencias": ["Token Asaas nao configurado."],
            }
        return BoletoService._serializar_configuracao_asaas(config)

    @staticmethod
    def atualizar_configuracao_asaas(tenant_id, escopo, empresa_id, data):
        try:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
            config = ConfiguracaoAsaasEmpresa.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id).first()
            if not config:
                config = ConfiguracaoAsaasEmpresa(tenant_id=tenant_id, empresa_id=empresa_id)
                BoletoRepository.adicionar(config)
            ambiente = (data.get("ambiente") or "sandbox").strip().lower()
            if ambiente not in {"sandbox", "producao"}:
                raise ValueError("Ambiente Asaas invalido.")
            config.ambiente = ambiente
            if "api_key" in data and data.get("api_key"):
                config.api_key = FieldCrypto.encrypt(data.get("api_key"))
            config.wallet_id = (data.get("wallet_id") or "").strip() or None
            config.webhook_url = (data.get("webhook_url") or "").strip() or None
            if "webhook_auth_token" in data and data.get("webhook_auth_token"):
                config.webhook_auth_token = FieldCrypto.encrypt(data.get("webhook_auth_token"))
            config.webhook_ativo = BoletoService._to_bool(data.get("webhook_ativo"), default=False)
            dias = data.get("dias_apos_vencimento_cancelamento")
            config.dias_apos_vencimento_cancelamento = int(dias) if dias not in (None, "") else None
            config.notificacoes_desabilitadas = BoletoService._to_bool(data.get("notificacoes_desabilitadas"), default=True)
            config.ativo = BoletoService._to_bool(data.get("ativo"), default=True)
            config.status_configuracao = "CONFIGURADO" if config.api_key else "PENDENTE"
            BoletoRepository.salvar()
            return BoletoService._serializar_configuracao_asaas(config)
        except Exception:
            BoletoRepository.rollback()
            raise

    @staticmethod
    def _serializar_configuracao_asaas(config):
        pendencias = []
        if not config.api_key:
            pendencias.append("Token Asaas nao configurado.")
        if config.webhook_ativo and not config.webhook_auth_token:
            pendencias.append("Token de autenticacao do webhook Asaas nao configurado.")
        return {
            "empresa_id": config.empresa_id,
            "ambiente": config.ambiente,
            "provider_codigo": config.provider_codigo,
            "api_key_configurada": bool(config.api_key),
            "wallet_id": config.wallet_id,
            "status_configuracao": config.status_configuracao,
            "ultima_validacao_em": TimeService.serialize_utc_iso(config.ultima_validacao_em),
            "ultima_validacao_status": config.ultima_validacao_status,
            "ultima_validacao_mensagem": config.ultima_validacao_mensagem,
            "webhook_url": config.webhook_url,
            "webhook_auth_token_configurado": bool(config.webhook_auth_token),
            "webhook_ativo": bool(config.webhook_ativo),
            "dias_apos_vencimento_cancelamento": config.dias_apos_vencimento_cancelamento,
            "notificacoes_desabilitadas": bool(config.notificacoes_desabilitadas),
            "ativo": bool(config.ativo),
            "apto_producao": config.ambiente == "producao" and not pendencias,
            "pendencias": pendencias,
        }

    @staticmethod
    def listar_bancos_emissores(tenant_id, escopo, empresa_id=None, ativo=None):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        bancos = BoletoRepository.listar_bancos_emissores(tenant_id, empresa_ids=empresa_ids, empresa_id=empresa_id, ativo=ativo)
        return [{
            "id": item.id,
            "empresa_id": item.empresa_id,
            "banco_codigo": item.banco_codigo,
            "banco_nome": item.banco_nome,
            "carteira": item.carteira,
            "agencia": item.agencia,
            "conta": item.conta,
            "codigo_cedente": item.codigo_cedente,
            "layout_arquivo": item.layout_arquivo.value if item.layout_arquivo else None,
            "ambiente": item.ambiente.value if item.ambiente else None,
            "is_padrao": bool(item.is_padrao),
            "ativo": bool(item.ativo),
        } for item in bancos]

    @staticmethod
    def listar_configuracoes_parcelamento(tenant_id, escopo, empresa_id=None, ativo=None):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        configs = BoletoRepository.listar_configuracoes_parcelamento(tenant_id, empresa_ids=empresa_ids, empresa_id=empresa_id, ativo=ativo)
        return [{
            "id": item.id,
            "empresa_id": item.empresa_id,
            "banco_emissor_id": item.banco_emissor_id,
            "numero_min_parcelas": item.numero_min_parcelas,
            "numero_max_parcelas": item.numero_max_parcelas,
            "intervalo_dias_padrao": item.intervalo_dias_padrao,
            "permite_intervalo_customizado": bool(item.permite_intervalo_customizado),
            "dia_fixo_vencimento": item.dia_fixo_vencimento,
            "valor_minimo_por_parcela": str(item.valor_minimo_por_parcela),
            "regra_distribuicao": item.regra_distribuicao.value if item.regra_distribuicao else None,
            "arredondamento_ultima_parcela": bool(item.arredondamento_ultima_parcela),
            "ativo": bool(item.ativo),
        } for item in configs]

    @staticmethod
    def listar_regras_juros_multa(tenant_id, escopo, empresa_id=None):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        regras = BoletoRepository.listar_regras_juros_multa(tenant_id, empresa_ids=empresa_ids, empresa_id=empresa_id)
        return [{
            "id": item.id,
            "empresa_id": item.empresa_id,
            "banco_emissor_id": item.banco_emissor_id,
            "tipo_multa": item.tipo_multa.value if item.tipo_multa else None,
            "percentual_multa": str(item.percentual_multa) if item.percentual_multa is not None else None,
            "valor_fixo_multa": str(item.valor_fixo_multa) if item.valor_fixo_multa is not None else None,
            "tipo_juros": item.tipo_juros.value if item.tipo_juros else None,
            "percentual_juros": str(item.percentual_juros) if item.percentual_juros is not None else None,
            "dias_carencia": item.dias_carencia,
            "base_calculo": item.base_calculo.value if item.base_calculo else None,
            "percentual_maximo_teto": str(item.percentual_maximo_teto),
            "vigente_desde": item.vigente_desde.isoformat() if item.vigente_desde else None,
            "vigente_ate": item.vigente_ate.isoformat() if item.vigente_ate else None,
            "ativo": bool(item.ativo),
        } for item in regras]

    @staticmethod
    def listar_boletos(tenant_id, escopo, empresa_id=None, status=None, banco_emissor_id=None, limite=100):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        boletos = BoletoRepository.listar_boletos(
            tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            status=status,
            banco_emissor_id=banco_emissor_id,
            limite=limite,
        )
        return [BoletoService.serializar_boleto(item) for item in boletos]

    @staticmethod
    def buscar_boleto(tenant_id, escopo, boleto_id, empresa_id=None):
        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        boleto = BoletoRepository.buscar_boleto(boleto_id, tenant_id, empresa_id=empresa_id)
        if not boleto:
            raise LookupError("Boleto nao encontrado.")
        return BoletoService.serializar_boleto(boleto)

    @staticmethod
    def criar_boleto(data, tenant_id, escopo, funcionario_id):
        try:
            empresa_id = BoletoService._to_int(data.get("empresa_id"), "empresa_id")
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

            cliente_id = BoletoService._to_int(data.get("cliente_id"), "cliente_id")
            banco_emissor_id = BoletoService._to_int(data.get("banco_emissor_id"), "banco_emissor_id")
            forma_pagamento_id = BoletoService._to_int(data.get("forma_pagamento_id"), "forma_pagamento_id")
            categoria_id = BoletoService._to_int(data.get("categoria_id"), "categoria_id")
            valor_nominal = BoletoService._to_decimal(data.get("valor_nominal"), "valor_nominal")
            data_vencimento = BoletoService._to_optional_date(data.get("data_vencimento"))
            if data_vencimento is None:
                raise ValueError("data_vencimento e obrigatoria.")
            numero_boleto = (data.get("numero_boleto") or "").strip() or BoletoService._gerar_numero_boleto(tenant_id)
            if BoletoRepository.existe_numero_boleto(tenant_id, numero_boleto):
                raise ValueError("Ja existe um boleto com esse numero.")

            banco_emissor = BoletoRepository.buscar_banco_emissor(banco_emissor_id, tenant_id, empresa_id=empresa_id)
            if not banco_emissor or not banco_emissor.ativo:
                raise ValueError("Banco emissor nao encontrado ou inativo.")
            forma_pagamento = db.session.get(FormaPagamento, forma_pagamento_id)
            if not forma_pagamento or not forma_pagamento.ativo:
                raise ValueError("Forma de pagamento invalida.")
            categoria = db.session.get(CategoriaFinanceira, categoria_id)
            if not categoria or not categoria.ativo:
                raise ValueError("Categoria financeira invalida.")

            boleto = Boleto(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                cliente_id=cliente_id,
                venda_id=data.get("venda_id"),
                banco_emissor_id=banco_emissor.id,
                configuracao_parcelamento_id=data.get("configuracao_parcelamento_id"),
                numero_boleto=numero_boleto,
                nosso_numero=data.get("nosso_numero"),
                status=StatusBoleto.PENDENTE,
                status_bancario=StatusBancarioBoleto.NAO_REGISTRADO,
                provider_codigo=None,
                ambiente_bancario="HOMOLOGACAO" if getattr(banco_emissor.ambiente, "value", "sandbox") == "sandbox" else "PRODUCAO",
                valor_nominal=valor_nominal,
                valor_pago=Decimal("0.00"),
                valor_restante=valor_nominal,
                data_emissao=TimeService.now_utc_naive(),
                data_vencimento=data_vencimento,
                data_pagamento=None,
                data_baixa=None,
                forma_pagamento_id=forma_pagamento.id,
                categoria_id=categoria.id,
                codigo_barras=data.get("codigo_barras"),
                linha_digitavel=data.get("linha_digitavel"),
                arquivo_pdf_path=data.get("arquivo_pdf_path"),
                arquivo_html_path=data.get("arquivo_html_path"),
                observacao=(data.get("observacao") or "").strip() or None,
            )
            BoletoRepository.adicionar(boleto)
            BoletoRepository.flush()

            parcelas = BoletoService._criar_parcelas(boleto, data, tenant_id, funcionario_id)
            boleto.status = StatusBoleto.EMITIDO if parcelas else StatusBoleto.PENDENTE
            if parcelas:
                boleto.valor_restante = sum((p.valor_restante or Decimal("0.00")) for p in parcelas)
            BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.EMISSAO, "Boleto criado internamente", None, funcionario_id)
            BoletoRepository.salvar()
            return BoletoService.serializar_boleto(boleto)
        except Exception:
            BoletoRepository.rollback()
            raise

    @staticmethod
    def registrar_boleto(tenant_id, escopo, boleto_id, funcionario_id):
        try:
            boleto = BoletoRepository.buscar_boleto(boleto_id, tenant_id)
            if not boleto:
                raise LookupError("Boleto nao encontrado.")
            AcessoEmpresaService.validar_empresa(boleto.empresa_id, escopo)
            if boleto.status_bancario == StatusBancarioBoleto.REGISTRADO:
                return BoletoService.serializar_boleto(boleto)
            if boleto.status in [StatusBoleto.PAGO, StatusBoleto.CANCELADO, StatusBoleto.ESTORNADO]:
                raise ValueError("Esse boleto nao pode ser registrado no banco.")

            provider = get_boleto_provider(boleto.banco_emissor)
            idempotency_key = boleto.idempotency_key_registro or f"boleto:{tenant_id}:{boleto.id}:{boleto.numero_boleto}"
            boleto.idempotency_key_registro = idempotency_key
            boleto.status_bancario = StatusBancarioBoleto.REGISTRO_SOLICITADO
            boleto.provider_codigo = provider.provider_codigo
            BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.REGISTRO_SOLICITADO, "Registro bancario solicitado ao provider.", None, funcionario_id)
            resultado = provider.registrar(boleto, idempotency_key)

            boleto.provider_codigo = resultado.provider_codigo
            boleto.mensagem_retorno_banco = resultado.mensagem
            if resultado.success:
                boleto.status_bancario = StatusBancarioBoleto.REGISTRADO
                boleto.registro_bancario_id = resultado.external_id
                boleto.cliente_externo_id = resultado.customer_id
                boleto.protocolo_registro = resultado.protocolo
                boleto.nosso_numero = resultado.nosso_numero
                boleto.codigo_barras = resultado.codigo_barras
                boleto.linha_digitavel = resultado.linha_digitavel
                boleto.arquivo_pdf_path = resultado.pdf_path
                boleto.arquivo_html_path = resultado.html_path
                boleto.boleto_url = resultado.boleto_url
                boleto.registrado_em = TimeService.now_utc_naive()
                BoletoService._registrar_arquivo_boleto(boleto, "PDF", resultado.pdf_path, resultado)
                BoletoService._registrar_arquivo_boleto(boleto, "HTML", resultado.html_path, resultado)
                BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.REGISTRO_BANCARIO, "Boleto registrado em ambiente de homologacao.", None, funcionario_id)
            else:
                boleto.status_bancario = StatusBancarioBoleto.REJEITADO
                BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.REGISTRO_REJEITADO, resultado.mensagem or "Registro bancario rejeitado.", None, funcionario_id)

            BoletoRepository.salvar()
            return BoletoService.serializar_boleto(boleto)
        except Exception:
            BoletoRepository.rollback()
            raise

    @staticmethod
    def consultar_status_bancario(tenant_id, escopo, boleto_id, funcionario_id):
        try:
            boleto = BoletoRepository.buscar_boleto(boleto_id, tenant_id)
            if not boleto:
                raise LookupError("Boleto nao encontrado.")
            AcessoEmpresaService.validar_empresa(boleto.empresa_id, escopo)
            provider = get_boleto_provider(boleto.banco_emissor)
            resultado = provider.consultar(boleto)
            boleto.provider_codigo = resultado.provider_codigo
            boleto.mensagem_retorno_banco = resultado.mensagem
            boleto.codigo_barras = resultado.codigo_barras or boleto.codigo_barras
            boleto.linha_digitavel = resultado.linha_digitavel or boleto.linha_digitavel
            boleto.boleto_url = resultado.boleto_url or getattr(boleto, "boleto_url", None)
            boleto.ultimo_retorno_bancario_em = TimeService.now_utc_naive()
            if resultado.external_status in ["RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"]:
                boleto.status_bancario = StatusBancarioBoleto.PAGO
            elif resultado.external_status in ["OVERDUE", "PENDING"]:
                boleto.status_bancario = StatusBancarioBoleto.REGISTRADO
            BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.WEBHOOK_BANCARIO, resultado.mensagem or "Consulta bancaria executada.", None, funcionario_id)
            BoletoRepository.salvar()
            return BoletoService.serializar_boleto(boleto)
        except Exception:
            BoletoRepository.rollback()
            raise

    @staticmethod
    def processar_retorno_bancario(tenant_id, escopo, boleto_id, data, funcionario_id):
        try:
            boleto = BoletoRepository.buscar_boleto(boleto_id, tenant_id)
            if not boleto:
                raise LookupError("Boleto nao encontrado.")
            AcessoEmpresaService.validar_empresa(boleto.empresa_id, escopo)
            provider = get_boleto_provider(boleto.banco_emissor)
            evento = provider.processar_retorno(boleto, data or {})
            event_id = evento.get("event_id") or f"{provider.provider_codigo}:{boleto.id}:{evento.get('tipo_evento')}:{evento.get('valor_pago')}"
            existente = RetornoBancarioBoleto.query.filter_by(
                tenant_id=tenant_id,
                provider_codigo=provider.provider_codigo,
                event_id=event_id,
            ).first()
            if existente:
                return BoletoService.serializar_boleto(boleto)

            retorno = RetornoBancarioBoleto(
                tenant_id=tenant_id,
                boleto_id=boleto.id,
                provider_codigo=provider.provider_codigo,
                event_id=event_id,
                tipo_evento=evento.get("tipo_evento") or "PAGAMENTO",
                payload_resumido=str(data or {})[:2000],
            )
            BoletoRepository.adicionar(retorno)
            boleto.ultimo_retorno_bancario_em = TimeService.now_utc_naive()
            if evento.get("external_id") and not boleto.registro_bancario_id:
                boleto.registro_bancario_id = evento.get("external_id")
            if evento.get("external_status"):
                boleto.mensagem_retorno_banco = f"Status externo: {evento.get('external_status')}"
            BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.WEBHOOK_BANCARIO, evento.get("mensagem") or "Retorno bancario recebido.", None, funcionario_id)

            if (evento.get("tipo_evento") or "").upper() in {"PAGAMENTO", "PAGO", "LIQUIDADO"}:
                resultado = BoletoService._aplicar_baixa(boleto, tenant_id, evento.get("valor_pago"), funcionario_id, origem="BANCARIA")
                boleto.status_bancario = StatusBancarioBoleto.PAGO if boleto.status == StatusBoleto.PAGO else boleto.status_bancario
                BoletoRepository.salvar()
                return resultado

            BoletoRepository.salvar()
            return BoletoService.serializar_boleto(boleto)
        except Exception:
            BoletoRepository.rollback()
            raise

    @staticmethod
    def _criar_parcelas(boleto, data, tenant_id, funcionario_id):
        parcelas_input = data.get("parcelas") or []
        if not parcelas_input:
            return []

        parcelas = []
        for item in parcelas_input:
            numero_parcela = int(item.get("numero_parcela") or 1)
            valor_parcela = BoletoService._to_decimal(item.get("valor_parcela"), "valor_parcela")
            data_vencimento = BoletoService._to_optional_date(item.get("data_vencimento")) or boleto.data_vencimento
            parcela = ParcelaBoleto(
                boleto_id=boleto.id,
                numero_parcela=numero_parcela,
                valor_parcela=valor_parcela,
                valor_pago=Decimal("0.00"),
                valor_restante=valor_parcela,
                data_vencimento=data_vencimento,
                data_pagamento=None,
                status=StatusBoleto.EMITIDO,
                juros_calculados=Decimal("0.00"),
                multa_calculada=Decimal("0.00"),
                desconto_aplicado=Decimal("0.00"),
                observacao=(item.get("observacao") or "").strip() or None,
            )
            BoletoRepository.adicionar(parcela)
            parcelas.append(parcela)
        BoletoRepository.flush()
        return parcelas

    @staticmethod
    def baixar_boleto(tenant_id, escopo, boleto_id, data, funcionario_id):
        try:
            boleto = BoletoRepository.buscar_boleto(boleto_id, tenant_id)
            if not boleto:
                raise LookupError("Boleto nao encontrado.")
            AcessoEmpresaService.validar_empresa(boleto.empresa_id, escopo)
            valor = BoletoService._to_decimal(data.get("valor_pago") or data.get("valor"), "valor_pago")
            if valor <= 0:
                raise ValueError("valor_pago deve ser maior que zero.")
            if boleto.status in [StatusBoleto.PAGO, StatusBoleto.CANCELADO, StatusBoleto.ESTORNADO]:
                raise ValueError("Esse boleto nao pode receber baixa.")

            if boleto.valor_restante < valor:
                raise ValueError("valor_pago nao pode exceder o valor restante do boleto.")

            BoletoService._aplicar_baixa(boleto, tenant_id, valor, funcionario_id, origem="MANUAL")
            BoletoRepository.salvar()
            return BoletoService.serializar_boleto(boleto)
        except Exception:
            BoletoRepository.rollback()
            raise

    @staticmethod
    def recalcular_juros_multa(tenant_id, escopo, boleto_id, data_referencia=None, funcionario_id=None):
        try:
            boleto = BoletoRepository.buscar_boleto(boleto_id, tenant_id)
            if not boleto:
                raise LookupError("Boleto nao encontrado.")
            AcessoEmpresaService.validar_empresa(boleto.empresa_id, escopo)
            data_ref = BoletoService._to_optional_date(data_referencia) or date.today()
            regra = BoletoRepository.buscar_regra_vigente_em(tenant_id, boleto.empresa_id, data_ref, banco_emissor_id=boleto.banco_emissor_id)
            if regra is None:
                raise ValueError("Nao existe regra de juros/multa vigente para esta empresa.")

            total_juros = Decimal("0.00")
            total_multa = Decimal("0.00")
            for parcela in boleto.parcelas:
                resultado = BoletoService.calcular_juros_multa(
                    valor_nominal=parcela.valor_parcela,
                    valor_pago=parcela.valor_pago,
                    data_vencimento=parcela.data_vencimento,
                    data_referencia=data_ref,
                    regra={
                        "tipo_multa": regra.tipo_multa,
                        "percentual_multa": regra.percentual_multa,
                        "valor_fixo_multa": regra.valor_fixo_multa,
                        "tipo_juros": regra.tipo_juros,
                        "percentual_juros": regra.percentual_juros,
                        "dias_carencia": regra.dias_carencia,
                        "base_calculo": regra.base_calculo,
                    },
                )
                parcela.juros_calculados = resultado["juros"]
                parcela.multa_calculada = resultado["multa"]
                parcela.valor_restante = (parcela.valor_parcela + resultado["juros"] + resultado["multa"] - parcela.valor_pago).quantize(Decimal("0.01"))
                if parcela.valor_restante < Decimal("0.00"):
                    parcela.valor_restante = Decimal("0.00")
                total_juros += resultado["juros"]
                total_multa += resultado["multa"]

            boleto.valor_restante = sum(
                (parcela.valor_restante or Decimal("0.00"))
                for parcela in boleto.parcelas
            ).quantize(Decimal("0.01"))
            if boleto.data_vencimento < data_ref and boleto.status == StatusBoleto.EMITIDO:
                boleto.status = StatusBoleto.VENCIDO
            BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.RECALCULO_JUROS, "Recalculo de juros/multa aplicado", total_juros + total_multa, funcionario_id)
            BoletoRepository.salvar()
            return BoletoService.serializar_boleto(boleto)
        except Exception:
            BoletoRepository.rollback()
            raise

    @staticmethod
    def calcular_juros_multa(valor_nominal, valor_pago, data_vencimento, data_referencia, regra):
        valor_nominal = BoletoService._to_decimal_value(valor_nominal)
        valor_pago = BoletoService._to_decimal_value(valor_pago)
        data_vencimento = BoletoService._to_optional_date(data_vencimento)
        data_referencia = BoletoService._to_optional_date(data_referencia)
        if data_referencia is None:
            data_referencia = date.today()
        if data_vencimento is None:
            raise ValueError("data_vencimento e obrigatoria.")
        if data_referencia < data_vencimento:
            return {"multa": Decimal("0.00"), "juros": Decimal("0.00"), "total": Decimal("0.00")}

        multa = Decimal("0.00")
        juros = Decimal("0.00")
        dias_atraso = (data_referencia - data_vencimento).days
        tipo_multa = regra.get("tipo_multa") if isinstance(regra, dict) else getattr(regra, "tipo_multa", None)
        percentual_multa = BoletoService._to_decimal_value(regra.get("percentual_multa") if isinstance(regra, dict) else getattr(regra, "percentual_multa", None))
        valor_fixo_multa = BoletoService._to_decimal_value(regra.get("valor_fixo_multa") if isinstance(regra, dict) else getattr(regra, "valor_fixo_multa", None))
        tipo_juros = regra.get("tipo_juros") if isinstance(regra, dict) else getattr(regra, "tipo_juros", None)
        percentual_juros = BoletoService._to_decimal_value(regra.get("percentual_juros") if isinstance(regra, dict) else getattr(regra, "percentual_juros", None))
        dias_carencia = int(regra.get("dias_carencia") if isinstance(regra, dict) else getattr(regra, "dias_carencia", 0) or 0)
        base_calculo = regra.get("base_calculo") if isinstance(regra, dict) else getattr(regra, "base_calculo", BaseCalculoJurosMulta.valor_restante)

        if dias_atraso > dias_carencia:
            if tipo_multa == TipoMultaBoleto.percentual:
                multa = (valor_nominal * (percentual_multa / Decimal("100"))).quantize(Decimal("0.01"))
            elif tipo_multa == TipoMultaBoleto.fixo:
                multa = valor_fixo_multa

            if tipo_juros == TipoJurosBoleto.diario:
                valor_base = valor_nominal - valor_pago if base_calculo == BaseCalculoJurosMulta.valor_restante else valor_nominal
                juros = (valor_base * (percentual_juros / Decimal("100")) * Decimal(max(dias_atraso - dias_carencia, 0))).quantize(Decimal("0.01"))
            elif tipo_juros == TipoJurosBoleto.mensal:
                valor_base = valor_nominal - valor_pago if base_calculo == BaseCalculoJurosMulta.valor_restante else valor_nominal
                juros = (valor_base * (percentual_juros / Decimal("100")) * Decimal(max((dias_atraso - dias_carencia) // 30, 0))).quantize(Decimal("0.01"))

        total = (multa + juros).quantize(Decimal("0.01"))
        return {"multa": multa.quantize(Decimal("0.01")), "juros": juros.quantize(Decimal("0.01")), "total": total}

    @staticmethod
    def _registrar_evento(boleto, parcela, tipo_evento, descricao, valor, funcionario_id):
        evento = EventoBoleto(
            boleto_id=boleto.id,
            parcela_id=getattr(parcela, "id", None),
            tipo_evento=tipo_evento,
            descricao=descricao,
            valor=BoletoService._to_decimal_value(valor),
            regra_juros_multa_id=None,
            criado_por_funcionario_id=funcionario_id,
            criado_em=TimeService.now_utc_naive(),
        )
        BoletoRepository.adicionar(evento)

    @staticmethod
    def _registrar_arquivo_boleto(boleto, tipo, path, resultado):
        if not path:
            return
        BoletoRepository.adicionar(ArquivoBoleto(
            tenant_id=boleto.tenant_id,
            boleto_id=boleto.id,
            tipo=tipo,
            ambiente=boleto.ambiente_bancario,
            path=path,
            provider_codigo=resultado.provider_codigo,
            identificador_externo=resultado.external_id,
        ))

    @staticmethod
    def _aplicar_baixa(boleto, tenant_id, valor, funcionario_id, origem="MANUAL"):
        valor = BoletoService._to_decimal(valor, "valor_pago")
        if valor <= 0:
            raise ValueError("valor_pago deve ser maior que zero.")
        if boleto.valor_restante < valor:
            raise ValueError("valor_pago nao pode exceder o valor restante do boleto.")

        boleto.valor_pago = (boleto.valor_pago + valor).quantize(Decimal("0.01"))
        boleto.valor_restante = (boleto.valor_restante - valor).quantize(Decimal("0.01"))
        boleto.data_pagamento = TimeService.now_utc_naive()
        boleto.data_baixa = TimeService.now_utc_naive()
        boleto.origem_baixa = origem
        boleto.status = StatusBoleto.PAGO if boleto.valor_restante <= Decimal("0.00") else StatusBoleto.PARCIALMENTE_PAGO

        lancamento = LancamentoFinanceiro(
            tenant_id=tenant_id,
            empresa_id=boleto.empresa_id,
            funcionario_id=funcionario_id,
            categoria_id=boleto.categoria_id,
            forma_pagamento_id=boleto.forma_pagamento_id,
            boleto_id=boleto.id,
            parcela_boleto_id=None,
            tipo=TipoFinanceiro.ENTRADA,
            descricao=f"Baixa de boleto {boleto.numero_boleto}",
            valor=valor,
            data_lancamento=TimeService.now_utc_naive(),
            data_competencia=date.today(),
            observacao=f"Baixa de boleto via {origem.lower()}",
        )
        BoletoRepository.adicionar(lancamento)
        BoletoService._registrar_evento(boleto, None, TipoEventoBoleto.PAGAMENTO, f"Baixa registrada via {origem.lower()}", valor, funcionario_id)
        return BoletoService.serializar_boleto(boleto)

    @staticmethod
    def _gerar_numero_boleto(tenant_id):
        return f"{tenant_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def serializar_boleto(boleto):
        return {
            "id": boleto.id,
            "tenant_id": boleto.tenant_id,
            "empresa_id": boleto.empresa_id,
            "cliente_id": boleto.cliente_id,
            "cliente_nome": boleto.cliente.nome if getattr(boleto, "cliente", None) else None,
            "venda_id": boleto.venda_id,
            "banco_emissor_id": boleto.banco_emissor_id,
            "banco_emissor_nome": boleto.banco_emissor.banco_nome if getattr(boleto, "banco_emissor", None) else None,
            "numero_boleto": boleto.numero_boleto,
            "nosso_numero": boleto.nosso_numero,
            "status": boleto.status.value if boleto.status else None,
            "status_bancario": boleto.status_bancario.value if getattr(boleto, "status_bancario", None) else None,
            "provider_codigo": getattr(boleto, "provider_codigo", None),
            "ambiente_bancario": getattr(boleto, "ambiente_bancario", None),
            "registro_bancario_id": getattr(boleto, "registro_bancario_id", None),
            "cliente_externo_id": getattr(boleto, "cliente_externo_id", None),
            "protocolo_registro": getattr(boleto, "protocolo_registro", None),
            "mensagem_retorno_banco": getattr(boleto, "mensagem_retorno_banco", None),
            "registrado_em": TimeService.serialize_utc_iso(getattr(boleto, "registrado_em", None)),
            "origem_baixa": getattr(boleto, "origem_baixa", None),
            "valor_nominal": str(BoletoService._to_decimal_value(boleto.valor_nominal)),
            "valor_pago": str(BoletoService._to_decimal_value(boleto.valor_pago)),
            "valor_restante": str(BoletoService._to_decimal_value(boleto.valor_restante)),
            "data_emissao": TimeService.serialize_utc_iso(boleto.data_emissao),
            "data_vencimento": boleto.data_vencimento.isoformat() if boleto.data_vencimento else None,
            "data_pagamento": TimeService.serialize_utc_iso(boleto.data_pagamento) if boleto.data_pagamento else None,
            "data_baixa": TimeService.serialize_utc_iso(boleto.data_baixa) if boleto.data_baixa else None,
            "forma_pagamento_id": boleto.forma_pagamento_id,
            "categoria_id": boleto.categoria_id,
            "codigo_barras": boleto.codigo_barras,
            "linha_digitavel": boleto.linha_digitavel,
            "arquivo_pdf_path": boleto.arquivo_pdf_path,
            "arquivo_html_path": boleto.arquivo_html_path,
            "boleto_url": getattr(boleto, "boleto_url", None),
            "observacao": boleto.observacao,
            "parcelas": [{
                "id": item.id,
                "numero_parcela": item.numero_parcela,
                "valor_parcela": str(BoletoService._to_decimal_value(item.valor_parcela)),
                "valor_pago": str(BoletoService._to_decimal_value(item.valor_pago)),
                "valor_restante": str(BoletoService._to_decimal_value(item.valor_restante)),
                "data_vencimento": item.data_vencimento.isoformat() if item.data_vencimento else None,
                "data_pagamento": TimeService.serialize_utc_iso(item.data_pagamento) if item.data_pagamento else None,
                "status": item.status.value if item.status else None,
                "juros_calculados": str(BoletoService._to_decimal_value(item.juros_calculados)),
                "multa_calculada": str(BoletoService._to_decimal_value(item.multa_calculada)),
                "desconto_aplicado": str(BoletoService._to_decimal_value(item.desconto_aplicado)),
                "observacao": item.observacao,
            } for item in getattr(boleto, "parcelas", []) or []],
            "eventos": [{
                "id": item.id,
                "tipo_evento": item.tipo_evento.value if item.tipo_evento else None,
                "descricao": item.descricao,
                "valor": str(BoletoService._to_decimal_value(item.valor)),
                "criado_em": TimeService.serialize_utc_iso(item.criado_em),
            } for item in getattr(boleto, "eventos", []) or []],
        }

    @staticmethod
    def _to_int(value, field_name):
        if value in (None, ""):
            raise ValueError(f"{field_name} e obrigatorio.")
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} invalido.")

    @staticmethod
    def _to_decimal(value, field_name):
        if value in (None, ""):
            raise ValueError(f"Informe {field_name}.")
        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")
        if valor < 0:
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")
        return valor.quantize(Decimal("0.01"))

    @staticmethod
    def _to_decimal_value(value):
        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _to_optional_date(value):
        if value in (None, ""):
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data invalida. Use o formato YYYY-MM-DD.")

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "t", "sim", "yes", "on"}
