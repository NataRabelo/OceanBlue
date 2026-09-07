from app.security.integrations import require_real_integration
import hashlib
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib import error, parse, request

from flask import current_app

from app.security.field_crypto import FieldCrypto
from app.services.time_service import TimeService


@dataclass
class BoletoProviderResult:
    success: bool
    provider_codigo: str
    external_id: str | None = None
    protocolo: str | None = None
    nosso_numero: str | None = None
    codigo_barras: str | None = None
    linha_digitavel: str | None = None
    pdf_path: str | None = None
    html_path: str | None = None
    mensagem: str | None = None
    codigo_retorno: str | None = None
    raw_resumido: str | None = None
    external_status: str | None = None
    boleto_url: str | None = None
    customer_id: str | None = None


class BoletoProvider:
    provider_codigo = "base"

    def registrar(self, boleto, idempotency_key):
        raise NotImplementedError

    def processar_retorno(self, boleto, payload):
        raise NotImplementedError

    def consultar(self, boleto):
        raise NotImplementedError


class ProviderCommunicationError(RuntimeError):
    pass


class AsaasProvider(BoletoProvider):
    provider_codigo = "asaas"

    STATUS_PAGOS = {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}

    def __init__(self, configuracao):
        self.configuracao = configuracao
        self.base_url = "https://api-sandbox.asaas.com/v3" if configuracao.ambiente == "sandbox" else "https://api.asaas.com/v3"
        self.timeout = int(os.getenv("ASAAS_TIMEOUT_SECONDS", "20"))

    def registrar(self, boleto, idempotency_key):
        if boleto.registro_bancario_id:
            consulta = self.consultar(boleto)
            consulta.external_id = boleto.registro_bancario_id
            return consulta

        customer_id = boleto.cliente_externo_id or self._criar_cliente(boleto)
        payload = {
            "customer": customer_id,
            "billingType": "BOLETO",
            "value": float(_to_decimal(boleto.valor_restante or boleto.valor_nominal)),
            "dueDate": boleto.data_vencimento.isoformat(),
            "description": f"Boleto OceanBlue {boleto.numero_boleto}",
            "externalReference": idempotency_key,
        }
        if self.configuracao.dias_apos_vencimento_cancelamento is not None:
            payload["daysAfterDueDateToRegistrationCancellation"] = int(self.configuracao.dias_apos_vencimento_cancelamento)

        data = self._request("POST", "/payments", payload)
        return BoletoProviderResult(
            success=True,
            provider_codigo=self.provider_codigo,
            external_id=data.get("id"),
            protocolo=data.get("id"),
            nosso_numero=data.get("nossoNumero") or data.get("nosso_numero"),
            codigo_barras=data.get("identificationField"),
            linha_digitavel=data.get("identificationField"),
            pdf_path=None,
            html_path=None,
            boleto_url=data.get("bankSlipUrl") or data.get("invoiceUrl"),
            customer_id=customer_id,
            mensagem=f"Cobranca Asaas criada com status {data.get('status') or 'desconhecido'}.",
            codigo_retorno=str(data.get("status") or "CREATED"),
            external_status=data.get("status"),
            raw_resumido=_safe_json(data),
        )

    def consultar(self, boleto):
        if not boleto.registro_bancario_id:
            raise ValueError("Boleto ainda nao possui identificador Asaas.")
        data = self._request("GET", f"/payments/{parse.quote(str(boleto.registro_bancario_id))}", None)
        return BoletoProviderResult(
            success=True,
            provider_codigo=self.provider_codigo,
            external_id=data.get("id"),
            protocolo=data.get("id"),
            nosso_numero=data.get("nossoNumero") or data.get("nosso_numero"),
            codigo_barras=data.get("identificationField"),
            linha_digitavel=data.get("identificationField"),
            boleto_url=data.get("bankSlipUrl") or data.get("invoiceUrl"),
            mensagem=f"Consulta Asaas retornou status {data.get('status') or 'desconhecido'}.",
            codigo_retorno=str(data.get("status") or "UNKNOWN"),
            external_status=data.get("status"),
            raw_resumido=_safe_json(data),
        )

    def processar_retorno(self, boleto, payload):
        payment = payload.get("payment") or {}
        event_name = str(payload.get("event") or payment.get("status") or "").upper()
        payment_id = str(payment.get("id") or payload.get("payment_id") or "")
        return {
            "event_id": str(payload.get("id") or f"{event_name}:{payment_id}"),
            "tipo_evento": event_name,
            "valor_pago": payment.get("value") or payment.get("netValue") or boleto.valor_restante,
            "external_id": payment_id,
            "external_status": payment.get("status") or event_name.replace("PAYMENT_", ""),
            "mensagem": f"Webhook Asaas recebido: {event_name or 'evento sem tipo'}.",
        }

    def _criar_cliente(self, boleto):
        cliente = boleto.cliente
        payload = {
            "name": getattr(cliente, "nome", None) or f"Cliente {boleto.cliente_id}",
            "cpfCnpj": _only_digits(getattr(cliente, "documento", "")),
            "email": getattr(cliente, "email", None),
            "mobilePhone": _only_digits(getattr(cliente, "telefone", "") or getattr(cliente, "whatsapp", "")),
            "externalReference": f"tenant:{boleto.tenant_id}:cliente:{boleto.cliente_id}",
            "notificationDisabled": bool(self.configuracao.notificacoes_desabilitadas),
        }
        payload = {key: value for key, value in payload.items() if value not in (None, "")}
        data = self._request("POST", "/customers", payload)
        return data.get("id")

    def _request(self, method, path, payload):
        require_real_integration()
        token = FieldCrypto.decrypt(self.configuracao.api_key)
        if not token:
            raise ValueError("Token Asaas nao configurado para a empresa.")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "access_token": token,
                "User-Agent": "OceanBlue-PDV/1.0",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise ProviderCommunicationError(f"Asaas HTTP {exc.code}: {_extract_error_message(raw)}") from exc
        except error.URLError as exc:
            raise ProviderCommunicationError(f"Falha de comunicacao com Asaas: {exc.reason}") from exc


