import hashlib
import base64
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib import error, parse, request

from flask import current_app

from app.models.db import AmbienteFiscal, RegimeTributarioFiscal
from app.security.field_crypto import FieldCrypto
from app.services.time_service import TimeService


@dataclass
class FiscalProviderResult:
    success: bool
    provider_codigo: str
    protocolo: str | None = None
    recibo: str | None = None
    codigo_retorno: str | None = None
    mensagem: str | None = None
    xml_assinado_path: str | None = None
    xml_autorizado_path: str | None = None
    danfe_path: str | None = None
    xml_url: str | None = None
    danfe_url: str | None = None
    chave_acesso: str | None = None
    status_externo: str | None = None
    raw_resumido: str | None = None


class FiscalProvider:
    provider_codigo = "base"

    def transmitir_nfce(self, nota, xml_path, idempotency_key):
        raise NotImplementedError

    def consultar_nfce(self, nota):
        raise NotImplementedError

    def cancelar_nfce(self, nota, justificativa):
        raise NotImplementedError


class FiscalCommunicationError(RuntimeError):
    pass


class FocusNFeProvider(FiscalProvider):
    provider_codigo = "focus_nfe"

    def __init__(self, configuracao):
        self.configuracao = configuracao
        self.base_url = (
            "https://homologacao.focusnfe.com.br/v2"
            if configuracao.ambiente == AmbienteFiscal.HOMOLOGACAO
            else "https://api.focusnfe.com.br/v2"
        )
        self.timeout = int(os.getenv("FOCUS_NFE_TIMEOUT_SECONDS", "30"))

    def transmitir_nfce(self, nota, xml_path, idempotency_key):
        payload = self._montar_payload_nfce(nota)
        data = self._request("POST", f"/nfce?ref={parse.quote(idempotency_key)}&completa=1", payload)
        return self._result_from_response(nota, data, idempotency_key)

    def consultar_nfce(self, nota):
        ref = nota.referencia_externa or nota.idempotency_key_envio
        if not ref:
            raise ValueError("Nota ainda nao possui referencia Focus NFe.")
        data = self._request("GET", f"/nfce/{parse.quote(ref)}?completa=1", None)
        return self._result_from_response(nota, data, ref)

    def cancelar_nfce(self, nota, justificativa):
        ref = nota.referencia_externa or nota.idempotency_key_envio
        if not ref:
            raise ValueError("Nota ainda nao possui referencia Focus NFe.")
        if not justificativa or len(justificativa.strip()) < 15:
            raise ValueError("Justificativa de cancelamento deve ter pelo menos 15 caracteres.")
        data = self._request("DELETE", f"/nfce/{parse.quote(ref)}", {"justificativa": justificativa.strip()})
        return self._result_from_response(nota, data, ref)

    def _result_from_response(self, nota, data, ref):
        status = str(data.get("status") or data.get("status_sefaz") or "").lower()
        autorizado = status in {"autorizado", "cancelado"} or str(data.get("codigo_status") or data.get("codigo_sefaz")) in {"100", "101", "135"}
        xml_url = data.get("caminho_xml_nota_fiscal") or data.get("xml") or data.get("url_xml")
        danfe_url = data.get("caminho_danfe") or data.get("caminho_danfe_pdf") or data.get("danfe") or data.get("url_danfe")
        xml_path = self._salvar_url(nota, xml_url, "xml-autorizado.xml") if xml_url else None
        danfe_path = self._salvar_url(nota, danfe_url, "danfe.html") if danfe_url else None
        protocolo = data.get("protocolo") or data.get("numero_protocolo") or data.get("protocolo_autorizacao")
        chave = data.get("chave_nfe") or data.get("chave_acesso") or data.get("chave")
        mensagem = data.get("mensagem") or data.get("mensagem_sefaz") or data.get("status") or "Retorno Focus NFe recebido."
        return FiscalProviderResult(
            success=autorizado,
            provider_codigo=self.provider_codigo,
            protocolo=protocolo,
            recibo=data.get("recibo"),
            codigo_retorno=str(data.get("codigo_status") or data.get("codigo_sefaz") or data.get("status") or ""),
            mensagem=mensagem,
            xml_assinado_path=None,
            xml_autorizado_path=xml_path,
            danfe_path=danfe_path,
            xml_url=xml_url,
            danfe_url=danfe_url,
            chave_acesso=chave,
            status_externo=status,
            raw_resumido=_safe_json(data),
        )

    def _montar_payload_nfce(self, nota):
        venda = nota.venda
        config = self.configuracao
        empresa = venda.empresa
        items = []
        for item in venda.itens:
            produto = item.produto
            valor_total = _to_decimal(item.valor_total)
            items.append({
                "numero_item": str(len(items) + 1),
                "codigo_produto": str(item.produto_id),
                "descricao": produto.nome if produto else f"Produto {item.produto_id}",
                "cfop": "5102",
                "unidade_comercial": "UN",
                "quantidade_comercial": float(item.quantidade),
                "valor_unitario_comercial": float(_to_decimal(item.valor_unitario)),
                "valor_total": float(valor_total),
                "ncm": ((produto.ncm or "") if produto else "").replace(".", ""),
                "icms_origem": "0",
                "icms_situacao_tributaria": "102" if config.regime_tributario == RegimeTributarioFiscal.SIMPLES_NACIONAL else "00",
            })

        formas_pagamento = []
        for pagamento in venda.pagamentos:
            formas_pagamento.append({
                "forma_pagamento": "99",
                "valor_pagamento": float(_to_decimal(pagamento.valor)),
            })

        payload = {
            "cnpj_emitente": _only_digits(config.focus_cnpj_emitente or getattr(empresa, "cnpj", "")),
            "data_emissao": TimeService.now_utc_naive().isoformat(),
            "indicador_inscricao_estadual_destinatario": "9",
            "modalidade_frete": "9",
            "local_destino": "1",
            "presenca_comprador": "1",
            "natureza_operacao": "VENDA AO CONSUMIDOR",
            "items": items,
            "formas_pagamento": formas_pagamento,
            "numero": str(nota.numero) if nota.numero else None,
            "serie": str(nota.serie) if nota.serie else str(config.serie_nfce or 1),
        }
        if venda.cliente:
            documento = _only_digits(getattr(venda.cliente, "documento", ""))
            payload["nome_destinatario"] = venda.cliente.nome
            if documento:
                payload["cpf_destinatario" if len(documento) <= 11 else "cnpj_destinatario"] = documento
        return {key: value for key, value in payload.items() if value not in (None, "")}

    def _request(self, method, path, payload):
        token = self._token()
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        auth = base64.b64encode(f"{token}:".encode("utf-8")).decode("ascii")
        req = request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Basic {auth}",
                "User-Agent": "OceanBlue-PDV/1.0",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise FiscalCommunicationError(f"Focus NFe HTTP {exc.code}: {_extract_error_message(raw)}") from exc
        except error.URLError as exc:
            raise FiscalCommunicationError(f"Falha de comunicacao com Focus NFe: {exc.reason}") from exc

    def _token(self):
        encrypted = (
            self.configuracao.focus_token_homologacao
            if self.configuracao.ambiente == AmbienteFiscal.HOMOLOGACAO
            else self.configuracao.focus_token_producao
        )
        token = FieldCrypto.decrypt(encrypted)
        if not token:
            raise ValueError("Token Focus NFe nao configurado para o ambiente da empresa.")
        return token

    def _salvar_url(self, nota, url, suffix):
        if not url:
            return None
        base_dir = _storage_base() / "tenants" / str(nota.tenant_id) / nota.ambiente.value.lower() / "fiscal" / "nfce" / TimeService.now_utc_naive().strftime("%Y/%m")
        base_dir.mkdir(parents=True, exist_ok=True)
        path = base_dir / f"nfce_{nota.serie}_{nota.numero}_{suffix}"
        try:
            with request.urlopen(url, timeout=self.timeout) as response:
                path.write_bytes(response.read())
            return str(path)
        except Exception:
            return None


