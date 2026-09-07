from datetime import timedelta
import smtplib

from app.extensions import db
from app.models.db import CanalMensagemCliente, EntregaAlerta, ProdutoEmpresa
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.cliente_service import ClienteService
from app.services.comunicacao_service import ComunicacaoService
from app.services.time_service import TimeService
from app.services.transaction_service import atomic_operation, after_commit


class AlertaService:
    @staticmethod
    def enfileirar(tenant_id, empresa_id, chave, assunto, conteudo, destinatarios):
        created = []
        for destino in sorted(set(destinatarios)):
            if len(destino) > 160 or "@" not in destino or "\r" in destino or "\n" in destino:
                raise ValueError("Destinatario de alerta invalido.")
            existing = EntregaAlerta.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id,
                chave=chave, destinatario=destino).first()
            if existing:
                continue
            entrega = EntregaAlerta(tenant_id=tenant_id, empresa_id=empresa_id, chave=chave,
                destinatario=destino, assunto=assunto[:160], conteudo=conteudo)
            db.session.add(entrega)
            db.session.flush()
            created.append(entrega.id)
        for entrega_id in created:
            after_commit(lambda record_id=entrega_id: AlertaService.entregar(record_id, tenant_id))
        return created

    @staticmethod
    @atomic_operation
    def produtos(tenant_id, empresa_id, produto_ids):
        from app.services.estoque_service import EstoqueService
        config = EstoqueService._obter_ou_criar_configuracao(tenant_id)
        if not config.email_habilitado:
            return {"itens_processados": 0, "emails_enviados": 0}
        destinos = EstoqueService._listar_destinatarios(config.email_destinatarios)
        hoje = TimeService.today_br()
        agora = TimeService.now_utc_naive()
        created = []
        records = ProdutoEmpresa.query.filter(ProdutoEmpresa.tenant_id == tenant_id,
            ProdutoEmpresa.empresa_id == empresa_id, ProdutoEmpresa.produto_id.in_(produto_ids),
            ProdutoEmpresa.ativo.is_(True)).all()
        for record in records:
            if not record.produto.ativo:
                continue
            status = EstoqueService._determinar_status_alerta_email(record, config)
            if status and EstoqueService._pode_disparar_alerta_email(record, status, agora):
                subject, content, _ = EstoqueService._montar_email_alerta_estoque(record, status, agora)
                key = f"estoque:{record.id}:{status}:{hoje}"
                added = AlertaService.enfileirar(tenant_id, empresa_id, key, subject, content, destinos)
                created.extend(added)
                if added:
                    record.ultimo_alerta_estoque_status = status
                    record.ultimo_alerta_estoque_em = agora
            elif not status:
                record.ultimo_alerta_estoque_status = None
                record.ultimo_alerta_estoque_em = None
            if config.alertar_validade and record.data_validade and record.data_validade <= hoje + timedelta(days=config.dias_vencimento_alerta):
                status = "VENCIDO" if record.data_validade < hoje else "PROXIMO_VENCIMENTO"
                content = f"{record.produto.nome}: {status}; validade {record.data_validade}; estoque {record.estoque_atual}."
                created.extend(AlertaService.enfileirar(tenant_id, empresa_id,
                    f"validade:{record.id}:{record.data_validade}:{hoje}", "Alerta de validade OceanBlue", content, destinos))
        return {"itens_processados": len(records), "emails_enviados": len(created)}

    @staticmethod
    def entregar(entrega_id, tenant_id, retentar=False):
        try:
            entrega = EntregaAlerta.query.filter_by(id=entrega_id, tenant_id=tenant_id).with_for_update().populate_existing().first()
            if not entrega:
                raise ValueError("Entrega nao encontrada.")
            if entrega.status not in (("PENDENTE", "FALHOU") if retentar else ("PENDENTE",)):
                result = AlertaService.serializar(entrega)
                db.session.rollback()
                return result
            config = ClienteService.obter_modelo_configuracao_empresa(entrega.empresa_id, tenant_id)
            entrega.tentativas += 1
            if not config.email_habilitado or not config.smtp_host or not config.email_remetente:
                entrega.status = "FALHOU"
                entrega.erro = "Email nao configurado; configure e tente novamente."
                db.session.commit()
                return AlertaService.serializar(entrega)
            entrega.status = "INCERTO"
            entrega.erro = "Entrega em andamento ou sem confirmacao; nao reenviar automaticamente."
            db.session.commit()
            try:
                ComunicacaoService.enviar(configuracao=config, canal=CanalMensagemCliente.EMAIL,
                    destinatario=entrega.destinatario, assunto=entrega.assunto, conteudo=entrega.conteudo)
            except (ValueError, ConnectionRefusedError, smtplib.SMTPRecipientsRefused,
                    smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, smtplib.SMTPHeloError,
                    smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
                entrega.status = "FALHOU"
                entrega.erro = "Envio recusado antes da entrega; corrija a configuracao e tente novamente."
            except Exception:
                entrega.erro = "Falha sem confirmacao de entrega; retentativa automatica bloqueada."
            else:
                entrega.status = "ENVIADO"
                entrega.erro = None
                entrega.enviado_em = TimeService.now_utc_naive()
            db.session.commit()
            return AlertaService.serializar(entrega)
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def historico(tenant_id, escopo, empresa_id):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        return [AlertaService.serializar(record) for record in EntregaAlerta.query.filter_by(
            tenant_id=tenant_id, empresa_id=empresa_id).order_by(EntregaAlerta.id.desc()).limit(200)]

    @staticmethod
    def retentar(entrega_id, tenant_id, escopo):
        entrega = EntregaAlerta.query.filter_by(id=entrega_id, tenant_id=tenant_id).first()
        if not entrega:
            raise ValueError("Entrega nao encontrada.")
        AcessoEmpresaService.validar_empresa(entrega.empresa_id, escopo)
        if entrega.status == "INCERTO":
            raise ValueError("Entrega incerta: verifique o provedor; reenvio bloqueado para evitar duplicacao.")
        return AlertaService.entregar(entrega_id, tenant_id, retentar=True)

    @staticmethod
    @atomic_operation
    def rotina(tenant_id, empresa_id, escopo):
        from app.services.estoque_service import EstoqueService
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        config = EstoqueService._obter_ou_criar_configuracao(tenant_id)
        records = ProdutoEmpresa.query.filter_by(tenant_id=tenant_id, empresa_id=empresa_id, ativo=True).all()
        result = AlertaService.produtos(tenant_id, empresa_id, [record.produto_id for record in records])
        if config.resumo_diario and config.email_habilitado:
            dados = EstoqueService.listar_notificacoes(tenant_id, escopo, empresa_id, config.dias_vencimento_alerta)
            resumo = dados["resumo"]
            content = "\n".join(f"{name}: {count}" for name, count in resumo.items())
            AlertaService.enfileirar(tenant_id, empresa_id, f"resumo:{TimeService.today_br()}",
                "Resumo diario de estoque OceanBlue", content, EstoqueService._listar_destinatarios(config.email_destinatarios))
        return result

    @staticmethod
    def serializar(record):
        return {"id": record.id, "empresa_id": record.empresa_id, "chave": record.chave,
            "destinatario": record.destinatario, "assunto": record.assunto, "conteudo": record.conteudo,
            "status": record.status, "tentativas": record.tentativas, "erro": record.erro,
            "criado_em": TimeService.serialize_utc_iso(record.criado_em),
            "enviado_em": TimeService.serialize_utc_iso(record.enviado_em)}
