import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.db import AmbienteFiscal, RegimeTributarioFiscal
from app.services.boleto_provider import AsaasProvider
from app.services.fiscal_provider import FocusNFeProvider


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        if isinstance(self.data, bytes):
            return self.data
        return json.dumps(self.data).encode("utf-8")


def test_asaas_provider_cria_cliente_e_cobranca_boleto(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.get_method(), json.loads(req.data.decode("utf-8")) if req.data else None, req.headers))
        if req.full_url.endswith("/customers"):
            return FakeResponse({"id": "cus_123"})
        return FakeResponse({
            "id": "pay_123",
            "status": "PENDING",
            "bankSlipUrl": "https://sandbox.asaas.com/b/pdf",
            "invoiceUrl": "https://sandbox.asaas.com/i/123",
            "identificationField": "001900000000000000000",
        })

    monkeypatch.setattr("app.services.boleto_provider.request.urlopen", fake_urlopen)
    config = SimpleNamespace(
        ambiente="sandbox",
        api_key="asaas-token",
        dias_apos_vencimento_cancelamento=2,
        notificacoes_desabilitadas=True,
    )
    boleto = SimpleNamespace(
        tenant_id=1,
        id=10,
        cliente_id=20,
        cliente=SimpleNamespace(nome="Cliente Teste", documento="12345678901", email="c@test.com", telefone="11999999999"),
        cliente_externo_id=None,
        registro_bancario_id=None,
        numero_boleto="BOL-10",
        valor_restante=Decimal("150.00"),
        valor_nominal=Decimal("150.00"),
        data_vencimento=date(2026, 8, 10),
    )

    result = AsaasProvider(config).registrar(boleto, "boleto:1:10")

    assert result.success is True
    assert result.external_id == "pay_123"
    assert result.customer_id == "cus_123"
    assert result.boleto_url == "https://sandbox.asaas.com/b/pdf"
    assert calls[0][0].endswith("/customers")
    assert calls[1][2]["billingType"] == "BOLETO"
    assert calls[1][2]["externalReference"] == "boleto:1:10"


def test_focus_provider_emite_nfce_com_ref_idempotente(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.get_method(), json.loads(req.data.decode("utf-8")) if req.data else None, req.headers))
        return FakeResponse({
            "status": "autorizado",
            "codigo_status": "100",
            "protocolo": "135260000000001",
            "chave_nfe": "35260712345678000123650010000000011000000010",
            "mensagem": "Autorizado o uso da NFC-e",
        })

    monkeypatch.setattr("app.services.fiscal_provider.request.urlopen", fake_urlopen)
    config = SimpleNamespace(
        ambiente=AmbienteFiscal.HOMOLOGACAO,
        focus_token_homologacao="focus-token-hom",
        focus_token_producao=None,
        focus_cnpj_emitente="12345678000123",
        regime_tributario=RegimeTributarioFiscal.SIMPLES_NACIONAL,
        serie_nfce=1,
    )
    produto = SimpleNamespace(nome="Produto Teste", ncm="22021000")
    item = SimpleNamespace(produto_id=1, produto=produto, quantidade=2, valor_unitario=Decimal("5.00"), valor_total=Decimal("10.00"))
    pagamento = SimpleNamespace(valor=Decimal("10.00"))
    venda = SimpleNamespace(
        empresa=SimpleNamespace(cnpj="12.345.678/0001-23"),
        cliente=SimpleNamespace(nome="Consumidor", documento="12345678901"),
        itens=[item],
        pagamentos=[pagamento],
    )
    nota = SimpleNamespace(tenant_id=1, venda=venda, numero=1, serie=1, ambiente=AmbienteFiscal.HOMOLOGACAO)

    result = FocusNFeProvider(config).transmitir_nfce(nota, None, "nfce:1:1")

    assert result.success is True
    assert result.protocolo == "135260000000001"
    assert result.chave_acesso == "35260712345678000123650010000000011000000010"
    assert calls[0][0].endswith("/v2/nfce?ref=nfce%3A1%3A1&completa=1")
    assert calls[0][2]["cnpj_emitente"] == "12345678000123"
    assert calls[0][2]["items"][0]["ncm"] == "22021000"