class MockIntegradorFiscalProvider(FiscalProvider):
    provider_codigo = "mock_integrador_nfce"

    def transmitir_nfce(self, nota, xml_path, idempotency_key):
        xml = Path(xml_path).read_text(encoding="utf-8")
        if "REJEITAR" in (nota.mensagem_retorno or "").upper():
            return FiscalProviderResult(
                success=False,
                provider_codigo=self.provider_codigo,
                codigo_retorno="999",
                mensagem="NFC-e rejeitada pelo integrador fiscal de homologacao.",
                raw_resumido="mock fiscal: rejeicao homologada",
            )

        digest = hashlib.sha1(idempotency_key.encode("utf-8")).hexdigest().upper()
        protocolo = f"135{digest[:12]}"
        recibo = f"REC{digest[12:24]}"
        base_dir = _storage_base() / "tenants" / str(nota.tenant_id) / "fiscal" / "nfce" / nota.ambiente.value.lower() / TimeService.now_utc_naive().strftime("%Y/%m")
        base_dir.mkdir(parents=True, exist_ok=True)
        stem = f"nfce_{nota.serie}_{nota.numero}_{nota.chave_acesso}"
        xml_assinado_path = base_dir / f"{stem}-assinado.xml"
        xml_autorizado_path = base_dir / f"{stem}-autorizado.xml"
        danfe_path = base_dir / f"{stem}-danfe.html"
        xml_assinado_path.write_text(xml.replace("<NFCe", "<NFCe assinaturaMock=\"true\"", 1), encoding="utf-8")
        xml_autorizado_path.write_text(
            xml.replace(
                "</NFCe>",
                f"<autorizacaoMock><nProt>{protocolo}</nProt><xMotivo>Autorizado em homologacao mock</xMotivo></autorizacaoMock></NFCe>",
            ),
            encoding="utf-8",
        )
        danfe_path.write_text(
            f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>DANFE NFC-e {nota.numero}</title></head>
<body>
<h1>DANFE NFC-e homologacao</h1>
<p>Serie {nota.serie} / Numero {nota.numero}</p>
<p>Chave: {nota.chave_acesso}</p>
<p>Protocolo homologacao mock: {protocolo}</p>
<p>Este DANFE e gerado para homologacao interna e deve ser substituido/validado pelo integrador fiscal real antes de producao.</p>
</body>
</html>
""",
            encoding="utf-8",
        )
        return FiscalProviderResult(
            success=True,
            provider_codigo=self.provider_codigo,
            protocolo=protocolo,
            recibo=recibo,
            codigo_retorno="100",
            mensagem="NFC-e autorizada em homologacao pelo integrador fiscal mock.",
            xml_assinado_path=str(xml_assinado_path),
            xml_autorizado_path=str(xml_autorizado_path),
            danfe_path=str(danfe_path),
            raw_resumido="mock fiscal: autorizado homologacao",
        )


def get_fiscal_provider(_configuracao=None):
    if (
        _configuracao
        and getattr(_configuracao, "integrador_provider", None) == "focus_nfe"
        and (
            getattr(_configuracao, "focus_token_homologacao", None)
            or getattr(_configuracao, "focus_token_producao", None)
        )
    ):
        return FocusNFeProvider(_configuracao)
    return MockIntegradorFiscalProvider()


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
    return str(data.get("mensagem") or data.get("message") or data.get("errors") or data)[:500]
