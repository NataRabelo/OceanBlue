from datetime import timedelta
import hashlib
import json

from flask import current_app

from app.extensions import db
from app.models.db import Cliente, MensagemCliente, StatusMensagemCliente, CanalMensagemCliente
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.financeiro_ciclo_service import audit
from app.services.time_service import TimeService
from app.services.transaction_service import atomic_operation


class GatewayRecusado(Exception):
    pass


class GatewayBloqueado:
    def enviar(self, mensagem):
        raise GatewayRecusado("Integracoes externas bloqueadas.")


class GatewaySimulado:
    def __init__(self, resultado="sucesso"):
        self.resultado = resultado
        self.aceites = set()

    def enviar(self, mensagem):
        if self.resultado == "recusa":
            raise GatewayRecusado("Recusa simulada.")
        if self.resultado == "timeout":
            raise TimeoutError("Resultado simulado incerto.")
        self.aceites.add(mensagem.id)
        return "Aceite simulado"


class MensagemFilaService:
    @staticmethod
    @atomic_operation
    def enfileirar(cliente_id, empresa_id, canal, assunto, conteudo, chave, tenant_id, funcionario_id=None):
        from app.services.cliente_service import ClienteService
        if not isinstance(chave, str) or not 1 <= len(chave) <= 128:
            raise ValueError("Informe chave de idempotencia de ate 128 caracteres.")
        cliente = Cliente.query.filter_by(id=cliente_id, tenant_id=tenant_id).first()
        if not cliente or not cliente.ativo or cliente.anonimizado_em:
            raise ValueError("Cliente indisponivel.")
        canal = ClienteService._to_canal(canal)
        if canal == CanalMensagemCliente.WHATSAPP:
            raise ValueError("WhatsApp desativado neste escopo.")
        ClienteService._validar_opt_in(cliente, canal)
        destino = ClienteService._obter_destinatario_cliente(cliente, canal)
        if not isinstance(conteudo, str) or not 1 <= len(conteudo.strip()) <= 10000 or len(assunto or "") > 160:
            raise ValueError("Conteudo ou assunto invalido.")
        digest = hashlib.sha256(json.dumps([canal.value, assunto, conteudo, destino], ensure_ascii=True).encode()).hexdigest()
        previous = MensagemCliente.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id, cliente_id=cliente_id, chave=chave).first()
        if previous:
            if previous.payload_hash != digest:
                raise ValueError("Chave de mensagem reutilizada com outros dados.")
            return ClienteService.serializar_mensagem(previous)
        now = TimeService.now_utc_naive()
        count = MensagemCliente.query.filter(MensagemCliente.tenant_id == tenant_id,
            MensagemCliente.empresa_id == empresa_id, MensagemCliente.criado_em >= now - timedelta(days=1)).count()
        if count >= 1000:
            raise ValueError("Limite de 1000 mensagens por empresa em 24 horas atingido.")
        record = MensagemCliente(tenant_id=tenant_id, empresa_id=empresa_id, cliente_id=cliente_id,
            funcionario_id=funcionario_id, canal=canal, destinatario=destino, assunto=assunto,
            conteudo=conteudo, chave=chave, payload_hash=digest, estado="PENDENTE", tentativas=0)
        db.session.add(record)
        db.session.flush()
        audit("MENSAGEM_ENFILEIRADA", record, funcionario_id, {"chave": chave})
        return ClienteService.serializar_mensagem(record)

    @staticmethod
    def processar(tenant_id, escopo, funcionario_id=None, limite=100, gateway=None):
        from app.services.money_service import positive_integer
        limit = min(positive_integer(limite, "Limite"), 100)
        query = MensagemCliente.query.filter_by(tenant_id=tenant_id).filter(MensagemCliente.estado.in_(["PENDENTE", "FALHOU"]))
        query = query.filter(db.or_(MensagemCliente.proxima_tentativa.is_(None), MensagemCliente.proxima_tentativa <= TimeService.now_utc_naive()))
        companies = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        if companies is not None:
            query = query.filter(MensagemCliente.empresa_id.in_(companies))
        ids = [record.id for record in query.order_by(MensagemCliente.id).limit(limit).all()]
        db.session.rollback()
        return [MensagemFilaService.entregar(record_id, tenant_id, escopo, funcionario_id, gateway) for record_id in ids]

    @staticmethod
    def entregar(mensagem_id, tenant_id, escopo, funcionario_id=None, gateway=None):
        from app.services.cliente_service import ClienteService
        if gateway is not None and not current_app.testing:
            raise PermissionError("Simulador permitido somente em testes isolados.")
        transport = gateway or GatewayBloqueado()
        try:
            db.session.execute(db.text("SELECT pg_advisory_xact_lock(7202, :tenant)"), {"tenant": tenant_id})
            record = MensagemCliente.query.filter_by(id=mensagem_id, tenant_id=tenant_id).populate_existing().with_for_update().first()
            if record is None:
                raise ValueError("Mensagem nao encontrada.")
            AcessoEmpresaService.validar_empresa(record.empresa_id, escopo)
            now = TimeService.now_utc_naive()
            if record.estado not in ("PENDENTE", "FALHOU") or (record.proxima_tentativa and now < record.proxima_tentativa):
                result = ClienteService.serializar_mensagem(record)
                db.session.rollback()
                return result
            cliente = Cliente.query.filter_by(id=record.cliente_id, tenant_id=tenant_id).one()
            try:
                ClienteService._validar_opt_in(cliente, record.canal)
                if not cliente.ativo or cliente.anonimizado_em or ClienteService._obter_destinatario_cliente(cliente, record.canal) != record.destinatario:
                    raise ValueError("Contato alterado ou cliente inativo.")
            except ValueError:
                record.estado = "CANCELADO"
                record.erro = "Consentimento ou contato indisponivel."
                db.session.commit()
                return ClienteService.serializar_mensagem(record)
            record.estado = "INCERTO"
            record.tentativas += 1
            record.erro = "Envio sem confirmacao; exige conciliacao."
            audit("MENSAGEM_TENTATIVA", record, funcionario_id, {"tentativa": record.tentativas})
            db.session.commit()
            db.session.execute(db.text("SELECT pg_advisory_xact_lock(7202, :tenant)"), {"tenant": tenant_id})
            db.session.expire_all()
            if funcionario_id is not None:
                escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
                if not AcessoEmpresaService.possui_permissao(escopo, "enviar_mensagem_cliente"):
                    raise PermissionError("Permissao de envio revogada.")
            record = MensagemCliente.query.filter_by(id=mensagem_id, tenant_id=tenant_id).populate_existing().with_for_update().one()
            cliente = Cliente.query.filter_by(id=record.cliente_id, tenant_id=tenant_id).populate_existing().one()
            AcessoEmpresaService.validar_empresa(record.empresa_id, escopo)
            try:
                ClienteService._validar_opt_in(cliente, record.canal)
                if not cliente.ativo or cliente.anonimizado_em or ClienteService._obter_destinatario_cliente(cliente, record.canal) != record.destinatario:
                    raise ValueError("Contato alterado ou cliente inativo.")
            except ValueError:
                record.estado = "CANCELADO"
                record.erro = "Consentimento ou contato indisponivel."
                db.session.commit()
                return ClienteService.serializar_mensagem(record)
            try:
                transport.enviar(record)
                record.estado = "ENVIADO"
                record.status = StatusMensagemCliente.ENVIADO
                record.enviado_em = TimeService.now_utc_naive()
                record.erro = None
                record.resposta_integracao = "Aceite confirmado pelo adaptador."
            except GatewayRecusado:
                record.estado = "ESGOTADO" if record.tentativas >= 5 else "FALHOU"
                record.status = StatusMensagemCliente.ERRO
                record.erro = "Entrega recusada antes do aceite."
                record.proxima_tentativa = now + timedelta(seconds=60 * 2 ** (record.tentativas - 1))
            except Exception:
                record.estado = "INCERTO"
                record.status = StatusMensagemCliente.ERRO
            db.session.commit()
            return ClienteService.serializar_mensagem(record)
        except Exception:
            db.session.rollback()
            raise
