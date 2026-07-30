from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.db import BaseCalculoJurosMulta, StatusBancarioBoleto, StatusBoleto, TipoJurosBoleto, TipoMultaBoleto
from app.services.boleto_provider import BoletoProviderResult
from app.services.boleto_service import BoletoService


def test_calcular_juros_multa_aplica_regra_basica():
    regra = {
        "tipo_multa": TipoMultaBoleto.percentual,
        "percentual_multa": Decimal("2"),
        "tipo_juros": TipoJurosBoleto.diario,
        "percentual_juros": Decimal("1"),
        "dias_carencia": 0,
        "base_calculo": BaseCalculoJurosMulta.valor_restante,
    }

    resultado = BoletoService.calcular_juros_multa(
        valor_nominal=Decimal("100.00"),
        valor_pago=Decimal("0.00"),
        data_vencimento=date(2024, 1, 1),
        data_referencia=date(2024, 1, 3),
        regra=regra,
    )

    assert resultado["multa"] == Decimal("2.00")
    assert resultado["juros"] == Decimal("2.00")
    assert resultado["total"] == Decimal("4.00")


def test_recalcular_juros_multa_nao_reaplica_total_de_forma_cumulativa(monkeypatch):
    regra = SimpleNamespace(
        tipo_multa=TipoMultaBoleto.percentual,
        percentual_multa=Decimal("2"),
        valor_fixo_multa=None,
        tipo_juros=TipoJurosBoleto.diario,
        percentual_juros=Decimal("1"),
        dias_carencia=0,
        base_calculo=BaseCalculoJurosMulta.valor_restante,
    )
    parcela = SimpleNamespace(
        id=1,
        numero_parcela=1,
        valor_parcela=Decimal("100.00"),
        valor_pago=Decimal("0.00"),
        valor_restante=Decimal("100.00"),
        data_vencimento=date(2024, 1, 1),
        data_pagamento=None,
        status=StatusBoleto.EMITIDO,
        juros_calculados=Decimal("0.00"),
        multa_calculada=Decimal("0.00"),
        desconto_aplicado=Decimal("0.00"),
        observacao=None,
    )
    boleto = SimpleNamespace(
        id=1,
        empresa_id=1,
        banco_emissor_id=1,
        data_vencimento=date(2024, 1, 1),
        status=StatusBoleto.EMITIDO,
        valor_restante=Decimal("100.00"),
        parcelas=[parcela],
        eventos=[],
        tenant_id=1,
        cliente_id=1,
        venda_id=None,
        numero_boleto="BOL-1",
        nosso_numero=None,
        valor_nominal=Decimal("100.00"),
        valor_pago=Decimal("0.00"),
        data_emissao=None,
        data_pagamento=None,
        data_baixa=None,
        forma_pagamento_id=1,
        categoria_id=1,
        codigo_barras=None,
        linha_digitavel=None,
        arquivo_pdf_path=None,
        arquivo_html_path=None,
        observacao=None,
    )

    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.buscar_boleto", lambda *_args, **_kwargs: boleto)
    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.buscar_regra_vigente_em", lambda *_args, **_kwargs: regra)
    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.salvar", lambda: None)
    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.rollback", lambda: None)
    monkeypatch.setattr("app.services.boleto_service.AcessoEmpresaService.validar_empresa", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.boleto_service.BoletoService._registrar_evento", lambda *_args, **_kwargs: None)

    primeiro = BoletoService.recalcular_juros_multa(1, {}, 1, data_referencia="2024-01-03")
    segundo = BoletoService.recalcular_juros_multa(1, {}, 1, data_referencia="2024-01-03")

    assert primeiro["valor_restante"] == "104.00"
    assert segundo["valor_restante"] == "104.00"


def test_registrar_boleto_atualiza_status_bancario_e_preserva_status_interno(monkeypatch):
    boleto = SimpleNamespace(
        id=1,
        empresa_id=1,
        banco_emissor=SimpleNamespace(banco_nome="Banco Homologacao"),
        banco_emissor_id=1,
        status=StatusBoleto.EMITIDO,
        status_bancario=StatusBancarioBoleto.NAO_REGISTRADO,
        ambiente_bancario="HOMOLOGACAO",
        idempotency_key_registro=None,
        numero_boleto="BOL-1",
        nosso_numero=None,
        observacao=None,
        tenant_id=1,
        cliente_id=1,
        cliente=None,
        venda_id=None,
        banco_emissor_nome=None,
        valor_nominal=Decimal("100.00"),
        valor_pago=Decimal("0.00"),
        valor_restante=Decimal("100.00"),
        data_emissao=None,
        data_vencimento=date(2024, 1, 10),
        data_pagamento=None,
        data_baixa=None,
        forma_pagamento_id=1,
        categoria_id=1,
        codigo_barras=None,
        linha_digitavel=None,
        arquivo_pdf_path=None,
        arquivo_html_path=None,
        eventos=[],
        parcelas=[],
    )

    class Provider:
        provider_codigo = "mock_api_bancaria"

        def registrar(self, _boleto, _idempotency_key):
            return BoletoProviderResult(
                success=True,
                provider_codigo=self.provider_codigo,
                external_id="EXT-1",
                protocolo="PROTO-1",
                nosso_numero="NN-1",
                codigo_barras="COD",
                linha_digitavel="LINHA",
                pdf_path="/tmp/boleto.pdf",
                html_path="/tmp/boleto.html",
                mensagem="Registrado",
            )

    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.buscar_boleto", lambda *_args, **_kwargs: boleto)
    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.salvar", lambda: None)
    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.rollback", lambda: None)
    monkeypatch.setattr("app.services.boleto_service.BoletoRepository.adicionar", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.boleto_service.AcessoEmpresaService.validar_empresa", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.boleto_service.get_boleto_provider", lambda *_args, **_kwargs: Provider())

    resultado = BoletoService.registrar_boleto(1, {}, 1, funcionario_id=1)

    assert resultado["status"] == "EMITIDO"
    assert resultado["status_bancario"] == "REGISTRADO"
    assert resultado["registro_bancario_id"] == "EXT-1"
    assert resultado["protocolo_registro"] == "PROTO-1"