class MockApiBancariaProvider(BoletoProvider):
    provider_codigo = "mock_api_bancaria"

    def registrar(self, boleto, idempotency_key):
        if "REJEITAR" in (boleto.observacao or "").upper():
            return BoletoProviderResult(
                success=False,
                provider_codigo=self.provider_codigo,
                codigo_retorno="MOCK_REJEICAO",
                mensagem="Registro rejeitado pelo provider de homologacao.",
                raw_resumido="mock: registro rejeitado",
            )

        digest = hashlib.sha1(idempotency_key.encode("utf-8")).hexdigest().upper()
        nosso_numero = boleto.nosso_numero or digest[:12]
        external_id = f"OBBOL{digest[:18]}"
        protocolo = f"HOM{digest[18:30]}"
        codigo_barras = f"2379{digest[:40]}"
        linha_digitavel = f"23790.{digest[:5]} {digest[5:10]}.{digest[10:15]} {digest[15:20]}.{digest[20:25]} 1 {digest[25:39]}"
        html_path, pdf_path = self._salvar_comprovantes(boleto, external_id, protocolo, linha_digitavel)
        return BoletoProviderResult(
            success=True,
            provider_codigo=self.provider_codigo,
            external_id=external_id,
            protocolo=protocolo,
            nosso_numero=nosso_numero,
            codigo_barras=codigo_barras,
            linha_digitavel=linha_digitavel,
            pdf_path=pdf_path,
            html_path=html_path,
            mensagem="Boleto registrado em homologacao pelo provider mock.",
            codigo_retorno="HOMOLOGADO",
            raw_resumido="mock: registro homologado",
        )

    def processar_retorno(self, boleto, payload):
        status = str(payload.get("status") or payload.get("tipo_evento") or "").upper()
        valor_pago = payload.get("valor_pago") or payload.get("valor") or boleto.valor_restante
        return {
            "event_id": str(payload.get("event_id") or payload.get("id") or ""),
            "tipo_evento": status or "PAGAMENTO",
            "valor_pago": valor_pago,
            "mensagem": payload.get("mensagem") or "Retorno bancario homologado processado.",
        }

    def _salvar_comprovantes(self, boleto, external_id, protocolo, linha_digitavel):
        base_dir = _storage_base() / "tenants" / str(boleto.tenant_id) / "boletos" / TimeService.now_utc_naive().strftime("%Y/%m/%d")
        base_dir.mkdir(parents=True, exist_ok=True)
        stem = f"boleto_{boleto.id}_{external_id}"
        html_path = base_dir / f"{stem}.html"
        pdf_path = base_dir / f"{stem}.pdf"
        html = f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Boleto {boleto.numero_boleto}</title></head>
<body>
<h1>Boleto homologacao OceanBlue</h1>
<p>Numero interno: {boleto.numero_boleto}</p>
<p>Registro externo: {external_id}</p>
<p>Protocolo: {protocolo}</p>
<p>Linha digitavel: {linha_digitavel}</p>
<p>Valor: {boleto.valor_restante}</p>
<p>Este arquivo e um comprovante de homologacao/mock, nao representa cobranca bancaria de producao.</p>
</body>
</html>
"""
        html_path.write_text(html, encoding="utf-8")
        pdf_path.write_text(
            "PDF homologacao OceanBlue\n"
            f"Boleto: {boleto.numero_boleto}\n"
            f"Registro externo: {external_id}\n"
            f"Protocolo: {protocolo}\n"
            "Substituir pelo PDF oficial do banco/integrador antes de producao.\n",
            encoding="utf-8",
        )
        return str(html_path), str(pdf_path)


def get_boleto_provider(_banco_emissor=None):
    empresa = getattr(_banco_emissor, "empresa", None)
    configuracao = getattr(empresa, "configuracao_asaas", None)
    if configuracao and configuracao.ativo and configuracao.api_key:
        raise PermissionError("Integracao bancaria real desativada nesta versao.")
    return MockApiBancariaProvider()


def _storage_base():
    configured = os.getenv("OCEANBLUE_STORAGE_PATH")
    if configured:
        return Path(configured)
    return Path(current_app.instance_path) / "storage"


def _only_digits(value):
    return "".join(char for char in str(value or "") if char.isdigit())


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _safe_json(data):
    return json.dumps(data, ensure_ascii=False, default=str)[:2000]


def _extract_error_message(raw):
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return raw[:500]
    if isinstance(data, dict) and data.get("errors"):
        return "; ".join(str(item.get("description") or item) for item in data["errors"])[:500]
    return str(data)[:500]
