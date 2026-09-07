from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import current_app, render_template

from app.models.db import CanalMensagemCliente, ConfiguracaoNotificacaoEstoque
from app.models.db import MotivoMovimentoEstoque, MovimentoEstoque, TipoMovimentoEstoque
from app.repositorys.estoque_repository import EstoqueRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.cliente_service import ClienteService
from app.services.comunicacao_service import ComunicacaoService
from app.services.tenant_bootstrap_service import TenantBootstrapService
from app.services.time_service import TimeService
from app.extensions import db
from app.models.db import ProdutoEmpresa, ItemVenda, StatusVenda
from app.services.transaction_service import after_commit


from app.services.transaction_service import atomic_operation


class EstoqueService:
    ALERTA_EMAIL_COOLDOWN_HOURS = 12
    STATUS_ALERTA_ESTOQUE_BAIXO = "ESTOQUE_BAIXO"
    STATUS_ALERTA_SEM_ESTOQUE = "SEM_ESTOQUE"

    MOTIVOS_MANUAIS = {
        TipoMovimentoEstoque.ENTRADA: (
            MotivoMovimentoEstoque.COMPRA,
            MotivoMovimentoEstoque.AJUSTE,
            MotivoMovimentoEstoque.DEVOLUCAO,
            MotivoMovimentoEstoque.TRANSFERENCIA,
        ),
        TipoMovimentoEstoque.SAIDA: (
            MotivoMovimentoEstoque.AJUSTE,
            MotivoMovimentoEstoque.PERDA,
            MotivoMovimentoEstoque.TRANSFERENCIA,
        ),
    }

    @staticmethod
    def listar_saldos(tenant_id, escopo, empresa_id=None):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        return EstoqueRepository.listar_saldos(
            tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
        )

    @staticmethod
    def listar_movimentos(tenant_id, escopo, empresa_id=None, limite=50):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        return EstoqueRepository.listar_movimentos(
            tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            limite=limite,
        )

    @staticmethod
    def listar_auxiliares(tenant_id, escopo):
        EstoqueService._garantir_base_operacional(tenant_id)
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        empresas = EstoqueRepository.listar_empresas(tenant_id, empresa_ids=empresa_ids)
        produtos_empresa = EstoqueRepository.listar_produtos_empresa_disponiveis(tenant_id, empresa_ids=empresa_ids)

        return {
            "empresas": [
                {"id": empresa.id, "nome": empresa.nome_fantasia}
                for empresa in empresas
            ],
            "motivos": {
                "ENTRADA": [motivo.value for motivo in EstoqueService.MOTIVOS_MANUAIS[TipoMovimentoEstoque.ENTRADA]],
                "SAIDA": [motivo.value for motivo in EstoqueService.MOTIVOS_MANUAIS[TipoMovimentoEstoque.SAIDA]],
            },
            "produtos": [
                {
                    "id": item.id,
                    "produto_id": item.produto.id,
                    "empresa_id": item.empresa.id,
                    "empresa_nome": item.empresa.nome_fantasia,
                    "nome": item.produto.nome,
                    "categoria_nome": item.produto.categoria.nome if item.produto.categoria else "",
                    "codigo_barras": item.produto.codigo_barras,
                    "estoque_atual": int(item.estoque_atual),
                    "estoque_minimo": int(item.estoque_minimo),
                    "valor_compra": str(item.valor_compra),
                    "valor_venda": str(item.valor_venda),
                    "data_validade": item.data_validade.isoformat() if item.data_validade else None,
                }
                for item in produtos_empresa
            ],
        }

    @staticmethod
    def listar_notificacoes(tenant_id, escopo, empresa_id=None, dias_vencimento=30):
        configuracao = EstoqueService._obter_ou_criar_configuracao(tenant_id)
        registros = EstoqueService.listar_saldos(tenant_id, escopo, empresa_id=empresa_id)
        hoje = date.today()
        dias_alerta = max(
            int(dias_vencimento or configuracao.dias_vencimento_alerta or 30),
            1,
        )

        estoque_baixo = []
        sem_estoque = []
        vencidos = []
        proximos_vencimento = []

        for item in registros:
            dados = {
                "id": item.id,
                "produto_id": item.produto.id,
                "empresa_id": item.empresa.id,
                "empresa_nome": item.empresa.nome_fantasia,
                "categoria_nome": item.produto.categoria.nome if item.produto.categoria else "",
                "nome": item.produto.nome,
                "codigo_barras": item.produto.codigo_barras,
                "estoque_atual": int(item.estoque_atual),
                "estoque_minimo": int(item.estoque_minimo),
                "data_validade": item.data_validade.isoformat() if item.data_validade else None,
            }

            if configuracao.alertar_sem_estoque and int(item.estoque_atual) <= 0:
                sem_estoque.append(dados)
            elif configuracao.alertar_estoque_baixo and int(item.estoque_atual) <= int(item.estoque_minimo):
                estoque_baixo.append(dados)

            if configuracao.alertar_validade and item.data_validade:
                dias_restantes = (item.data_validade - hoje).days
                dados["dias_para_vencimento"] = dias_restantes

                if dias_restantes < 0:
                    vencidos.append(dados)
                elif dias_restantes <= dias_alerta:
                    proximos_vencimento.append(dados)

        return {
            "resumo": {
                "estoque_baixo": len(estoque_baixo),
                "sem_estoque": len(sem_estoque),
                "vencidos": len(vencidos),
                "proximos_vencimento": len(proximos_vencimento),
                "dias_vencimento": dias_alerta,
            },
            "estoque_baixo": estoque_baixo[:12],
            "sem_estoque": sem_estoque[:12],
            "vencidos": sorted(vencidos, key=lambda item: item["dias_para_vencimento"])[:12],
            "proximos_vencimento": sorted(proximos_vencimento, key=lambda item: item["dias_para_vencimento"])[:12],
        }

    @staticmethod
    def obter_configuracao_alerta(tenant_id, escopo):
        if not AcessoEmpresaService.possui_permissao(escopo, "gerenciar_alerta_estoque"):
            raise PermissionError("Voce nao tem permissao para gerenciar as configuracoes de alertas.")

        configuracao = EstoqueService._obter_ou_criar_configuracao(tenant_id)
        return EstoqueService.serializar_configuracao_alerta(configuracao)

    @staticmethod
    def atualizar_configuracao_alerta(data, tenant_id, escopo):
        if not AcessoEmpresaService.possui_permissao(escopo, "gerenciar_alerta_estoque"):
            raise PermissionError("Voce nao tem permissao para gerenciar as configuracoes de alertas.")

        try:
            configuracao = EstoqueService._obter_ou_criar_configuracao(tenant_id)
            configuracao.popup_ao_entrar = EstoqueService._to_bool(data.get("popup_ao_entrar", True))
            configuracao.alertar_estoque_baixo = EstoqueService._to_bool(data.get("alertar_estoque_baixo", True))
            configuracao.alertar_sem_estoque = EstoqueService._to_bool(data.get("alertar_sem_estoque", True))
            configuracao.alertar_validade = EstoqueService._to_bool(data.get("alertar_validade", True))
            configuracao.dias_vencimento_alerta = EstoqueService._to_positive_int(
                data.get("dias_vencimento_alerta", 30),
                "dias de vencimento",
            )
            configuracao.email_habilitado = EstoqueService._to_bool(data.get("email_habilitado", False))
            configuracao.email_destinatarios = EstoqueService._normalizar_destinatarios(data.get("email_destinatarios"))
            configuracao.whatsapp_habilitado = EstoqueService._to_bool(data.get("whatsapp_habilitado", False))
            configuracao.whatsapp_destinatarios = EstoqueService._normalizar_destinatarios(data.get("whatsapp_destinatarios"))
            configuracao.resumo_diario = EstoqueService._to_bool(data.get("resumo_diario", False))

            EstoqueRepository.adicionar(configuracao)
            EstoqueRepository.salvar()
            return EstoqueService.serializar_configuracao_alerta(configuracao)
        except Exception:
            EstoqueRepository.rollback()
            raise

    @staticmethod
    def obter_popup_alertas(tenant_id, escopo):
        if not AcessoEmpresaService.possui_permissao(escopo, "visualizar_notificacao"):
            raise PermissionError("Voce nao tem permissao para visualizar alertas de estoque.")

        configuracao = EstoqueService._obter_ou_criar_configuracao(tenant_id)
        dados = EstoqueService.listar_notificacoes(
            tenant_id=tenant_id,
            escopo=escopo,
            dias_vencimento=configuracao.dias_vencimento_alerta,
        )

        itens = (
            [
                {**item, "tipo": "Sem estoque"}
                for item in dados["sem_estoque"][:4]
            ] +
            [
                {**item, "tipo": "Baixo estoque"}
                for item in dados["estoque_baixo"][:4]
            ] +
            [
                {**item, "tipo": "Validade"}
                for item in (dados["vencidos"][:2] + dados["proximos_vencimento"][:2])
            ]
        )[:8]

        return {
            "deve_exibir": bool(configuracao.popup_ao_entrar and itens),
            "configuracao": EstoqueService.serializar_configuracao_alerta(configuracao),
            "resumo": dados["resumo"],
            "itens": itens,
        }

    @staticmethod
    def listar_produtos_mais_vendidos(tenant_id, escopo, empresa_id=None, periodo="mes", data_inicio=None, data_fim=None, limite=12):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)

        if empresa_id:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        periodo_normalizado = str(periodo or "mes").strip().lower()
        hoje = date.today()

        if periodo_normalizado == "semana":
            data_inicio_obj = hoje - timedelta(days=6)
            data_fim_obj = hoje
        elif periodo_normalizado == "mes":
            data_inicio_obj = date(hoje.year, hoje.month, 1)
            data_fim_obj = hoje
        elif periodo_normalizado == "periodo":
            data_inicio_obj = EstoqueService._to_optional_date(data_inicio) or date(hoje.year, hoje.month, 1)
            data_fim_obj = EstoqueService._to_optional_date(data_fim) or hoje
        else:
            raise ValueError("Periodo invalido. Use semana, mes ou periodo.")

        if data_fim_obj < data_inicio_obj:
            raise ValueError("A data final nao pode ser menor que a data inicial.")

        itens = EstoqueRepository.listar_produtos_mais_vendidos(
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            empresa_id=empresa_id,
            data_inicio=data_inicio_obj,
            data_fim=data_fim_obj,
            limite=limite,
        )

        return {
            "periodo": {
                "tipo": periodo_normalizado,
                "data_inicio": data_inicio_obj.isoformat(),
                "data_fim": data_fim_obj.isoformat(),
            },
            "itens": [
                {
                    "produto_id": item.produto_id,
                    "produto_nome": item.produto_nome,
                    "empresa_id": item.empresa_id,
                    "empresa_nome": item.empresa_nome,
                    "quantidade": int(item.quantidade or 0),
                    "faturamento": str(Decimal(str(item.faturamento or 0)).quantize(Decimal("0.01"))),
                }
                for item in itens
            ],
        }

    @staticmethod
    def serializar_configuracao_alerta(configuracao):
        return {
            "id": configuracao.id,
            "popup_ao_entrar": bool(configuracao.popup_ao_entrar),
            "alertar_estoque_baixo": bool(configuracao.alertar_estoque_baixo),
            "alertar_sem_estoque": bool(configuracao.alertar_sem_estoque),
            "alertar_validade": bool(configuracao.alertar_validade),
            "dias_vencimento_alerta": int(configuracao.dias_vencimento_alerta or 30),
            "email_habilitado": bool(configuracao.email_habilitado),
            "email_destinatarios": configuracao.email_destinatarios or "",
            "whatsapp_habilitado": bool(configuracao.whatsapp_habilitado),
            "whatsapp_destinatarios": configuracao.whatsapp_destinatarios or "",
            "resumo_diario": bool(configuracao.resumo_diario),
            "possui_dispatch_email": True,
            "possui_dispatch_whatsapp": True,
        }

    @staticmethod
    def processar_alertas_por_produtos(tenant_id, empresa_id, produto_ids):
        if db.session.info.get("atomic_operation"):
            after_commit(lambda: EstoqueService.processar_alertas_por_produtos(tenant_id, empresa_id, produto_ids))
            return
        ids_unicos = []
        for produto_id in produto_ids or []:
            produto_id_int = EstoqueService._to_optional_int(produto_id, "Produto")
            if produto_id_int and produto_id_int not in ids_unicos:
                ids_unicos.append(produto_id_int)

        if not ids_unicos:
            return {"itens_processados": 0, "emails_enviados": 0}

        configuracao_alerta = EstoqueService._obter_ou_criar_configuracao(tenant_id)
        houve_alteracao = False
        emails_enviados = 0

        try:
            for produto_id in ids_unicos:
                produto_empresa = EstoqueRepository.buscar_produto_empresa(produto_id, empresa_id, tenant_id)
                if not produto_empresa or not produto_empresa.ativo:
                    continue

                alterado, email_enviado = EstoqueService._processar_alerta_email_produto(
                    tenant_id=tenant_id,
                    configuracao_alerta=configuracao_alerta,
                    produto_empresa=produto_empresa,
                )
                houve_alteracao = houve_alteracao or alterado
                emails_enviados += int(bool(email_enviado))

            if houve_alteracao:
                EstoqueRepository.salvar()
        except Exception as exc:
            EstoqueRepository.rollback()
            current_app.logger.warning("Falha ao processar alerta de estoque por email: %s", exc)

        return {
            "itens_processados": len(ids_unicos),
            "emails_enviados": emails_enviados,
        }

    @staticmethod
    def _processar_alerta_email_produto(tenant_id, configuracao_alerta, produto_empresa):
        status_alerta = EstoqueService._determinar_status_alerta_email(produto_empresa, configuracao_alerta)
        agora = TimeService.now_utc_naive()

        if status_alerta is None:
            if produto_empresa.ultimo_alerta_estoque_status or produto_empresa.ultimo_alerta_estoque_em:
                produto_empresa.ultimo_alerta_estoque_status = None
                produto_empresa.ultimo_alerta_estoque_em = None
                EstoqueRepository.adicionar(produto_empresa)
                return True, False
            return False, False

        if not configuracao_alerta.email_habilitado:
            return False, False

        destinatarios = EstoqueService._listar_destinatarios(configuracao_alerta.email_destinatarios)
        if not destinatarios:
            return False, False

        if not EstoqueService._pode_disparar_alerta_email(produto_empresa, status_alerta, agora):
            return False, False

        configuracao_email = ClienteService.obter_modelo_configuracao_empresa(produto_empresa.empresa_id, tenant_id)
        if not EstoqueService._configuracao_email_operacional_valida(configuracao_email):
            return False, False

        assunto, conteudo, html_conteudo = EstoqueService._montar_email_alerta_estoque(
            produto_empresa,
            status_alerta,
            agora,
        )
        houve_envio = False

        for destinatario in destinatarios:
            try:
                ComunicacaoService.enviar(
                    configuracao=configuracao_email,
                    canal=CanalMensagemCliente.EMAIL,
                    destinatario=destinatario,
                    assunto=assunto,
                    conteudo=conteudo,
                    cliente=None,
                    html_conteudo=html_conteudo,
                )
                houve_envio = True
            except Exception as exc:
                current_app.logger.warning(
                    "Falha ao enviar alerta de estoque para %s (%s / empresa %s): %s",
                    destinatario,
                    getattr(produto_empresa.produto, "nome", produto_empresa.produto_id),
                    produto_empresa.empresa_id,
                    exc,
                )

        if not houve_envio:
            return False, False

        produto_empresa.ultimo_alerta_estoque_status = status_alerta
        produto_empresa.ultimo_alerta_estoque_em = agora
        EstoqueRepository.adicionar(produto_empresa)
        return True, True

    @staticmethod
    def _determinar_status_alerta_email(produto_empresa, configuracao_alerta):
        estoque_atual = int(produto_empresa.estoque_atual or 0)
        estoque_minimo = int(produto_empresa.estoque_minimo or 0)

        if configuracao_alerta.alertar_sem_estoque and estoque_atual <= 0:
            return EstoqueService.STATUS_ALERTA_SEM_ESTOQUE

        if configuracao_alerta.alertar_estoque_baixo and estoque_atual <= estoque_minimo:
            return EstoqueService.STATUS_ALERTA_ESTOQUE_BAIXO

        return None

    @staticmethod
    def _pode_disparar_alerta_email(produto_empresa, status_alerta, agora):
        ultimo_status = (produto_empresa.ultimo_alerta_estoque_status or "").strip().upper() or None
        ultimo_alerta_em = getattr(produto_empresa, "ultimo_alerta_estoque_em", None)

        if ultimo_status != status_alerta:
            return True

        if not ultimo_alerta_em:
            return True

        return agora >= (ultimo_alerta_em + timedelta(hours=EstoqueService.ALERTA_EMAIL_COOLDOWN_HOURS))

    @staticmethod
    def _listar_destinatarios(value):
        linhas = [parte.strip() for parte in str(value or "").replace(";", "\n").replace(",", "\n").splitlines()]
        return [parte for parte in linhas if parte]

    @staticmethod
    def _configuracao_email_operacional_valida(configuracao):
        return bool(
            getattr(configuracao, "email_habilitado", False)
            and (getattr(configuracao, "email_remetente", None) or "").strip()
            and (getattr(configuracao, "smtp_host", None) or "").strip()
        )

    @staticmethod
    def _montar_email_alerta_estoque(produto_empresa, status_alerta, data_referencia):
        produto_nome = produto_empresa.produto.nome if getattr(produto_empresa, "produto", None) else f"Produto #{produto_empresa.produto_id}"
        empresa_nome = produto_empresa.empresa.nome_fantasia if getattr(produto_empresa, "empresa", None) else f"Empresa #{produto_empresa.empresa_id}"
        status_legivel = "sem estoque" if status_alerta == EstoqueService.STATUS_ALERTA_SEM_ESTOQUE else "abaixo do minimo"

        assunto = f"Alerta de estoque: {produto_nome} {status_legivel} - {empresa_nome}"
        conteudo = "\n".join([
            "Ola,",
            "",
            "O sistema OceanBlue identificou um alerta operacional de estoque.",
            "",
            f"Empresa: {empresa_nome}",
            f"Produto: {produto_nome}",
            f"Status: {status_legivel}",
            f"Estoque atual: {int(produto_empresa.estoque_atual or 0)}",
            f"Estoque minimo: {int(produto_empresa.estoque_minimo or 0)}",
            f"Gerado em: {TimeService.format_br(data_referencia)}",
        ]).strip()

        html_conteudo = render_template(
            "emails/alerta_estoque.html",
            preheader=f"{produto_nome} esta {status_legivel}.",
            badge="Alerta operacional",
            email_title="Estoque requer atencao",
            email_subtitle=f"{empresa_nome} recebeu um alerta automatico de reposicao no OceanBlue.",
            footer_note=f"Alerta operacional emitido automaticamente para {empresa_nome}.",
            produto_nome=produto_nome,
            empresa_nome=empresa_nome,
            status_alerta=status_legivel,
            estoque_atual=int(produto_empresa.estoque_atual or 0),
            estoque_minimo=int(produto_empresa.estoque_minimo or 0),
            codigo_barras=(getattr(getattr(produto_empresa, "produto", None), "codigo_barras", None) or "").strip() or None,
            data_alerta=TimeService.format_br(data_referencia),
        )
        return assunto, conteudo, html_conteudo

    @staticmethod
    @atomic_operation
    def registrar_movimentacao_manual(data, tenant_id, escopo, funcionario_id):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        produto_empresa_id = EstoqueService._to_int(data.get("produto_empresa_id"), "Produto")
        tipo = EstoqueService._to_tipo_movimento(data.get("tipo_movimento"))
        motivo = EstoqueService._to_motivo(data.get("motivo"))
        quantidade = EstoqueService._to_positive_int(data.get("quantidade"), "quantidade")
        valor_unitario = EstoqueService._to_optional_decimal(data.get("valor_unitario"), "valor unitario", casas=2)
        observacao = (data.get("observacao") or "").strip() or None

        produto_empresa = EstoqueRepository.buscar_produto_empresa_por_id(
            produto_empresa_id,
            tenant_id,
            empresa_ids=empresa_ids,
        )
        if not produto_empresa:
            raise ValueError("Produto nao encontrado para o estoque informado.")

        AcessoEmpresaService.validar_empresa(produto_empresa.empresa_id, escopo)
        EstoqueService._validar_motivo_manual(tipo, motivo)

        try:
            movimento = EstoqueService._registrar_movimento(
                tenant_id=tenant_id,
                produto_empresa=produto_empresa,
                tipo_movimento=tipo,
                motivo=motivo,
                quantidade=quantidade,
                funcionario_id=funcionario_id,
                valor_unitario=valor_unitario,
                observacao=observacao,
            )
            EstoqueRepository.salvar()
            EstoqueService.processar_alertas_por_produtos(
                tenant_id=tenant_id,
                empresa_id=produto_empresa.empresa_id,
                produto_ids=[produto_empresa.produto_id],
            )
            return movimento
        except Exception:
            EstoqueRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def registrar_saida_por_venda(
        venda_id,
        empresa_id,
        itens,
        tenant_id,
        funcionario_id=None,
        escopo=None,
        persistir=True,
    ):
        if escopo is not None:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        movimentos = []

        try:
            for item in itens:
                item_venda_id = EstoqueService._to_optional_int(item.get("item_venda_id"), "Item da venda")
                produto_id = EstoqueService._to_int(item.get("produto_id"), "Produto")
                quantidade = EstoqueService._to_positive_int(item.get("quantidade"), "quantidade")
                valor_unitario = EstoqueService._to_optional_decimal(
                    item.get("valor_unitario"),
                    "valor unitario",
                    casas=2
                )

                produto_empresa = EstoqueRepository.buscar_produto_empresa(produto_id, empresa_id, tenant_id)
                if not produto_empresa:
                    raise ValueError("Produto da venda nao encontrado no estoque da empresa.")

                movimento = EstoqueService._registrar_movimento(
                    tenant_id=tenant_id,
                    produto_empresa=produto_empresa,
                    tipo_movimento=TipoMovimentoEstoque.SAIDA,
                    motivo=MotivoMovimentoEstoque.VENDA,
                    quantidade=quantidade,
                    funcionario_id=funcionario_id,
                    venda_id=venda_id,
                    item_venda_id=item_venda_id,
                    valor_unitario=valor_unitario,
                    observacao="Baixa automatica por venda do PDV.",
                )
                movimentos.append(movimento)

            if persistir:
                EstoqueRepository.salvar()
            return movimentos
        except Exception:
            if persistir:
                EstoqueRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def registrar_entrada_por_cancelamento_venda(
        venda_id,
        empresa_id,
        itens,
        tenant_id,
        funcionario_id=None,
        escopo=None,
        persistir=True,
    ):
        if escopo is not None:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        movimentos = []

        try:
            for item in itens:
                item_venda_id = EstoqueService._to_optional_int(item.get("item_venda_id"), "Item da venda")
                produto_id = EstoqueService._to_int(item.get("produto_id"), "Produto")
                quantidade = EstoqueService._to_positive_int(item.get("quantidade"), "quantidade")
                valor_unitario = EstoqueService._to_optional_decimal(
                    item.get("valor_unitario"),
                    "valor unitario",
                    casas=2,
                )

                produto_empresa = EstoqueRepository.buscar_produto_empresa(produto_id, empresa_id, tenant_id)
                if not produto_empresa:
                    raise ValueError("Produto da venda nao encontrado no estoque da empresa.")

                movimento_origem = None
                if item_venda_id:
                    movimento_origem = EstoqueRepository.buscar_movimento_venda_por_item(item_venda_id, tenant_id)
                    if movimento_origem and quantidade >= int(movimento_origem.quantidade):
                        movimento_origem.revertido = True

                movimento = EstoqueService._registrar_movimento(
                    tenant_id=tenant_id,
                    produto_empresa=produto_empresa,
                    tipo_movimento=TipoMovimentoEstoque.ENTRADA,
                    motivo=MotivoMovimentoEstoque.DEVOLUCAO,
                    quantidade=quantidade,
                    funcionario_id=funcionario_id,
                    venda_id=venda_id,
                    item_venda_id=item_venda_id,
                    movimento_origem_id=movimento_origem.id if movimento_origem else None,
                    valor_unitario=valor_unitario,
                    observacao="Estorno automatico por cancelamento de venda do PDV.",
                )
                movimentos.append(movimento)

            if persistir:
                EstoqueRepository.salvar()
            return movimentos
        except Exception:
            if persistir:
                EstoqueRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def registrar_entrada_por_cancelamento_item_venda(
        venda_id,
        empresa_id,
        item_venda,
        quantidade,
        tenant_id,
        funcionario_id=None,
        escopo=None,
        persistir=True,
    ):
        if escopo is not None:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        try:
            quantidade_cancelada = EstoqueService._to_positive_int(quantidade, "quantidade")
            produto_empresa = EstoqueRepository.buscar_produto_empresa(item_venda.produto_id, empresa_id, tenant_id)
            if not produto_empresa:
                raise ValueError("Produto da venda nao encontrado no estoque da empresa.")

            movimento_origem = EstoqueRepository.buscar_movimento_venda_por_item(item_venda.id, tenant_id)
            if movimento_origem and int(getattr(item_venda, "quantidade_cancelada", 0) or 0) >= int(item_venda.quantidade):
                movimento_origem.revertido = True

            movimento = EstoqueService._registrar_movimento(
                tenant_id=tenant_id,
                produto_empresa=produto_empresa,
                tipo_movimento=TipoMovimentoEstoque.ENTRADA,
                motivo=MotivoMovimentoEstoque.DEVOLUCAO,
                quantidade=quantidade_cancelada,
                funcionario_id=funcionario_id,
                venda_id=venda_id,
                item_venda_id=item_venda.id,
                movimento_origem_id=movimento_origem.id if movimento_origem else None,
                valor_unitario=EstoqueService._to_optional_decimal(item_venda.valor_unitario, "valor unitario", casas=2),
                observacao="Retorno automatico por cancelamento parcial de item da venda.",
            )

            if persistir:
                EstoqueRepository.salvar()
                EstoqueService.processar_alertas_por_produtos(
                    tenant_id=tenant_id,
                    empresa_id=empresa_id,
                    produto_ids=[item_venda.produto_id],
                )

            return movimento
        except Exception:
            if persistir:
                EstoqueRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def cancelar_movimento(movimento_id, data, tenant_id, escopo, funcionario_id):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        movimento = EstoqueRepository.buscar_movimento_por_id(movimento_id, tenant_id, empresa_ids=empresa_ids)
        if not movimento:
            raise ValueError("Movimentacao nao encontrada.")

        if movimento.revertido:
            return MovimentoEstoque.query.filter_by(tenant_id=tenant_id, movimento_origem_id=movimento.id).first()

        if movimento.venda_id:
            raise ValueError("Use o modulo do PDV para cancelar movimentos originados de venda.")

        if getattr(movimento, "adiantamentos", None):
            raise ValueError("Use o modulo de vales para tratar movimentos vinculados a adiantamentos.")

        configuracao = ClienteService.obter_modelo_configuracao_empresa(movimento.empresa_id, tenant_id)
        EstoqueService._validar_janela_cancelamento(
            data_base=movimento.data_movimento,
            limite_horas=configuracao.cancelamento_movimento_limite_horas,
            mensagem="A janela de cancelamento da movimentacao expirou para esta empresa.",
        )

        motivo = (data.get("motivo") or "").strip() or "Cancelamento manual de movimentacao."
        produto_empresa = EstoqueRepository.buscar_produto_empresa(movimento.produto_id, movimento.empresa_id, tenant_id)
        if not produto_empresa:
            raise ValueError("Produto nao encontrado para reverter a movimentacao.")

        tipo_reverso = (
            TipoMovimentoEstoque.ENTRADA
            if movimento.tipo_movimento == TipoMovimentoEstoque.SAIDA
            else TipoMovimentoEstoque.SAIDA
        )

        try:
            movimento.revertido = True
            movimento.cancelado_por_funcionario_id = funcionario_id
            movimento.cancelado_em = TimeService.now_utc_naive()
            movimento.motivo_cancelamento = motivo

            reversao = EstoqueService._registrar_movimento(
                tenant_id=tenant_id,
                produto_empresa=produto_empresa,
                tipo_movimento=tipo_reverso,
                motivo=movimento.motivo,
                quantidade=int(movimento.quantidade),
                funcionario_id=funcionario_id,
                valor_unitario=EstoqueService._to_optional_decimal(movimento.valor_unitario, "valor unitario", casas=2),
                observacao=f"Reversao automatica da movimentacao #{movimento.id}. {motivo}",
                movimento_origem_id=movimento.id,
            )
            EstoqueRepository.salvar()
            EstoqueService.processar_alertas_por_produtos(
                tenant_id=tenant_id,
                empresa_id=movimento.empresa_id,
                produto_ids=[movimento.produto_id],
            )
            return reversao
        except Exception:
            EstoqueRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def registrar_saida_por_adiantamento(
        tenant_id,
        empresa_id,
        produto_id,
        quantidade,
        funcionario_id=None,
        valor_unitario=None,
        observacao=None,
        escopo=None,
        persistir=True,
    ):
        if escopo is not None:
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        try:
            produto_empresa = EstoqueRepository.buscar_produto_empresa(produto_id, empresa_id, tenant_id)
            if not produto_empresa:
                raise ValueError("Produto nao encontrado no estoque da empresa.")

            movimento = EstoqueService._registrar_movimento(
                tenant_id=tenant_id,
                produto_empresa=produto_empresa,
                tipo_movimento=TipoMovimentoEstoque.SAIDA,
                motivo=MotivoMovimentoEstoque.AJUSTE,
                quantidade=EstoqueService._to_positive_int(quantidade, "quantidade"),
                funcionario_id=funcionario_id,
                valor_unitario=EstoqueService._to_optional_decimal(valor_unitario, "valor unitario", casas=2),
                observacao=observacao or "Retirada de produto por adiantamento em folha.",
            )

            if persistir:
                EstoqueRepository.salvar()

            return movimento
        except Exception:
            if persistir:
                EstoqueRepository.rollback()
            raise

    @staticmethod
    def _registrar_movimento(
        tenant_id,
        produto_empresa,
        tipo_movimento,
        motivo,
        quantidade,
        funcionario_id=None,
        venda_id=None,
        item_venda_id=None,
        movimento_origem_id=None,
        valor_unitario=None,
        observacao=None,
        data_movimento=None,
    ):
        if quantidade <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")

        db.session.flush()
        db.session.refresh(produto_empresa, with_for_update={"of": ProdutoEmpresa})
        if produto_empresa.tenant_id != tenant_id:
            raise PermissionError("Produto indisponivel neste tenant.")
        if venda_id and not item_venda_id:
            raise ValueError("Item da venda obrigatorio para movimentacao idempotente.")
        if item_venda_id:
            item = ItemVenda.query.filter_by(id=item_venda_id, tenant_id=tenant_id, venda_id=venda_id).first()
            if not item or item.produto_id != produto_empresa.produto_id or item.venda.empresa_id != produto_empresa.empresa_id:
                raise ValueError("Item incompativel com a venda e o estoque.")
            previous = MovimentoEstoque.query.filter_by(tenant_id=tenant_id, item_venda_id=item_venda_id)
            if tipo_movimento == TipoMovimentoEstoque.SAIDA and motivo == MotivoMovimentoEstoque.VENDA:
                if quantidade != item.quantidade:
                    raise ValueError("Quantidade da baixa difere do item da venda.")
                existing = previous.filter_by(tipo_movimento=TipoMovimentoEstoque.SAIDA, motivo=MotivoMovimentoEstoque.VENDA).first()
                if existing:
                    if existing.quantidade != quantidade:
                        raise ValueError("Baixa do item ja registrada com outra quantidade.")
                    return existing
            elif tipo_movimento == TipoMovimentoEstoque.ENTRADA and motivo == MotivoMovimentoEstoque.DEVOLUCAO:
                if item.venda.status != StatusVenda.CANCELADA and not item.quantidade_cancelada:
                    raise ValueError("Item ainda nao cancelado.")
                if not previous.filter_by(tipo_movimento=TipoMovimentoEstoque.SAIDA, motivo=MotivoMovimentoEstoque.VENDA).first():
                    raise ValueError("Baixa original da venda nao encontrada.")
                returns = previous.filter_by(tipo_movimento=TipoMovimentoEstoque.ENTRADA, motivo=MotivoMovimentoEstoque.DEVOLUCAO).all()
                restored = sum(record.quantidade for record in returns)
                target = int(item.quantidade_cancelada or 0) or int(item.quantidade)
                if restored >= target:
                    return returns[-1]
                if restored + quantidade > target:
                    raise ValueError("Devolucao ultrapassa a quantidade cancelada do item.")

        estoque_atual = int(produto_empresa.estoque_atual)

        if tipo_movimento == TipoMovimentoEstoque.SAIDA and estoque_atual < quantidade:
            raise ValueError("Estoque insuficiente para realizar a saida.")

        if tipo_movimento == TipoMovimentoEstoque.ENTRADA:
            produto_empresa.estoque_atual = estoque_atual + quantidade
        else:
            produto_empresa.estoque_atual = estoque_atual - quantidade

        if valor_unitario is not None and motivo == MotivoMovimentoEstoque.COMPRA:
            produto_empresa.valor_compra = valor_unitario

        valor_total = None
        if valor_unitario is not None:
            valor_total = (valor_unitario * quantidade).quantize(Decimal("0.01"))

        movimento = MovimentoEstoque(
            tenant_id=tenant_id,
            empresa_id=produto_empresa.empresa_id,
            produto_id=produto_empresa.produto_id,
            funcionario_id=funcionario_id,
            venda_id=venda_id,
            item_venda_id=item_venda_id,
            movimento_origem_id=movimento_origem_id,
            tipo_movimento=tipo_movimento,
            motivo=motivo,
            quantidade=quantidade,
            valor_unitario=valor_unitario,
            valor_total=valor_total,
            observacao=observacao,
            data_movimento=data_movimento or TimeService.now_utc_naive(),
        )
        EstoqueRepository.adicionar(movimento)
        EstoqueRepository.adicionar(produto_empresa)

        return movimento

    @staticmethod
    def _validar_motivo_manual(tipo, motivo):
        if motivo == MotivoMovimentoEstoque.VENDA:
            raise ValueError("Use o fluxo do PDV para movimentos de venda.")

        if motivo not in EstoqueService.MOTIVOS_MANUAIS[tipo]:
            raise ValueError("Motivo invalido para o tipo de movimentacao informado.")

    @staticmethod
    def _to_tipo_movimento(value):
        try:
            return TipoMovimentoEstoque[(value or "").strip().upper()]
        except KeyError:
            raise ValueError("Tipo de movimentacao invalido.")

    @staticmethod
    def _to_motivo(value):
        try:
            return MotivoMovimentoEstoque[(value or "").strip().upper()]
        except KeyError:
            raise ValueError("Motivo de movimentacao invalido.")

    @staticmethod
    def _to_decimal(value, field_name, casas=2, obrigatorio=False):
        if value in (None, ""):
            if obrigatorio:
                raise ValueError(f"Informe {field_name}.")
            value = 0

        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if not valor.is_finite() or abs(valor) >= Decimal("10000000000"):
            raise ValueError(f"Valor invalido para {field_name}.")
        if valor <= 0 and obrigatorio:
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")

        quant = "0." + ("0" * (casas - 1)) + "1" if casas > 0 else "1"
        return valor.quantize(Decimal(quant))

    @staticmethod
    def _to_optional_decimal(value, field_name, casas=2):
        if value in (None, ""):
            return None

        valor = EstoqueService._to_decimal(value, field_name, casas=casas, obrigatorio=False)
        if valor < 0:
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")
        return valor

    @staticmethod
    def _to_positive_int(value, field_name):
        if value in (None, ""):
            raise ValueError(f"Informe {field_name}.")

        try:
            valor = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if valor <= 0:
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")

        return valor

    @staticmethod
    def _to_int(value, field_name):
        if value in (None, ""):
            raise ValueError(f"{field_name} e obrigatorio.")

        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} invalido.")

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

        return str(value).strip().lower() in {"1", "true", "on", "sim", "yes"}

    @staticmethod
    def _normalizar_destinatarios(value):
        linhas = [parte.strip() for parte in str(value or "").replace(";", "\n").splitlines()]
        return "\n".join([parte for parte in linhas if parte]) or None

    @staticmethod
    def _to_optional_int(value, field_name):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} invalido.")

    @staticmethod
    def _esta_dentro_janela_cancelamento(data_base, limite_horas):
        try:
            limite = int(limite_horas or 0)
        except (TypeError, ValueError):
            limite = 0
        if limite <= 0:
            return True
        return TimeService.now_utc_naive() <= (data_base + timedelta(hours=limite))

    @staticmethod
    def _validar_janela_cancelamento(data_base, limite_horas, mensagem):
        if not EstoqueService._esta_dentro_janela_cancelamento(data_base, limite_horas):
            raise ValueError(mensagem)

    @staticmethod
    def _obter_ou_criar_configuracao(tenant_id):
        EstoqueService._garantir_base_operacional(tenant_id)
        configuracao = EstoqueRepository.obter_configuracao_notificacao(tenant_id)
        if configuracao:
            return configuracao

        configuracao = ConfiguracaoNotificacaoEstoque(
            tenant_id=tenant_id,
            popup_ao_entrar=True,
            alertar_estoque_baixo=True,
            alertar_sem_estoque=True,
            alertar_validade=True,
            dias_vencimento_alerta=30,
            email_habilitado=False,
            whatsapp_habilitado=False,
            resumo_diario=False,
        )
        EstoqueRepository.adicionar(configuracao)
        EstoqueRepository.salvar()
        return configuracao

    @staticmethod
    def _garantir_base_operacional(tenant_id):
        try:
            TenantBootstrapService.garantir_cadastros_operacionais(tenant_id)
            EstoqueRepository.salvar()
        except Exception:
            EstoqueRepository.rollback()
            raise
