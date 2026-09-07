import json

from app.extensions import db
from app.models.db import Cliente, MensagemCliente, Venda, CreditoCashbackCliente, MovimentoCarteiraCliente, AuditLog, OperacaoIdempotente
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.audit_service import AuditService
from app.services.cliente_service import ClienteService
from app.services.financeiro_ciclo_service import motivo
from app.services.time_service import TimeService
from app.services.transaction_service import atomic_operation


class ClientePrivacidadeService:
    @staticmethod
    def obter(cliente_id, tenant_id, escopo):
        if AcessoEmpresaService.filtrar_empresa_ids(escopo) is not None:
            raise PermissionError("Privacidade exige acesso a todas as empresas do tenant.")
        cliente = Cliente.query.filter_by(id=cliente_id, tenant_id=tenant_id).first()
        if not cliente:
            raise ValueError("Cliente nao encontrado.")
        return cliente

    @staticmethod
    @atomic_operation
    def consentir(cliente_id, data, tenant_id, escopo, funcionario_id):
        cliente = ClientePrivacidadeService.obter(cliente_id, tenant_id, escopo)
        if cliente.anonimizado_em:
            raise ValueError("Cliente anonimizado.")
        reason = motivo(data)
        before = {key: getattr(cliente, key) for key in ("aceita_email", "aceita_sms", "aceita_whatsapp")}
        for key in before:
            if key in data:
                if not isinstance(data[key], bool):
                    raise ValueError("Consentimento deve ser booleano explicito.")
                setattr(cliente, key, data[key])
        after = {key: getattr(cliente, key) for key in before}
        for record in MensagemCliente.query.filter_by(tenant_id=tenant_id, cliente_id=cliente.id).all():
            if record.estado in ("PENDENTE", "FALHOU") and not after["aceita_" + record.canal.value.lower()]:
                record.estado = "CANCELADO"
                record.erro = "Descadastro solicitado."
        ClientePrivacidadeService.auditar(cliente, funcionario_id, "CLIENTE_CONSENTIMENTO",
            {"antes": before, "depois": after, "motivo": reason})
        return ClienteService.serializar_cliente(cliente)

    @staticmethod
    def auditar(cliente, actor, action, details):
        AuditService.registrar(action, tenant_id=cliente.tenant_id, actor_scope="tenant", actor_id=actor,
            entity_type="clientes", entity_id=cliente.id, details=json.dumps(details, ensure_ascii=True))

    @staticmethod
    @atomic_operation
    def exportar(cliente_id, tenant_id, escopo, funcionario_id):
        cliente = ClientePrivacidadeService.obter(cliente_id, tenant_id, escopo)
        result = {"cliente": ClienteService.serializar_cliente(cliente),
            "vendas": [ClienteService.serializar_venda_cliente(record) for record in Venda.query.filter_by(tenant_id=tenant_id, cliente_id=cliente_id).order_by(Venda.id).all()],
            "creditos": [ClienteService.serializar_credito(record) for record in CreditoCashbackCliente.query.filter_by(tenant_id=tenant_id, cliente_id=cliente_id).all()],
            "movimentos": [ClienteService.serializar_movimento_carteira(record) for record in MovimentoCarteiraCliente.query.filter_by(tenant_id=tenant_id, cliente_id=cliente_id).all()],
            "mensagens": [ClienteService.serializar_mensagem(record) for record in MensagemCliente.query.filter_by(tenant_id=tenant_id, cliente_id=cliente_id).all()],
            "consentimentos": [{"data": TimeService.serialize_utc_iso(record.criado_em), "detalhes": record.details}
                for record in AuditLog.query.filter_by(tenant_id=tenant_id, entity_type="clientes", entity_id=str(cliente_id), action="CLIENTE_CONSENTIMENTO").all()]}
        ClientePrivacidadeService.auditar(cliente, funcionario_id, "CLIENTE_EXPORTADO", {"formato": "JSON"})
        return result

    @staticmethod
    @atomic_operation
    def anonimizar(cliente_id, data, tenant_id, escopo, funcionario_id):
        cliente = ClientePrivacidadeService.obter(cliente_id, tenant_id, escopo)
        reason = motivo(data)
        if not cliente.anonimizado_em:
            cliente.nome = f"Cliente anonimizado {cliente.id}"
            for field in ("documento", "email", "telefone", "whatsapp", "data_nascimento", "observacao"):
                setattr(cliente, field, None)
            cliente.aceita_email = cliente.aceita_sms = cliente.aceita_whatsapp = cliente.ativo = False
            cliente.anonimizado_em = TimeService.now_utc_naive()
            for operation in OperacaoIdempotente.query.filter_by(tenant_id=tenant_id).all():
                response = operation.resposta
                if isinstance(response, dict) and response.get("cliente_id") == cliente_id:
                    operation.resposta = {**response, "cliente_nome": cliente.nome, "cliente_documento": None,
                        "email_venda": {"status": "ANONIMIZADO"}}
            for record in MensagemCliente.query.filter_by(tenant_id=tenant_id, cliente_id=cliente_id).all():
                if record.estado in ("PENDENTE", "FALHOU"):
                    record.estado = "CANCELADO"
                record.destinatario = "anonimizado"
                record.assunto = None
                record.conteudo = "Conteudo removido por anonimizacao."
                record.erro = record.resposta_integracao = None
            ClientePrivacidadeService.auditar(cliente, funcionario_id, "CLIENTE_ANONIMIZADO", {"motivo": reason,
                "retencao": "Vendas, financeiro, carteira, eventos e documentos fiscais historicos preservados."})
        return ClienteService.serializar_cliente(cliente)

    @staticmethod
    @atomic_operation
    def expirar(tenant_id):
        customer_ids = [record.id for record in Cliente.query.filter_by(tenant_id=tenant_id).order_by(Cliente.id).all()]
        return {"clientes_atualizados": sum(bool(ClienteService._aplicar_expiracoes_cliente(customer_id, tenant_id)) for customer_id in customer_ids)}
