import json
import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib import error, request

from flask import render_template

from app.models.db import CanalMensagemCliente
from app.security.field_crypto import FieldCrypto
from app.security.outbound import NoRedirect, validate_host, validate_webhook


class ComunicacaoService:

    @staticmethod
    def enviar(configuracao, canal, destinatario, assunto, conteudo, cliente=None, html_conteudo=None):
        canal_enum = ComunicacaoService._to_canal(canal)
        destino = (destinatario or "").strip()
        if not destino:
            raise ValueError("Destino da mensagem nao informado.")

        if canal_enum == CanalMensagemCliente.EMAIL:
            return ComunicacaoService._enviar_email(
                configuracao=configuracao,
                destinatario=destino,
                assunto=assunto,
                conteudo=conteudo,
                html_conteudo=html_conteudo,
                cliente=cliente,
            )

        if canal_enum == CanalMensagemCliente.WHATSAPP:
            return ComunicacaoService._enviar_webhook(
                configuracao=configuracao,
                canal=canal_enum,
                destinatario=destino,
                assunto=assunto,
                conteudo=conteudo,
                remetente=configuracao.whatsapp_remetente,
                endpoint=configuracao.whatsapp_api_url,
                token=FieldCrypto.decrypt(configuracao.whatsapp_token),
                cliente=cliente,
            )

        return ComunicacaoService._enviar_webhook(
            configuracao=configuracao,
            canal=canal_enum,
            destinatario=destino,
            assunto=assunto,
            conteudo=conteudo,
            remetente=configuracao.sms_remetente,
            endpoint=configuracao.sms_api_url,
            token=FieldCrypto.decrypt(configuracao.sms_token),
            cliente=cliente,
        )

    @staticmethod
    def _enviar_email(configuracao, destinatario, assunto, conteudo, html_conteudo=None, cliente=None):
        if not configuracao.email_habilitado:
            raise ValueError("Canal de email desabilitado para esta empresa.")

        if not configuracao.smtp_host:
            raise ValueError("Host SMTP nao configurado.")
        if not configuracao.email_remetente:
            raise ValueError("Email remetente nao configurado.")
        if not configuracao.smtp_ssl and not configuracao.smtp_tls:
            raise PermissionError("O envio SMTP exige TLS.")
        validate_host(configuracao.smtp_host, int(configuracao.smtp_port or 587))

        mensagem = EmailMessage()
        remetente_nome = (configuracao.email_remetente_nome or "").strip()
        if remetente_nome:
            mensagem["From"] = f"{remetente_nome} <{configuracao.email_remetente}>"
        else:
            mensagem["From"] = configuracao.email_remetente
        mensagem["To"] = destinatario
        mensagem["Subject"] = (assunto or "Mensagem do sistema").strip() or "Mensagem do sistema"
        mensagem.set_content(conteudo or "")
        mensagem.add_alternative(
            html_conteudo or ComunicacaoService._renderizar_email_generico_html(configuracao, destinatario, assunto, conteudo, cliente=cliente),
            subtype="html",
        )

        timeout = max(int(configuracao.request_timeout_segundos or 15), 1)
        context = ssl.create_default_context()

        try:
            if configuracao.smtp_ssl:
                with smtplib.SMTP_SSL(
                    configuracao.smtp_host,
                    int(configuracao.smtp_port or 465),
                    timeout=timeout,
                    context=context,
                ) as server:
                    ComunicacaoService._autenticar_smtp(server, configuracao)
                    server.send_message(mensagem)
            else:
                with smtplib.SMTP(
                    configuracao.smtp_host,
                    int(configuracao.smtp_port or 587),
                    timeout=timeout,
                ) as server:
                    server.ehlo()
                    if configuracao.smtp_tls:
                        server.starttls(context=context)
                        server.ehlo()
                    ComunicacaoService._autenticar_smtp(server, configuracao)
                    server.send_message(mensagem)
        except smtplib.SMTPAuthenticationError as exc:
            raise ValueError(
                ComunicacaoService._formatar_erro_autenticacao_smtp(configuracao, exc)
            ) from exc

        return {
            "canal": CanalMensagemCliente.EMAIL.value,
            "destinatario": destinatario,
            "status": "ENVIADO",
            "resposta": "Email encaminhado via SMTP.",
        }

    @staticmethod
    def _autenticar_smtp(server, configuracao):
        usuario = (configuracao.smtp_usuario or "").strip()
        senha = ComunicacaoService._normalizar_senha_smtp(configuracao)
        if usuario:
            server.login(usuario, senha)

    @staticmethod
    def _normalizar_senha_smtp(configuracao):
        senha = FieldCrypto.decrypt(configuracao.smtp_senha) or ""
        host = (configuracao.smtp_host or "").strip().lower()

        if host == "smtp.gmail.com" and re.fullmatch(r"[A-Za-z0-9]{4}( [A-Za-z0-9]{4}){3}", senha.strip()):
            return senha.replace(" ", "")

        return senha

    @staticmethod
    def _formatar_erro_autenticacao_smtp(configuracao, exc):
        host = (configuracao.smtp_host or "").strip().lower()

        if host == "smtp.gmail.com":
            return (
                "Falha de autenticacao no Gmail SMTP. "
                "Use uma senha de app do Google com a verificacao em duas etapas ativa. "
                "Se a senha foi copiada no formato 'xxxx xxxx xxxx xxxx', remova os espacos. "
            ).strip()

        return "Falha de autenticacao SMTP. Confira as credenciais configuradas."

    @staticmethod
    def _renderizar_email_generico_html(configuracao, destinatario, assunto, conteudo, cliente=None):
        nome_cliente = (getattr(cliente, "nome", None) or "").strip()
        if not nome_cliente and "@" in destinatario:
            nome_cliente = destinatario.split("@", 1)[0].replace(".", " ").replace("_", " ").strip().title()
        saudacao = f"Ola {nome_cliente}," if nome_cliente else "Ola,"
        empresa_nome = (configuracao.email_remetente_nome or "").strip() or "sua empresa"
        titulo = (assunto or "Mensagem do sistema").strip() or "Mensagem do sistema"
        subtitulo = f"Comunicacao enviada por {empresa_nome} usando o ambiente OceanBlue."

        return render_template(
            "emails/mensagem_cliente.html",
            preheader=titulo,
            badge="Comunicacao",
            email_title=titulo,
            email_subtitle=subtitulo,
            saudacao=saudacao,
            conteudo=conteudo or "",
            footer_note=f"Mensagem enviada por {empresa_nome} via OceanBlue.",
        )

    @staticmethod
    def _enviar_webhook(configuracao, canal, destinatario, assunto, conteudo, remetente, endpoint, token, cliente=None):
        flag_habilitado = (
            configuracao.whatsapp_habilitado
            if canal == CanalMensagemCliente.WHATSAPP
            else configuracao.sms_habilitado
        )
        if not flag_habilitado:
            raise ValueError(f"Canal de {canal.value.lower()} desabilitado para esta empresa.")

        if not endpoint:
            raise ValueError(f"Endpoint de {canal.value.lower()} nao configurado.")

        payload = {
            "channel": canal.value.lower(),
            "to": destinatario,
            "subject": (assunto or "").strip() or None,
            "message": conteudo or "",
            "sender": (remetente or "").strip() or None,
            "customer": {
                "nome": getattr(cliente, "nome", None),
                "documento": getattr(cliente, "documento", None),
                "email": getattr(cliente, "email", None),
                "telefone": getattr(cliente, "telefone", None),
                "whatsapp": getattr(cliente, "whatsapp", None),
            },
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        validate_webhook(endpoint)
        requisicao = request.Request(endpoint, data=body, headers=headers, method="POST")
        timeout = max(int(configuracao.request_timeout_segundos or 15), 1)

        try:
            opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
            with opener.open(requisicao, timeout=timeout) as response:
                resposta = response.read().decode("utf-8", errors="ignore")
                return {
                    "canal": canal.value,
                    "destinatario": destinatario,
                    "status": "ENVIADO",
                    "resposta": resposta or f"Mensagem enviada via webhook de {canal.value.lower()}.",
                }
        except error.HTTPError as exc:
            raise ValueError(
                f"Falha ao enviar {canal.value.lower()}: HTTP {exc.code}."
            ) from None
        except error.URLError as exc:
            raise ValueError(f"Falha ao conectar ao servidor de {canal.value.lower()}.") from None

    @staticmethod
    def _to_canal(value):
        if isinstance(value, CanalMensagemCliente):
            return value

        try:
            return CanalMensagemCliente[(value or "").strip().upper()]
        except KeyError as exc:
            raise ValueError("Canal de comunicacao invalido.") from exc
