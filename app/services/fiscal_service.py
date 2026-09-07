import hashlib
import os
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from flask import current_app

from app.models.db import (
    AmbienteFiscal,
    ConfiguracaoFiscalEmpresa,
    NotaFiscalVenda,
    RegimeTributarioFiscal,
    EventoFiscalNota,
    StatusOficialNotaFiscal,
    StatusNotaFiscal,
    StatusVenda,
)
from app.security.field_crypto import FieldCrypto
from app.repositorys.fiscal_repository import FiscalRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.fiscal_provider import get_fiscal_provider
from app.services.time_service import TimeService


class FiscalService:
    REQUIRED_CONFIG_FIELDS = (
        ("inscricao_estadual", "Inscricao estadual"),
        ("uf", "UF"),
        ("municipio_nome", "Municipio"),
        ("municipio_codigo_ibge", "Codigo IBGE do municipio"),
        ("cep", "CEP"),
        ("logradouro", "Logradouro"),
        ("numero", "Numero"),
        ("bairro", "Bairro"),
        ("certificado_caminho", "Caminho do certificado"),
        ("certificado_senha_env", "Variavel de ambiente da senha do certificado"),
        ("csc_id", "ID do CSC"),
        ("csc_token", "Token CSC"),
    )

    @staticmethod
    def listar_auxiliares(tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        empresas = FiscalRepository.listar_empresas(tenant_id, empresa_ids=empresa_ids)

        return {
            "empresas": [
                {
                    "id": empresa.id,
                    "nome": empresa.nome_fantasia,
                    "configurada": bool(empresa.configuracao_fiscal),
                    "ambiente": (
                        getattr(empresa.configuracao_fiscal.ambiente, "value", AmbienteFiscal.HOMOLOGACAO.value)
                        if empresa.configuracao_fiscal
                        else AmbienteFiscal.HOMOLOGACAO.value
                    ),
                }
                for empresa in empresas
            ],
            "ambientes": [item.value for item in AmbienteFiscal],
            "regimes_tributarios": [item.value for item in RegimeTributarioFiscal],
        }

    @staticmethod
    def obter_configuracao(empresa_id, tenant_id, escopo):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        empresa = FiscalRepository.buscar_empresa(empresa_id, tenant_id)
        if not empresa:
            raise ValueError("Empresa nao encontrada.")

        configuracao = FiscalRepository.buscar_configuracao_por_empresa(empresa_id, tenant_id)
        return FiscalService._serializar_configuracao(
            configuracao or FiscalService._build_default_config(empresa_id, tenant_id),
            empresa=empresa,
        )

    @staticmethod
    def atualizar_configuracao(empresa_id, data, tenant_id, escopo):
        try:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
            empresa = FiscalRepository.buscar_empresa(empresa_id, tenant_id)
            if not empresa:
                raise ValueError("Empresa nao encontrada.")

            configuracao = FiscalRepository.buscar_configuracao_por_empresa(empresa_id, tenant_id)
            if not configuracao:
                configuracao = ConfiguracaoFiscalEmpresa(
                    tenant_id=tenant_id,
                    empresa_id=empresa_id,
                )
                FiscalRepository.adicionar(configuracao)

            configuracao.ambiente = FiscalService._to_ambiente(data.get("ambiente"))
            configuracao.regime_tributario = FiscalService._to_regime(data.get("regime_tributario"))
            configuracao.serie_nfce = FiscalService._to_positive_int(data.get("serie_nfce"), "serie NFC-e", default=1)
            configuracao.proximo_numero_nfce = FiscalService._to_positive_int(
                data.get("proximo_numero_nfce"),
                "proximo numero NFC-e",
                default=1,
            )
            configuracao.inscricao_estadual = FiscalService._optional_text(data.get("inscricao_estadual"), max_length=30)
            configuracao.inscricao_municipal = FiscalService._optional_text(data.get("inscricao_municipal"), max_length=30)
            configuracao.cnae = FiscalService._optional_text(data.get("cnae"), max_length=20)
            configuracao.uf = FiscalService._optional_text(data.get("uf"), max_length=2, uppercase=True)
            configuracao.municipio_nome = FiscalService._optional_text(data.get("municipio_nome"), max_length=120)
            configuracao.municipio_codigo_ibge = FiscalService._only_digits(data.get("municipio_codigo_ibge"), max_length=7)
            configuracao.cep = FiscalService._only_digits(data.get("cep"), max_length=8)
            configuracao.logradouro = FiscalService._optional_text(data.get("logradouro"), max_length=180)
            configuracao.numero = FiscalService._optional_text(data.get("numero"), max_length=20)
            configuracao.complemento = FiscalService._optional_text(data.get("complemento"), max_length=120)
            configuracao.bairro = FiscalService._optional_text(data.get("bairro"), max_length=120)
            configuracao.certificado_caminho = FiscalService._optional_text(data.get("certificado_caminho"), max_length=255)
            configuracao.certificado_senha_env = FiscalService._optional_text(
                data.get("certificado_senha_env"),
                max_length=120,
                uppercase=True,
            )
            configuracao.csc_id = FiscalService._optional_text(data.get("csc_id"), max_length=20)
            configuracao.integrador_provider = FiscalService._optional_text(data.get("integrador_provider"), max_length=80) or "mock_nfce"
            configuracao.integrador_credencial_env = FiscalService._optional_text(
                data.get("integrador_credencial_env"),
                max_length=120,
                uppercase=True,
            )
            if "focus_token_homologacao" in data and data.get("focus_token_homologacao"):
                configuracao.focus_token_homologacao = FieldCrypto.encrypt(data.get("focus_token_homologacao"))
            if "focus_token_producao" in data and data.get("focus_token_producao"):
                configuracao.focus_token_producao = FieldCrypto.encrypt(data.get("focus_token_producao"))
            configuracao.focus_cnpj_emitente = FiscalService._only_digits(data.get("focus_cnpj_emitente"), max_length=14)
            configuracao.focus_status_configuracao = (
                "CONFIGURADO"
                if configuracao.integrador_provider == "focus_nfe"
                and (
                    configuracao.focus_token_homologacao
                    if configuracao.ambiente == AmbienteFiscal.HOMOLOGACAO
                    else configuracao.focus_token_producao
                )
                else "PENDENTE"
            )
            if "csc_token" in data:
                configuracao.csc_token = FieldCrypto.encrypt(
                    FiscalService._optional_text(data.get("csc_token"), max_length=255)
                )
            configuracao.contingencia_ativa = FiscalService._to_bool(data.get("contingencia_ativa"), default=False)

            FiscalService._atualizar_status_certificado(configuracao)
            FiscalRepository.salvar()

            configuracao = FiscalRepository.buscar_configuracao_por_empresa(empresa_id, tenant_id)
            return FiscalService._serializar_configuracao(configuracao, empresa=empresa)
        except Exception:
            FiscalRepository.rollback()
            raise

    @staticmethod
    def listar_notas(tenant_id, escopo, limite=50):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        notas = FiscalRepository.listar_notas(tenant_id, empresa_ids=empresa_ids, limite=limite)
        return [FiscalService._serializar_nota(nota) for nota in notas]

    @staticmethod
    def prevalidar_venda(venda_id, tenant_id, escopo):
        try:
            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            venda = FiscalRepository.buscar_venda(venda_id, tenant_id, empresa_ids=empresa_ids)
            if not venda:
                raise ValueError("Venda nao encontrada.")

            configuracao = FiscalRepository.buscar_configuracao_por_empresa(venda.empresa_id, tenant_id)
            nota = FiscalRepository.buscar_nota_por_venda(venda.id, tenant_id)
            if not nota:
                nota = NotaFiscalVenda(
                    tenant_id=tenant_id,
                    empresa_id=venda.empresa_id,
                    venda_id=venda.id,
                    configuracao_fiscal_id=configuracao.id if configuracao else None,
                    ambiente=configuracao.ambiente if configuracao else AmbienteFiscal.HOMOLOGACAO,
                    status=StatusNotaFiscal.PENDENTE,
                    status_oficial=StatusOficialNotaFiscal.NAO_ENVIADA,
                    modelo="NFC-e",
                )
                FiscalRepository.adicionar(nota)

            pendencias = FiscalService._validar_prontidao_venda(venda, configuracao)
            nota.configuracao_fiscal_id = configuracao.id if configuracao else None
            nota.ambiente = configuracao.ambiente if configuracao else AmbienteFiscal.HOMOLOGACAO
            nota.status = (
                StatusNotaFiscal.PRONTA_PARA_EMISSAO if not pendencias else StatusNotaFiscal.VALIDACAO_ERRO
            )
            nota.mensagem_retorno = "\n".join(pendencias) if pendencias else "Venda pronta para preparar XML fiscal interno."
            nota.enviado_em = TimeService.now_utc_naive()

            FiscalRepository.salvar()
            nota = FiscalRepository.buscar_nota_por_venda(venda.id, tenant_id)
            return {
                "venda_id": venda.id,
                "venda_numero": venda.numero_unico,
                "status": nota.status.value,
                "pendencias": pendencias,
                "nota": FiscalService._serializar_nota(nota),
            }
        except Exception:
            FiscalRepository.rollback()
            raise

    @staticmethod
    def emitir_nota_venda(venda_id, tenant_id, escopo):
        try:
            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            venda = FiscalRepository.buscar_venda(venda_id, tenant_id, empresa_ids=empresa_ids)
            if not venda:
                raise ValueError("Venda nao encontrada.")

            configuracao = FiscalRepository.buscar_configuracao_por_empresa(venda.empresa_id, tenant_id)
            pendencias = FiscalService._validar_prontidao_venda(venda, configuracao)
            nota = FiscalRepository.buscar_nota_por_venda(venda.id, tenant_id)
            if not nota:
                nota = NotaFiscalVenda(
                    tenant_id=tenant_id,
                    empresa_id=venda.empresa_id,
                    venda_id=venda.id,
                    status=StatusNotaFiscal.PENDENTE,
                    status_oficial=StatusOficialNotaFiscal.NAO_ENVIADA,
                    modelo="NFC-e",
                )
                FiscalRepository.adicionar(nota)
                FiscalRepository.flush()

            nota.configuracao_fiscal_id = configuracao.id if configuracao else None
            nota.ambiente = configuracao.ambiente if configuracao else AmbienteFiscal.HOMOLOGACAO

            if nota.status_oficial == StatusOficialNotaFiscal.AUTORIZADA:
                return FiscalService._serializar_nota(nota)

            if pendencias:
                nota.status = StatusNotaFiscal.VALIDACAO_ERRO
                nota.mensagem_retorno = "\n".join(pendencias)
                nota.enviado_em = TimeService.now_utc_naive()
                FiscalRepository.salvar()
                raise ValueError("A venda ainda possui pendencias fiscais: " + "; ".join(pendencias))

            nota.serie = int(configuracao.serie_nfce or 1)
            nota.numero = int(configuracao.proximo_numero_nfce or 1)
            nota.chave_acesso = FiscalService._gerar_chave_acesso(venda, configuracao, nota.numero, nota.serie)
            nota.recibo = FiscalService._gerar_recibo(nota.chave_acesso)
            nota.protocolo = FiscalService._gerar_protocolo(nota.chave_acesso)
            nota.xml_path = FiscalService._salvar_xml_nota(venda, configuracao, nota)
            nota.status = StatusNotaFiscal.XML_GERADO
            nota.status_oficial = StatusOficialNotaFiscal.NAO_ENVIADA
            nota.mensagem_retorno = (
                "XML NFC-e gerado internamente. Envio homologado ao integrador fiscal ainda pendente."
            )
            nota.enviado_em = TimeService.now_utc_naive()
            nota.emitida_em = TimeService.now_utc_naive()

            provider = get_fiscal_provider(configuracao)
            idempotency_key = nota.idempotency_key_envio or f"nfce:{tenant_id}:{nota.venda_id}:{nota.serie}:{nota.numero}"
            nota.idempotency_key_envio = idempotency_key
            nota.referencia_externa = idempotency_key
            nota.provider_codigo = provider.provider_codigo
            nota.status = StatusNotaFiscal.ENVIADA_AUTORIZACAO
            nota.status_oficial = StatusOficialNotaFiscal.EM_PROCESSAMENTO
            resultado = provider.transmitir_nfce(nota, nota.xml_path, idempotency_key)
            FiscalService._registrar_evento_fiscal(nota, resultado, f"envio:{idempotency_key}")

            nota.codigo_retorno = resultado.codigo_retorno
            nota.mensagem_retorno = resultado.mensagem
            if resultado.success:
                nota.status = StatusNotaFiscal.EMITIDA
                nota.status_oficial = StatusOficialNotaFiscal.AUTORIZADA
                nota.protocolo_oficial = resultado.protocolo
                nota.protocolo = resultado.protocolo
                nota.recibo = resultado.recibo
                nota.chave_acesso = resultado.chave_acesso or nota.chave_acesso
                nota.xml_assinado_path = resultado.xml_assinado_path
                nota.xml_autorizado_path = resultado.xml_autorizado_path
                nota.danfe_path = resultado.danfe_path
                nota.xml_url = resultado.xml_url
                nota.danfe_url = resultado.danfe_url
                nota.autorizada_em = TimeService.now_utc_naive()
            else:
                nota.status = StatusNotaFiscal.REJEITADA
                nota.status_oficial = StatusOficialNotaFiscal.REJEITADA

            configuracao.proximo_numero_nfce = nota.numero + 1

            FiscalRepository.salvar()
            nota = FiscalRepository.buscar_nota_por_venda(venda.id, tenant_id)
            return FiscalService._serializar_nota(nota)
        except Exception:
            FiscalRepository.rollback()
            raise

    @staticmethod
    def consultar_nota_venda(nota_id, tenant_id, escopo):
        try:
            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            nota = FiscalRepository.buscar_nota_por_id(nota_id, tenant_id, empresa_ids=empresa_ids)
            if not nota:
                raise ValueError("Nota fiscal nao encontrada.")
            provider = get_fiscal_provider(nota.configuracao_fiscal)
            resultado = provider.consultar_nfce(nota)
            FiscalService._aplicar_resultado_provider(nota, resultado)
            FiscalService._registrar_evento_fiscal(nota, resultado, f"consulta:{nota.referencia_externa or nota.idempotency_key_envio}")
            FiscalRepository.salvar()
            return FiscalService._serializar_nota(nota)
        except Exception:
            FiscalRepository.rollback()
            raise

    @staticmethod
    def cancelar_nota_venda(nota_id, justificativa, tenant_id, escopo):
        try:
            empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
            nota = FiscalRepository.buscar_nota_por_id(nota_id, tenant_id, empresa_ids=empresa_ids)
            if not nota:
                raise ValueError("Nota fiscal nao encontrada.")
            if nota.status_oficial != StatusOficialNotaFiscal.AUTORIZADA:
                raise ValueError("Somente NFC-e autorizada pode ser cancelada.")
            if nota.cancelada_em:
                return FiscalService._serializar_nota(nota)
            provider = get_fiscal_provider(nota.configuracao_fiscal)
            resultado = provider.cancelar_nfce(nota, justificativa)
            FiscalService._aplicar_resultado_provider(nota, resultado, cancelamento=True)
            FiscalService._registrar_evento_fiscal(nota, resultado, f"cancelamento:{nota.referencia_externa or nota.idempotency_key_envio}")
            FiscalRepository.salvar()
            return FiscalService._serializar_nota(nota)
        except Exception:
            FiscalRepository.rollback()
            raise

    @staticmethod
    def obter_xml_nota(nota_id, tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        nota = FiscalRepository.buscar_nota_por_id(nota_id, tenant_id, empresa_ids=empresa_ids)
        if not nota:
            raise ValueError("Nota fiscal nao encontrada.")
        if nota.status != StatusNotaFiscal.EMITIDA or not nota.xml_path:
            raise ValueError("A nota ainda nao possui XML interno gerado.")
        path = Path(nota.xml_path)
        if not path.exists():
            raise ValueError("Arquivo XML da nota nao encontrado.")
        return nota, path

    @staticmethod
    def obter_danfe_nota(nota_id, tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        nota = FiscalRepository.buscar_nota_por_id(nota_id, tenant_id, empresa_ids=empresa_ids)
        if not nota:
            raise ValueError("Nota fiscal nao encontrada.")
        if nota.status_oficial != StatusOficialNotaFiscal.AUTORIZADA or not nota.danfe_path:
            raise ValueError("A nota ainda nao possui DANFE NFC-e autorizado/homologado.")
        path = Path(nota.danfe_path)
        if not path.exists():
            raise ValueError("Arquivo DANFE da nota nao encontrado.")
        return nota, path

    @staticmethod
    def _validar_prontidao_venda(venda, configuracao):
        pendencias = []

        if venda.status != StatusVenda.FINALIZADA:
            pendencias.append("Somente vendas finalizadas podem seguir para preparacao fiscal.")

        if not configuracao:
            pendencias.append("A empresa nao possui configuracao fiscal cadastrada.")
            return pendencias

        for field_name, label in FiscalService.REQUIRED_CONFIG_FIELDS:
            if not getattr(configuracao, field_name, None):
                pendencias.append(f"{label} nao configurado.")

        certificado_ok, certificado_detalhe = FiscalService._validar_certificado(configuracao)
        if not certificado_ok:
            pendencias.append(certificado_detalhe)

        if not venda.itens:
            pendencias.append("A venda nao possui itens para preparacao fiscal.")
            return pendencias

        for item in venda.itens:
            produto = item.produto
            if not produto:
                pendencias.append(f"Item {item.id} sem produto vinculado.")
                continue
            if not produto.possui_ncm or not (produto.ncm or "").strip():
                pendencias.append(f"Produto '{produto.nome}' sem NCM fiscal configurado.")

        return pendencias

    @staticmethod
    def _serializar_configuracao(configuracao, empresa=None):
        certificado_ok, certificado_detalhe = FiscalService._validar_certificado(configuracao)
        pendencias = [
            mensagem
            for mensagem in FiscalService._validar_prontidao_configuracao(configuracao)
            if mensagem
        ]

        return {
            "empresa_id": configuracao.empresa_id,
            "empresa_nome": empresa.nome_fantasia if empresa else None,
            "ambiente": getattr(configuracao.ambiente, "value", AmbienteFiscal.HOMOLOGACAO.value),
            "regime_tributario": getattr(
                configuracao.regime_tributario,
                "value",
                RegimeTributarioFiscal.SIMPLES_NACIONAL.value,
            ),
            "serie_nfce": int(configuracao.serie_nfce or 1),
            "proximo_numero_nfce": int(configuracao.proximo_numero_nfce or 1),
            "inscricao_estadual": configuracao.inscricao_estadual or "",
            "inscricao_municipal": configuracao.inscricao_municipal or "",
            "cnae": configuracao.cnae or "",
            "uf": configuracao.uf or "",
            "municipio_nome": configuracao.municipio_nome or "",
            "municipio_codigo_ibge": configuracao.municipio_codigo_ibge or "",
            "cep": configuracao.cep or "",
            "logradouro": configuracao.logradouro or "",
            "numero": configuracao.numero or "",
            "complemento": configuracao.complemento or "",
            "bairro": configuracao.bairro or "",
            "certificado_caminho": configuracao.certificado_caminho or "",
            "certificado_senha_env": configuracao.certificado_senha_env or "",
            "csc_id": configuracao.csc_id or "",
            "csc_token": "",
            "csc_token_configurado": bool(configuracao.csc_token),
            "contingencia_ativa": bool(configuracao.contingencia_ativa),
            "integrador_provider": getattr(configuracao, "integrador_provider", None) or "mock_nfce",
            "integrador_credencial_env": getattr(configuracao, "integrador_credencial_env", None) or "",
            "focus_token_homologacao_configurado": bool(getattr(configuracao, "focus_token_homologacao", None)),
            "focus_token_producao_configurado": bool(getattr(configuracao, "focus_token_producao", None)),
            "focus_cnpj_emitente": getattr(configuracao, "focus_cnpj_emitente", None) or "",
            "focus_status_configuracao": getattr(configuracao, "focus_status_configuracao", None) or "PENDENTE",
            "focus_ultima_validacao_em": TimeService.serialize_utc_iso(getattr(configuracao, "focus_ultima_validacao_em", None)),
            "focus_ultima_validacao_status": getattr(configuracao, "focus_ultima_validacao_status", None),
            "focus_ultima_validacao_mensagem": getattr(configuracao, "focus_ultima_validacao_mensagem", None),
            "certificado_ok": certificado_ok,
            "certificado_detalhe": certificado_detalhe,
            "ultimo_teste_certificado_em": TimeService.serialize_utc_iso(configuracao.ultimo_teste_certificado_em),
            "ultimo_teste_certificado_status": configuracao.ultimo_teste_certificado_status,
            "ultimo_teste_certificado_detalhe": configuracao.ultimo_teste_certificado_detalhe,
            "pendencias": pendencias,
            "pronto_para_emissao": not pendencias,
        }

    @staticmethod
    def _serializar_nota(nota):
        return {
            "id": nota.id,
            "empresa_id": nota.empresa_id,
            "empresa_nome": nota.empresa.nome_fantasia if nota.empresa else None,
            "venda_id": nota.venda_id,
            "venda_numero": nota.venda.numero_unico if nota.venda else None,
            "ambiente": getattr(nota.ambiente, "value", AmbienteFiscal.HOMOLOGACAO.value),
            "status": getattr(nota.status, "value", StatusNotaFiscal.PENDENTE.value),
            "status_oficial": getattr(getattr(nota, "status_oficial", None), "value", StatusOficialNotaFiscal.NAO_ENVIADA.value),
            "modelo": getattr(nota, "modelo", None) or "NFC-e",
            "provider_codigo": getattr(nota, "provider_codigo", None),
            "referencia_externa": getattr(nota, "referencia_externa", None),
            "serie": nota.serie,
            "numero": nota.numero,
            "chave_acesso": nota.chave_acesso,
            "protocolo": nota.protocolo,
            "protocolo_oficial": getattr(nota, "protocolo_oficial", None),
            "recibo": nota.recibo,
            "xml_disponivel": bool(nota.xml_path),
            "xml_autorizado_disponivel": bool(getattr(nota, "xml_autorizado_path", None)),
            "danfe_disponivel": bool(getattr(nota, "danfe_path", None)),
            "xml_url": getattr(nota, "xml_url", None),
            "danfe_url": getattr(nota, "danfe_url", None),
            "codigo_retorno": getattr(nota, "codigo_retorno", None),
            "mensagem_retorno": nota.mensagem_retorno,
            "enviado_em": TimeService.serialize_utc_iso(nota.enviado_em),
            "emitida_em": TimeService.serialize_utc_iso(nota.emitida_em),
            "autorizada_em": TimeService.serialize_utc_iso(getattr(nota, "autorizada_em", None)),
            "cancelada_em": TimeService.serialize_utc_iso(nota.cancelada_em),
        }

    @staticmethod
    def _aplicar_resultado_provider(nota, resultado, cancelamento=False):
        nota.provider_codigo = resultado.provider_codigo
        nota.codigo_retorno = resultado.codigo_retorno
        nota.mensagem_retorno = resultado.mensagem
        nota.protocolo_oficial = resultado.protocolo or nota.protocolo_oficial
        nota.protocolo = resultado.protocolo or nota.protocolo
        nota.recibo = resultado.recibo or nota.recibo
        nota.chave_acesso = resultado.chave_acesso or nota.chave_acesso
        nota.xml_autorizado_path = resultado.xml_autorizado_path or nota.xml_autorizado_path
        nota.danfe_path = resultado.danfe_path or nota.danfe_path
        nota.xml_url = resultado.xml_url or getattr(nota, "xml_url", None)
        nota.danfe_url = resultado.danfe_url or getattr(nota, "danfe_url", None)
        if cancelamento and resultado.success:
            nota.status = StatusNotaFiscal.CANCELADA
            nota.status_oficial = StatusOficialNotaFiscal.CANCELADA
            nota.cancelada_em = TimeService.now_utc_naive()
        elif resultado.success:
            nota.status = StatusNotaFiscal.EMITIDA
            nota.status_oficial = StatusOficialNotaFiscal.AUTORIZADA
            nota.autorizada_em = nota.autorizada_em or TimeService.now_utc_naive()
        else:
            nota.status = StatusNotaFiscal.REJEITADA
            nota.status_oficial = StatusOficialNotaFiscal.REJEITADA

    @staticmethod
    def _registrar_evento_fiscal(nota, resultado, event_id):
        existente = EventoFiscalNota.query.filter_by(
            tenant_id=nota.tenant_id,
            provider_codigo=resultado.provider_codigo,
            event_id=event_id,
        ).first()
        if existente:
            return
        FiscalRepository.adicionar(EventoFiscalNota(
            tenant_id=nota.tenant_id,
            nota_id=nota.id,
            provider_codigo=resultado.provider_codigo,
            event_id=event_id,
            tipo_evento="AUTORIZACAO_NFCE",
            codigo_retorno=resultado.codigo_retorno,
            mensagem=resultado.mensagem,
            payload_resumido=resultado.raw_resumido,
        ))

    @staticmethod
    def _build_default_config(empresa_id, tenant_id):
        return ConfiguracaoFiscalEmpresa(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            ambiente=AmbienteFiscal.HOMOLOGACAO,
            regime_tributario=RegimeTributarioFiscal.SIMPLES_NACIONAL,
            serie_nfce=1,
            proximo_numero_nfce=1,
            contingencia_ativa=False,
        )

    @staticmethod
    def _validar_prontidao_configuracao(configuracao):
        pendencias = []
        for field_name, label in FiscalService.REQUIRED_CONFIG_FIELDS:
            if not getattr(configuracao, field_name, None):
                pendencias.append(f"{label} nao configurado.")

        certificado_ok, certificado_detalhe = FiscalService._validar_certificado(configuracao)
        if not certificado_ok:
            pendencias.append(certificado_detalhe)

        return pendencias

    @staticmethod
    def _atualizar_status_certificado(configuracao):
        certificado_ok, certificado_detalhe = FiscalService._validar_certificado(configuracao)
        configuracao.ultimo_teste_certificado_em = TimeService.now_utc_naive()
        configuracao.ultimo_teste_certificado_status = "VALIDO" if certificado_ok else "ERRO"
        configuracao.ultimo_teste_certificado_detalhe = certificado_detalhe

    @staticmethod
    def _validar_certificado(configuracao):
        caminho = (configuracao.certificado_caminho or "").strip()
        senha_env = (configuracao.certificado_senha_env or "").strip()

        if not caminho:
            return False, "Caminho do certificado digital nao configurado."
        if not senha_env:
            return False, "Informe a variavel de ambiente que contem a senha do certificado."

        extensao = os.path.splitext(caminho)[1].lower()
        if extensao not in {".pfx", ".p12"}:
            return False, "Utilize um certificado A1 no formato .pfx ou .p12."

        return True, "Configuracao declarada para simulacao; certificado real nao verificado nesta versao."

    @staticmethod
    def _salvar_xml_nota(venda, configuracao, nota):
        base_dir = Path(current_app.instance_path) / "fiscal" / f"tenant_{venda.tenant_id}" / f"empresa_{venda.empresa_id}"
        base_dir.mkdir(parents=True, exist_ok=True)
        filename = f"nfce_{nota.serie}_{nota.numero}_{nota.chave_acesso}.xml"
        path = base_dir / filename
        xml_content = FiscalService._montar_xml_nota(venda, configuracao, nota)
        path.write_text(xml_content, encoding="utf-8")
        return str(path)

    @staticmethod
    def _montar_xml_nota(venda, configuracao, nota):
        root = ET.Element("NFCe", versao="4.00", ambiente=getattr(nota.ambiente, "value", str(nota.ambiente)))
        inf = ET.SubElement(root, "infNFe", Id=f"NFe{nota.chave_acesso}", versao="4.00")

        ide = ET.SubElement(inf, "ide")
        FiscalService._xml_text(ide, "cUF", FiscalService._codigo_uf(configuracao.uf))
        FiscalService._xml_text(ide, "mod", "65")
        FiscalService._xml_text(ide, "serie", nota.serie)
        FiscalService._xml_text(ide, "nNF", nota.numero)
        FiscalService._xml_text(ide, "dhEmi", TimeService.serialize_utc_iso(nota.emitida_em or TimeService.now_utc_naive()))
        FiscalService._xml_text(ide, "tpAmb", "2" if nota.ambiente == AmbienteFiscal.HOMOLOGACAO else "1")
        FiscalService._xml_text(ide, "cNF", nota.chave_acesso[-9:-1])
        FiscalService._xml_text(ide, "natOp", "VENDA")

        emit = ET.SubElement(inf, "emit")
        FiscalService._xml_text(emit, "CNPJ", FiscalService._only_digits(getattr(venda.empresa, "cnpj", ""), max_length=14))
        FiscalService._xml_text(emit, "xNome", getattr(venda.empresa, "razao_social", None) or getattr(venda.empresa, "nome_fantasia", ""))
        FiscalService._xml_text(emit, "xFant", getattr(venda.empresa, "nome_fantasia", ""))
        FiscalService._xml_text(emit, "IE", configuracao.inscricao_estadual)

        ender = ET.SubElement(emit, "enderEmit")
        FiscalService._xml_text(ender, "xLgr", configuracao.logradouro)
        FiscalService._xml_text(ender, "nro", configuracao.numero)
        FiscalService._xml_text(ender, "xCpl", configuracao.complemento or "")
        FiscalService._xml_text(ender, "xBairro", configuracao.bairro)
        FiscalService._xml_text(ender, "cMun", configuracao.municipio_codigo_ibge)
        FiscalService._xml_text(ender, "xMun", configuracao.municipio_nome)
        FiscalService._xml_text(ender, "UF", configuracao.uf)
        FiscalService._xml_text(ender, "CEP", configuracao.cep)

        if venda.cliente:
            dest = ET.SubElement(inf, "dest")
            documento = FiscalService._only_digits(getattr(venda.cliente, "documento", ""))
            FiscalService._xml_text(dest, "CPF" if len(documento) <= 11 else "CNPJ", documento)
            FiscalService._xml_text(dest, "xNome", venda.cliente.nome)

        total_produtos = Decimal("0.00")
        for index, item in enumerate(venda.itens, start=1):
            produto = item.produto
            det = ET.SubElement(inf, "det", nItem=str(index))
            prod = ET.SubElement(det, "prod")
            valor_total = FiscalService._to_decimal(item.valor_total)
            total_produtos += valor_total
            FiscalService._xml_text(prod, "cProd", item.produto_id)
            FiscalService._xml_text(prod, "xProd", produto.nome if produto else f"Produto {item.produto_id}")
            FiscalService._xml_text(prod, "NCM", (produto.ncm or "").replace(".", "") if produto else "")
            FiscalService._xml_text(prod, "CFOP", "5102")
            FiscalService._xml_text(prod, "uCom", "UN")
            FiscalService._xml_text(prod, "qCom", int(item.quantidade))
            FiscalService._xml_text(prod, "vUnCom", FiscalService._money(item.valor_unitario))
            FiscalService._xml_text(prod, "vProd", FiscalService._money(valor_total))

            imposto = ET.SubElement(det, "imposto")
            icms = ET.SubElement(imposto, "ICMS")
            FiscalService._xml_text(icms, "orig", "0")
            FiscalService._xml_text(icms, "CSOSN" if configuracao.regime_tributario == RegimeTributarioFiscal.SIMPLES_NACIONAL else "CST", "102")

        total = ET.SubElement(inf, "total")
        icmstot = ET.SubElement(total, "ICMSTot")
        FiscalService._xml_text(icmstot, "vProd", FiscalService._money(total_produtos))
        FiscalService._xml_text(icmstot, "vDesc", FiscalService._money(venda.desconto))
        FiscalService._xml_text(icmstot, "vNF", FiscalService._money(venda.total))

        pag = ET.SubElement(inf, "pag")
        for pagamento in venda.pagamentos:
            det_pag = ET.SubElement(pag, "detPag")
            FiscalService._xml_text(det_pag, "tPag", "99")
            FiscalService._xml_text(det_pag, "xPag", pagamento.forma_pagamento.nome if pagamento.forma_pagamento else "Pagamento")
            FiscalService._xml_text(det_pag, "vPag", FiscalService._money(pagamento.valor))
        if FiscalService._to_decimal(venda.cashback_utilizado) > Decimal("0.00"):
            det_pag = ET.SubElement(pag, "detPag")
            FiscalService._xml_text(det_pag, "tPag", "99")
            FiscalService._xml_text(det_pag, "xPag", "Cashback")
            FiscalService._xml_text(det_pag, "vPag", FiscalService._money(venda.cashback_utilizado))

        prot = ET.SubElement(root, "protNFe")
        FiscalService._xml_text(prot, "chNFe", nota.chave_acesso)
        FiscalService._xml_text(prot, "nProt", nota.protocolo)
        FiscalService._xml_text(prot, "digVal", hashlib.sha1(nota.chave_acesso.encode("utf-8")).hexdigest())
        FiscalService._xml_text(prot, "xMotivo", "XML interno gerado sem autorizacao oficial SEFAZ")

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    @staticmethod
    def _gerar_chave_acesso(venda, configuracao, numero, serie):
        cuf = FiscalService._codigo_uf(configuracao.uf)
        aamm = TimeService.now_utc_naive().strftime("%y%m")
        cnpj = FiscalService._only_digits(getattr(venda.empresa, "cnpj", ""), max_length=14) or "0"
        cnpj = cnpj.zfill(14)
        modelo = "65"
        serie_formatada = str(int(serie)).zfill(3)
        numero_formatado = str(int(numero)).zfill(9)
        tipo_emissao = "1"
        codigo = hashlib.sha1(f"{venda.id}:{venda.numero_unico}:{numero}".encode("utf-8")).hexdigest()
        cnf = str(int(codigo[:8], 16))[-8:].zfill(8)
        base = f"{cuf}{aamm}{cnpj}{modelo}{serie_formatada}{numero_formatado}{tipo_emissao}{cnf}"
        return f"{base}{FiscalService._calcular_dv_chave(base)}"

    @staticmethod
    def _calcular_dv_chave(base):
        pesos = [2, 3, 4, 5, 6, 7, 8, 9]
        total = 0
        for index, char in enumerate(reversed(base)):
            total += int(char) * pesos[index % len(pesos)]
        resto = total % 11
        dv = 11 - resto
        return str(0 if dv >= 10 else dv)

    @staticmethod
    def _gerar_recibo(chave):
        return hashlib.sha1(f"recibo:{chave}".encode("utf-8")).hexdigest()[:15].upper()

    @staticmethod
    def _gerar_protocolo(chave):
        return hashlib.sha1(f"protocolo:{chave}".encode("utf-8")).hexdigest()[:15].upper()

    @staticmethod
    def _codigo_uf(uf):
        return {
            "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
            "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
            "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
            "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53",
        }.get((uf or "").upper(), "35")

    @staticmethod
    def _xml_text(parent, tag, value):
        child = ET.SubElement(parent, tag)
        child.text = "" if value is None else str(value)
        return child

    @staticmethod
    def _money(value):
        return f"{FiscalService._to_decimal(value):.2f}"

    @staticmethod
    def _to_decimal(value):
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.01"))
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))

    @staticmethod
    def _to_ambiente(value):
        raw_value = (value or "").strip().upper()
        if not raw_value:
            return AmbienteFiscal.HOMOLOGACAO

        try:
            return AmbienteFiscal[raw_value]
        except KeyError:
            raise ValueError("Ambiente fiscal invalido.")

    @staticmethod
    def _to_regime(value):
        raw_value = (value or "").strip().upper()
        if not raw_value:
            return RegimeTributarioFiscal.SIMPLES_NACIONAL

        try:
            return RegimeTributarioFiscal[raw_value]
        except KeyError:
            raise ValueError("Regime tributario invalido.")

    @staticmethod
    def _to_positive_int(value, field_name, default=1):
        if value in (None, ""):
            return int(default)

        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError(f"{field_name.capitalize()} invalido.")

        if parsed <= 0:
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")

        return parsed

    @staticmethod
    def _optional_text(value, max_length=None, uppercase=False):
        text = str(value or "").strip()
        if uppercase:
            text = text.upper()
        if max_length:
            text = text[:max_length]
        return text or None

    @staticmethod
    def _only_digits(value, max_length=None):
        digits = "".join(char for char in str(value or "") if char.isdigit())
        if max_length:
            digits = digits[:max_length]
        return digits or None

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "t", "sim", "yes", "on"}
