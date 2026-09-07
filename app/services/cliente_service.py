from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json

from flask import render_template
from app.extensions import db
from app.services.transaction_service import atomic_operation
from app.services.money_service import positive_integer

from app.models.db import (
    CanalMensagemCliente,
    CarteiraCliente,
    Cliente,
    ConfiguracaoClienteEmpresa,
    CreditoCashbackCliente,
    MensagemCliente,
    MovimentoCarteiraCliente,
    StatusMensagemCliente,
    TipoMovimentoCarteiraCliente,
    TipoPessoa,
)
from app.repositorys.cliente_repository import ClienteRepository
from app.security.field_crypto import FieldCrypto
from app.security.errors import public_error
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.comunicacao_service import ComunicacaoService
from app.services.time_service import TimeService
from app.services.money_service import allocate_money


class ClienteService:
    @staticmethod
    @atomic_operation
    def listar(tenant_id, escopo, busca=None):
        clientes = ClienteRepository.listar_clientes(tenant_id, busca=busca)
        houve_expiracao = False
        for cliente in clientes:
            houve_expiracao = ClienteService._aplicar_expiracoes_cliente(cliente.id, tenant_id) or houve_expiracao
        if houve_expiracao:
            ClienteRepository.salvar()

        return [ClienteService.serializar_cliente(cliente) for cliente in clientes]

    @staticmethod
    @atomic_operation
    def listar_para_pdv(tenant_id):
        clientes = ClienteRepository.listar_clientes_para_pdv(tenant_id)
        houve_expiracao = False
        for cliente in clientes:
            houve_expiracao = ClienteService._aplicar_expiracoes_cliente(cliente.id, tenant_id) or houve_expiracao
        if houve_expiracao:
            ClienteRepository.salvar()

        return [
            {
                "id": cliente.id,
                "nome": cliente.nome,
                "documento": cliente.documento,
                "email": cliente.email,
                "telefone": cliente.telefone,
                "whatsapp": cliente.whatsapp,
                "saldo_cashback": str(ClienteService._to_decimal_value(cliente.carteira.saldo_disponivel if cliente.carteira else 0)),
            }
            for cliente in clientes
        ]

    @staticmethod
    def listar_auxiliares(tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        empresas = ClienteRepository.listar_empresas(tenant_id, empresa_ids=empresa_ids)

        return {
            "empresas": [
                {"id": empresa.id, "nome": empresa.nome_fantasia}
                for empresa in empresas
            ],
            "tipos_pessoa": [item.value for item in TipoPessoa],
            "canais_mensagem": [item.value for item in CanalMensagemCliente if item != CanalMensagemCliente.WHATSAPP],
        }

    @staticmethod
    @atomic_operation
    def criar(data, tenant_id):
        try:
            nome = (data.get("nome") or "").strip()
            documento = ClienteService._normalizar_documento(data.get("documento"))
            email = ClienteService._normalizar_email(data.get("email"))
            telefone = ClienteService._normalizar_telefone(data.get("telefone"))
            whatsapp = ClienteService._normalizar_telefone(data.get("whatsapp"))
            data_nascimento = ClienteService._to_optional_date(data.get("data_nascimento"))
            observacao = (data.get("observacao") or "").strip() or None
            tipo_pessoa = ClienteService._to_tipo_pessoa(data.get("tipo_pessoa"))
            aceita_email = ClienteService._to_bool(data.get("aceita_email", False))
            aceita_sms = ClienteService._to_bool(data.get("aceita_sms", False))
            aceita_whatsapp = ClienteService._to_bool(data.get("aceita_whatsapp", False))
            ativo = ClienteService._to_bool(data.get("ativo", True))

            if not nome:
                raise ValueError("Nome do cliente e obrigatorio.")

            if documento and ClienteRepository.buscar_cliente_por_documento(documento, tenant_id):
                raise ValueError("Ja existe um cliente com esse documento.")

            cliente = Cliente(
                tenant_id=tenant_id,
                nome=nome,
                documento=documento,
                tipo_pessoa=tipo_pessoa,
                email=email,
                telefone=telefone,
                whatsapp=whatsapp,
                data_nascimento=data_nascimento,
                observacao=observacao,
                aceita_email=aceita_email,
                aceita_sms=aceita_sms,
                aceita_whatsapp=aceita_whatsapp,
                ativo=ativo,
            )
            ClienteRepository.adicionar(cliente)
            ClienteRepository.flush()
            ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)
            ClienteService._auditar_consentimento(cliente, {}, "Cadastro")
            ClienteRepository.salvar()

            return ClienteRepository.buscar_cliente_por_id(cliente.id, tenant_id)
        except Exception:
            ClienteRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def atualizar(cliente_id, data, tenant_id):
        try:
            cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
            if not cliente:
                raise ValueError("Cliente nao encontrado.")

            nome = (data.get("nome") or "").strip()
            documento = ClienteService._normalizar_documento(data.get("documento"))
            email = ClienteService._normalizar_email(data.get("email"))
            telefone = ClienteService._normalizar_telefone(data.get("telefone"))
            whatsapp = ClienteService._normalizar_telefone(data.get("whatsapp"))
            data_nascimento = ClienteService._to_optional_date(data.get("data_nascimento"))
            observacao = (data.get("observacao") or "").strip() or None
            tipo_pessoa = ClienteService._to_tipo_pessoa(data.get("tipo_pessoa"))

            if not nome:
                raise ValueError("Nome do cliente e obrigatorio.")

            if documento and ClienteRepository.buscar_cliente_por_documento(documento, tenant_id, ignorar_cliente_id=cliente.id):
                raise ValueError("Ja existe um cliente com esse documento.")

            if cliente.anonimizado_em:
                raise ValueError("Cliente anonimizado nao pode ser reativado ou editado.")
            consent_before = {field: getattr(cliente, field) for field in ("aceita_email", "aceita_sms", "aceita_whatsapp")}
            cliente.nome = nome
            cliente.documento = documento
            cliente.tipo_pessoa = tipo_pessoa
            cliente.email = email
            cliente.telefone = telefone
            cliente.whatsapp = whatsapp
            cliente.data_nascimento = data_nascimento
            cliente.observacao = observacao
            cliente.aceita_email = ClienteService._to_bool(data.get("aceita_email", cliente.aceita_email))
            cliente.aceita_sms = ClienteService._to_bool(data.get("aceita_sms", cliente.aceita_sms))
            cliente.aceita_whatsapp = ClienteService._to_bool(data.get("aceita_whatsapp", cliente.aceita_whatsapp))
            cliente.ativo = ClienteService._to_bool(data.get("ativo", cliente.ativo))
            ClienteService._auditar_consentimento(cliente, consent_before, "Atualizacao cadastral")

            ClienteRepository.salvar()
            return ClienteRepository.buscar_cliente_por_id(cliente.id, tenant_id)
        except Exception:
            ClienteRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def deletar(cliente_id, tenant_id):
        try:
            cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
            if not cliente:
                raise ValueError("Cliente nao encontrado.")

            cliente.ativo = False
            ClienteRepository.salvar()
        except Exception:
            ClienteRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def obter(cliente_id, tenant_id):
        cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
        if not cliente:
            raise ValueError("Cliente nao encontrado.")

        if ClienteService._aplicar_expiracoes_cliente(cliente.id, tenant_id):
            ClienteRepository.salvar()
        return ClienteService.serializar_cliente(cliente)

    @staticmethod
    @atomic_operation
    def obter_carteira(cliente_id, tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
        if not cliente:
            raise ValueError("Cliente nao encontrado.")

        if ClienteService._aplicar_expiracoes_cliente(cliente.id, tenant_id):
            ClienteRepository.salvar()
        carteira = ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)
        creditos = ClienteRepository.listar_creditos_disponiveis(cliente.id, tenant_id)
        movimentos = ClienteRepository.listar_movimentos_carteira(cliente.id, tenant_id, limite=120)
        vendas = ClienteRepository.listar_vendas_cliente(cliente.id, tenant_id, empresa_ids=empresa_ids, limite=25)

        return {
            "cliente": ClienteService.serializar_cliente(cliente),
            "carteira": {
                "saldo_disponivel": str(ClienteService._to_decimal_value(carteira.saldo_disponivel)),
                "creditos_disponiveis": [ClienteService.serializar_credito(credito) for credito in creditos],
                "movimentos": [ClienteService.serializar_movimento_carteira(item) for item in movimentos],
            },
            "historico_vendas": [ClienteService.serializar_venda_cliente(venda) for venda in vendas],
        }

    @staticmethod
    def obter_historico_vendas(cliente_id, tenant_id, escopo, limite=100):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
        if not cliente:
            raise ValueError("Cliente nao encontrado.")

        vendas = ClienteRepository.listar_vendas_cliente(
            cliente_id=cliente.id,
            tenant_id=tenant_id,
            empresa_ids=empresa_ids,
            limite=limite,
        )
        return [ClienteService.serializar_venda_cliente(venda) for venda in vendas]

    @staticmethod
    def listar_mensagens(cliente_id, tenant_id):
        cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
        if not cliente:
            raise ValueError("Cliente nao encontrado.")

        mensagens = ClienteRepository.listar_mensagens_cliente(cliente.id, tenant_id, limite=40)
        return [ClienteService.serializar_mensagem(item) for item in mensagens]

    @staticmethod
    def listar_configuracoes_empresa(tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        empresas = ClienteRepository.listar_empresas(tenant_id, empresa_ids=empresa_ids)
        return [
            ClienteService.serializar_configuracao_empresa(
                ClienteService.obter_modelo_configuracao_empresa(empresa.id, tenant_id)
            )
            for empresa in empresas
        ]

    @staticmethod
    def obter_configuracao_empresa(empresa_id, tenant_id, escopo):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        configuracao = ClienteService.obter_modelo_configuracao_empresa(empresa_id, tenant_id)
        return ClienteService.serializar_configuracao_empresa(configuracao)

    @staticmethod
    def obter_modelo_configuracao_empresa(empresa_id, tenant_id):
        configuracao = ClienteRepository.buscar_configuracao_empresa(empresa_id, tenant_id)
        if configuracao:
            return configuracao

        configuracao = ConfiguracaoClienteEmpresa(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            cashback_ativo=False,
            cashback_percentual=Decimal("0.00"),
            cashback_percentual_limite_resgate_venda=Decimal("100.00"),
            cashback_validade_dias=30,
            cashback_valor_minimo_resgate=Decimal("0.00"),
            cancelamento_venda_limite_horas=24,
            cancelamento_item_limite_horas=24,
            cancelamento_movimento_limite_horas=24,
            email_habilitado=False,
            smtp_port=587,
            smtp_tls=True,
            smtp_ssl=False,
            whatsapp_habilitado=False,
            sms_habilitado=False,
            request_timeout_segundos=15,
        )
        empresa = ClienteRepository.buscar_empresa_por_id(empresa_id, tenant_id)
        configuracao._empresa_nome_fallback = empresa.nome_fantasia if empresa else None
        return configuracao

    @staticmethod
    def atualizar_configuracao_empresa(empresa_id, data, tenant_id, escopo):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        try:
            configuracao = ClienteService._obter_ou_criar_configuracao_empresa(empresa_id, tenant_id)
            ClienteService._aplicar_payload_configuracao(configuracao, data)
            ClienteRepository.salvar()
            return ClienteService.serializar_configuracao_empresa(configuracao)
        except Exception:
            ClienteRepository.rollback()
            raise

    @staticmethod
    def testar_configuracao_empresa(empresa_id, data, tenant_id, escopo, funcionario_id):
        AcessoEmpresaService.validar_empresa(empresa_id, escopo)
        configuracao_base = ClienteService.obter_modelo_configuracao_empresa(empresa_id, tenant_id)
        configuracao = ClienteService._clonar_configuracao_empresa(configuracao_base)
        ClienteService._aplicar_payload_configuracao(configuracao, data.get("configuracao") or {}, encrypt_sensitive=False)
        canal = ClienteService._to_canal(data.get("canal"))
        ClienteService._validar_canal_habilitado(configuracao, canal)
        destinatario = (data.get("destinatario") or "").strip()
        assunto = (data.get("assunto") or "").strip() or "Teste de integracao"
        conteudo = (data.get("conteudo") or "").strip() or "Mensagem de teste enviada pelo modulo de clientes."

        if not destinatario:
            raise ValueError("Informe o destinatario para o teste.")

        resposta = ComunicacaoService.enviar(
            configuracao=configuracao,
            canal=canal,
            destinatario=destinatario,
            assunto=assunto,
            conteudo=conteudo,
            cliente=None,
        )
        return {
            "canal": canal.value,
            "destinatario": destinatario,
            "status": "ENVIADO",
            "resposta": resposta.get("resposta") if isinstance(resposta, dict) else None,
            "funcionario_id": funcionario_id,
        }

    @staticmethod
    @atomic_operation
    def enviar_mensagem(cliente_id, data, tenant_id, escopo, funcionario_id):
        try:
            cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
            if not cliente:
                raise ValueError("Cliente nao encontrado.")

            empresa_id = ClienteService._to_int(data.get("empresa_id"), "Empresa")
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
            configuracao = ClienteService._obter_ou_criar_configuracao_empresa(empresa_id, tenant_id)
            canal = ClienteService._to_canal(data.get("canal"))
            ClienteService._validar_canal_habilitado(configuracao, canal)
            assunto = (data.get("assunto") or "").strip() or None
            conteudo = (data.get("conteudo") or "").strip()
            if not conteudo:
                raise ValueError("Conteudo da mensagem e obrigatorio.")

            ClienteService._validar_opt_in(cliente, canal)
            return ClienteService._registrar_envio_mensagem_cliente(
                cliente=cliente,
                configuracao=configuracao,
                empresa_id=empresa_id,
                canal=canal,
                assunto=assunto,
                conteudo=conteudo,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                chave=data.get("idempotency_key"),
            )
        except Exception:
            ClienteRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def enviar_mensagem_coletiva(data, tenant_id, escopo, funcionario_id):
        try:
            empresa_id = ClienteService._to_int(data.get("empresa_id"), "Empresa")
            AcessoEmpresaService.validar_empresa(empresa_id, escopo)
            configuracao = ClienteService._obter_ou_criar_configuracao_empresa(empresa_id, tenant_id)
            canal = ClienteService._to_canal(data.get("canal"))
            ClienteService._validar_canal_habilitado(configuracao, canal)
            assunto = (data.get("assunto") or "").strip() or None
            conteudo = (data.get("conteudo") or "").strip()
            if not conteudo:
                raise ValueError("Conteudo da mensagem e obrigatorio.")

            cliente_ids_payload = data.get("cliente_ids")
            cliente_ids = None
            if isinstance(cliente_ids_payload, list) and cliente_ids_payload:
                cliente_ids = [ClienteService._to_int(item, "Cliente") for item in cliente_ids_payload]

            clientes = ClienteRepository.listar_clientes_para_mensagem(tenant_id, cliente_ids=cliente_ids)

            enfileirados = 0
            enviados = 0
            erros = 0
            ignorados = 0
            detalhes = []

            for cliente in clientes:
                try:
                    ClienteService._validar_opt_in(cliente, canal)
                    destinatario = ClienteService._obter_destinatario_cliente(cliente, canal)
                except ValueError as exc:
                    ignorados += 1
                    detalhes.append({
                        "cliente_id": cliente.id,
                        "cliente_nome": cliente.nome,
                        "status": "IGNORADO",
                        "motivo": public_error(exc),
                    })
                    continue

                mensagem = ClienteService._registrar_envio_mensagem_cliente(
                    cliente=cliente,
                    configuracao=configuracao,
                    empresa_id=empresa_id,
                    canal=canal,
                    assunto=assunto,
                    conteudo=conteudo,
                    tenant_id=tenant_id,
                    funcionario_id=funcionario_id,
                    destinatario=destinatario,
                    validar_opt_in=False,
                    propagar_erro=False,
                    chave=data.get("idempotency_key"),
                )

                if mensagem["status"] == "PENDENTE":
                    enfileirados += 1
                elif mensagem["status"] == StatusMensagemCliente.ENVIADO.value:
                    enviados += 1
                else:
                    erros += 1
                    detalhes.append({
                        "cliente_id": cliente.id,
                        "cliente_nome": cliente.nome,
                        "status": mensagem["status"],
                        "motivo": mensagem.get("erro") or "Falha ao enviar a mensagem.",
                    })

            return {
                "empresa_id": empresa_id,
                "canal": canal.value,
                "total_clientes": len(clientes),
                "enviados": enviados,
                "enfileirados": enfileirados,
                "erros": erros,
                "ignorados": ignorados,
                "detalhes": detalhes,
            }
        except Exception:
            ClienteRepository.rollback()
            raise

    @staticmethod
    def enviar_email_venda_automatica(venda, tenant_id, funcionario_id=None):
        cliente = getattr(venda, "cliente", None)
        if not cliente:
            return {
                "status": "NAO_APLICAVEL",
                "motivo": "Venda sem cliente vinculado.",
            }

        configuracao = ClienteService._obter_ou_criar_configuracao_empresa(venda.empresa_id, tenant_id)
        if not configuracao.email_habilitado:
            return {
                "status": "NAO_APLICAVEL",
                "motivo": "Email desabilitado para esta empresa.",
            }

        if not bool(cliente.aceita_email):
            return {
                "status": "NAO_APLICAVEL",
                "motivo": "Cliente sem autorizacao para email.",
            }

        destinatario = (cliente.email or "").strip()
        if not destinatario:
            return {
                "status": "NAO_APLICAVEL",
                "motivo": "Cliente sem email cadastrado.",
            }

        try:
            ClienteService._validar_canal_habilitado(configuracao, CanalMensagemCliente.EMAIL)
            assunto, conteudo, html_conteudo = ClienteService._montar_email_venda(venda, tenant_id)
            mensagem = ClienteService._registrar_envio_mensagem_cliente(
                cliente=cliente,
                configuracao=configuracao,
                empresa_id=venda.empresa_id,
                canal=CanalMensagemCliente.EMAIL,
                assunto=assunto,
                conteudo=conteudo,
                html_conteudo=html_conteudo,
                tenant_id=tenant_id,
                funcionario_id=funcionario_id,
                destinatario=destinatario,
                validar_opt_in=False,
                propagar_erro=False,
                chave=f"venda:{venda.id}",
            )
            return {
                "status": mensagem["status"],
                "destinatario": mensagem["destinatario"],
                "mensagem_id": mensagem["id"],
                "erro": mensagem.get("erro"),
            }
        except Exception:
            raise

    @staticmethod
    def _registrar_envio_mensagem_cliente(
        cliente,
        configuracao,
        empresa_id,
        canal,
        assunto,
        conteudo,
        tenant_id,
        funcionario_id=None,
        destinatario=None,
        validar_opt_in=True,
        propagar_erro=True,
        html_conteudo=None,
        chave=None,
    ):
        from app.services.mensagem_fila_service import MensagemFilaService
        return MensagemFilaService.enfileirar(cliente.id, empresa_id, canal, assunto, conteudo,
            chave, tenant_id, funcionario_id)

    @staticmethod
    def _montar_email_venda(venda, tenant_id):
        cliente = getattr(venda, "cliente", None)
        empresa_nome = venda.empresa.nome_fantasia if getattr(venda, "empresa", None) else f"Empresa #{venda.empresa_id}"
        credito = ClienteRepository.buscar_credito_por_venda_origem(venda.id, tenant_id)
        carteira = ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)

        linhas = [
            f"Ola {cliente.nome},",
            "",
            f"Sua compra na {empresa_nome} foi concluida com sucesso.",
            "",
            "Resumo da venda",
            f"- Numero: {venda.numero_unico}",
            f"- Data: {TimeService.format_br(venda.data_venda)}",
            f"- Total pago: {ClienteService._formatar_moeda(getattr(venda, 'total', 0))}",
        ]

        desconto = ClienteService._to_decimal_value(getattr(venda, "desconto", 0))
        cashback_utilizado = ClienteService._to_decimal_value(getattr(venda, "cashback_utilizado", 0))
        cashback_gerado = ClienteService._to_decimal_value(getattr(venda, "cashback_gerado", 0))

        if desconto > Decimal("0.00"):
            linhas.append(f"- Desconto aplicado: {ClienteService._formatar_moeda(desconto)}")
        if cashback_utilizado > Decimal("0.00"):
            linhas.append(f"- Cashback utilizado: {ClienteService._formatar_moeda(cashback_utilizado)}")

        linhas.append(f"- Cashback gerado nesta compra: {ClienteService._formatar_moeda(cashback_gerado)}")

        if credito and credito.data_expiracao:
            linhas.append(f"- Validade do cashback: {credito.data_expiracao.strftime('%d/%m/%Y')}")

        linhas.append(f"- Saldo atual da carteira: {ClienteService._formatar_moeda(carteira.saldo_disponivel)}")

        if getattr(venda, "itens", None):
            linhas.extend(["", "Itens da venda"])
            for item in venda.itens:
                produto_nome = item.produto.nome if getattr(item, "produto", None) else f"Produto #{item.produto_id}"
                linhas.append(
                    f"- {produto_nome} x{int(item.quantidade)}: {ClienteService._formatar_moeda(item.valor_total)}"
                )

        if getattr(venda, "pagamentos", None):
            linhas.extend(["", "Pagamentos"])
            for pagamento in venda.pagamentos:
                forma_nome = (
                    pagamento.forma_pagamento.nome
                    if getattr(pagamento, "forma_pagamento", None)
                    else f"Forma #{pagamento.forma_pagamento_id}"
                )
                linhas.append(f"- {forma_nome}: {ClienteService._formatar_moeda(pagamento.valor)}")

        linhas.extend([
            "",
            "Obrigado pela preferencia.",
        ])

        assunto = f"Comprovante da venda {venda.numero_unico} - {empresa_nome}"
        html_conteudo = render_template(
            "emails/venda_cliente.html",
            preheader=f"Venda {venda.numero_unico} concluida com cashback atualizado.",
            badge="Comprovante de venda",
            email_title="Sua compra foi concluida",
            email_subtitle=f"{empresa_nome} preparou um resumo elegante da sua venda e da carteira de cashback.",
            footer_note=f"Comprovante enviado por {empresa_nome} via OceanBlue.",
            saudacao=f"Ola {cliente.nome},",
            venda_numero=venda.numero_unico,
            data_venda=TimeService.format_br(venda.data_venda),
            total_pago=ClienteService._formatar_moeda(getattr(venda, "total", 0)),
            cashback_gerado=ClienteService._formatar_moeda(getattr(venda, "cashback_gerado", 0)),
            resumo_financeiro=ClienteService._montar_resumo_financeiro_email(venda, credito, carteira),
            itens=ClienteService._montar_itens_email(venda),
            pagamentos=ClienteService._montar_pagamentos_email(venda),
        )
        return assunto, "\n".join(linhas).strip(), html_conteudo

    @staticmethod
    def _montar_resumo_financeiro_email(venda, credito, carteira):
        resumo = [
            {"label": "Numero da venda", "value": venda.numero_unico},
            {"label": "Data da compra", "value": TimeService.format_br(venda.data_venda)},
            {"label": "Total pago", "value": ClienteService._formatar_moeda(getattr(venda, "total", 0))},
        ]

        desconto = ClienteService._to_decimal_value(getattr(venda, "desconto", 0))
        cashback_utilizado = ClienteService._to_decimal_value(getattr(venda, "cashback_utilizado", 0))
        cashback_gerado = ClienteService._to_decimal_value(getattr(venda, "cashback_gerado", 0))

        if desconto > Decimal("0.00"):
            resumo.append({"label": "Desconto aplicado", "value": ClienteService._formatar_moeda(desconto)})
        if cashback_utilizado > Decimal("0.00"):
            resumo.append({"label": "Cashback utilizado", "value": ClienteService._formatar_moeda(cashback_utilizado)})

        resumo.append({"label": "Cashback gerado", "value": ClienteService._formatar_moeda(cashback_gerado)})

        if credito and credito.data_expiracao:
            resumo.append({"label": "Validade do cashback", "value": credito.data_expiracao.strftime("%d/%m/%Y")})

        resumo.append({"label": "Saldo atual da carteira", "value": ClienteService._formatar_moeda(carteira.saldo_disponivel)})
        return resumo

    @staticmethod
    def _montar_itens_email(venda):
        itens = []
        for item in getattr(venda, "itens", None) or []:
            itens.append({
                "nome": item.produto.nome if getattr(item, "produto", None) else f"Produto #{item.produto_id}",
                "quantidade": int(item.quantidade),
                "valor_total": ClienteService._formatar_moeda(item.valor_total),
            })
        return itens

    @staticmethod
    def _montar_pagamentos_email(venda):
        pagamentos = []
        for pagamento in getattr(venda, "pagamentos", None) or []:
            pagamentos.append({
                "forma": (
                    pagamento.forma_pagamento.nome
                    if getattr(pagamento, "forma_pagamento", None)
                    else f"Forma #{pagamento.forma_pagamento_id}"
                ),
                "valor": ClienteService._formatar_moeda(pagamento.valor),
            })
        return pagamentos

    @staticmethod
    @atomic_operation
    def _aplicar_expiracoes_cliente(cliente_id, tenant_id):
        creditos_vencidos = ClienteRepository.listar_creditos_vencidos(cliente_id, tenant_id, TimeService.today_br())
        if not creditos_vencidos:
            return False

        carteira = ClienteService._obter_ou_criar_carteira(cliente_id, tenant_id)
        houve_alteracao = False
        for credito in creditos_vencidos:
            saldo = ClienteService._to_decimal_value(credito.saldo_disponivel)
            if saldo <= Decimal("0.00"):
                continue
            credito.saldo_disponivel = Decimal("0.00")
            credito.expirado_em = TimeService.now_utc_naive()
            carteira.saldo_disponivel = (
                ClienteService._to_decimal_value(carteira.saldo_disponivel) - saldo
            ).quantize(Decimal("0.01"))
            ClienteRepository.adicionar(
                MovimentoCarteiraCliente(
                    tenant_id=tenant_id,
                    carteira_id=carteira.id,
                    cliente_id=cliente_id,
                    credito_id=credito.id,
                    venda_id=credito.venda_origem_id,
                    funcionario_id=None,
                    tipo=TipoMovimentoCarteiraCliente.EXPIRACAO,
                    valor=saldo,
                    descricao=f"Expiracao automatica do cashback da venda {credito.venda_origem.numero_unico if credito.venda_origem else credito.venda_origem_id}.",
                    data_movimento=TimeService.now_utc_naive(),
                )
            )
            houve_alteracao = True

        if houve_alteracao:
            ClienteRepository.flush()
        return houve_alteracao

    @staticmethod
    def preparar_uso_cashback(cliente_id, empresa_id, valor_solicitado, tenant_id, valor_base_venda=None):
        valor = ClienteService._to_non_negative_decimal(valor_solicitado, "cashback solicitado")
        configuracao = ClienteService._obter_ou_criar_configuracao_empresa(empresa_id, tenant_id)

        if valor <= Decimal("0.00"):
            return {
                "cliente": None,
                "carteira": None,
                "configuracao": configuracao,
                "valor_utilizado": Decimal("0.00"),
                "alocacoes": [],
            }

        cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
        if not cliente or not cliente.ativo:
            raise ValueError("Cliente nao encontrado para uso de cashback.")

        if not configuracao.cashback_ativo:
            raise ValueError("O cashback nao esta habilitado para esta empresa.")

        ClienteService._aplicar_expiracoes_cliente(cliente.id, tenant_id)
        carteira = ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)

        if valor < ClienteService._to_decimal_value(configuracao.cashback_valor_minimo_resgate):
            raise ValueError("O valor informado esta abaixo do minimo configurado para uso do cashback.")

        if valor_base_venda is not None:
            limite_resgate = ClienteService.calcular_limite_resgate_cashback(
                configuracao,
                valor_base_venda,
            )
            if valor > limite_resgate:
                percentual_limite = ClienteService._to_decimal_value(
                    getattr(configuracao, "cashback_percentual_limite_resgate_venda", 100)
                )
                raise ValueError(
                    "O cashback utilizado nao pode ultrapassar "
                    f"{str(percentual_limite)}% do valor liquido da venda para esta empresa."
                )

        saldo_disponivel = ClienteService._to_decimal_value(carteira.saldo_disponivel)
        if saldo_disponivel < valor:
            raise ValueError("Saldo de cashback insuficiente para esta venda.")

        creditos = ClienteRepository.listar_creditos_disponiveis(cliente.id, tenant_id)
        restante = valor
        alocacoes = []

        for credito in creditos:
            saldo_credito = ClienteService._to_decimal_value(credito.saldo_disponivel)
            if saldo_credito <= Decimal("0.00"):
                continue
            consumido = min(saldo_credito, restante)
            if consumido <= Decimal("0.00"):
                continue
            alocacoes.append({"credito": credito, "valor": consumido})
            restante = (restante - consumido).quantize(Decimal("0.01"))
            if restante <= Decimal("0.00"):
                break

        if restante > Decimal("0.00"):
            raise ValueError("Nao foi possivel compor o valor solicitado com os creditos disponiveis.")

        return {
            "cliente": cliente,
            "carteira": carteira,
            "configuracao": configuracao,
            "valor_utilizado": valor,
            "alocacoes": alocacoes,
        }

    @staticmethod
    @atomic_operation
    def processar_cashback_da_venda(
        venda,
        cliente_id,
        empresa_id,
        valor_cashback_utilizado,
        tenant_id,
        funcionario_id,
        cashback_ativado=True,
    ):
        if venda.tenant_id != tenant_id or venda.empresa_id != empresa_id:
            raise PermissionError("Venda indisponivel neste escopo.")
        digest = hashlib.sha256(json.dumps([cliente_id, empresa_id, str(valor_cashback_utilizado), cashback_ativado]).encode()).hexdigest()
        configuracao = ClienteService._obter_ou_criar_configuracao_empresa(empresa_id, tenant_id)
        if venda.cashback_processado:
            if venda.cashback_payload != digest:
                raise ValueError("Cashback ja processado; payload divergente ou venda historica.")
            return {"cliente": venda.cliente, "configuracao": configuracao,
                "cashback_utilizado": str(venda.cashback_utilizado), "cashback_gerado": str(venda.cashback_gerado)}
        preparacao = (
            ClienteService.preparar_uso_cashback(
                cliente_id=cliente_id,
                empresa_id=empresa_id,
                valor_solicitado=valor_cashback_utilizado,
                tenant_id=tenant_id,
                valor_base_venda=(
                    ClienteService._to_decimal_value(venda.total)
                    + ClienteService._to_decimal_value(valor_cashback_utilizado)
                ),
            )
            if cliente_id and cashback_ativado
            else {
                "cliente": None,
                "carteira": None,
                "configuracao": configuracao,
                "valor_utilizado": Decimal("0.00"),
                "alocacoes": [],
            }
        )

        cliente = preparacao["cliente"] if cliente_id else None
        carteira = preparacao["carteira"] if cliente_id else None
        if cliente_id and not cliente:
            cliente = ClienteRepository.buscar_cliente_por_id(cliente_id, tenant_id)
            if not cliente or not cliente.ativo:
                raise ValueError("Cliente nao encontrado para vinculo da venda.")
        valor_utilizado = ClienteService._to_decimal_value(preparacao["valor_utilizado"])
        percentual_gerado = Decimal("0.00")
        valor_gerado = Decimal("0.00")

        if cliente:
            venda.cliente_id = cliente.id

        if valor_utilizado > Decimal("0.00"):
            if not carteira:
                raise ValueError("Carteira do cliente nao encontrada.")

            for alocacao in preparacao["alocacoes"]:
                credito = alocacao["credito"]
                valor = ClienteService._to_decimal_value(alocacao["valor"])
                credito.saldo_disponivel = (
                    ClienteService._to_decimal_value(credito.saldo_disponivel) - valor
                ).quantize(Decimal("0.01"))
                carteira.saldo_disponivel = (
                    ClienteService._to_decimal_value(carteira.saldo_disponivel) - valor
                ).quantize(Decimal("0.01"))
                ClienteRepository.adicionar(
                    MovimentoCarteiraCliente(
                        tenant_id=tenant_id,
                        carteira_id=carteira.id,
                        cliente_id=cliente.id,
                        credito_id=credito.id,
                        venda_id=venda.id,
                        funcionario_id=funcionario_id,
                        tipo=TipoMovimentoCarteiraCliente.DEBITO,
                        valor=valor,
                        descricao=f"Uso de cashback na venda {venda.numero_unico}.",
                        data_movimento=TimeService.now_utc_naive(),
                    )
                )

            venda.cashback_utilizado = valor_utilizado

        if cliente and configuracao.cashback_ativo and cashback_ativado:
            percentual_gerado = ClienteService._to_decimal_value(configuracao.cashback_percentual)
            total_venda = ClienteService._to_decimal_value(venda.total)
            if percentual_gerado > Decimal("0.00") and total_venda > Decimal("0.00"):
                valor_gerado = (total_venda * percentual_gerado / Decimal("100")).quantize(Decimal("0.01"))
                if valor_gerado > Decimal("0.00"):
                    carteira = carteira or ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)
                    credito = CreditoCashbackCliente(
                        tenant_id=tenant_id,
                        carteira_id=carteira.id,
                        cliente_id=cliente.id,
                        empresa_id=empresa_id,
                        venda_origem_id=venda.id,
                        valor_original=valor_gerado,
                        saldo_disponivel=valor_gerado,
                        data_expiracao=TimeService.today_br() + timedelta(days=int(configuracao.cashback_validade_dias or 30)),
                        observacao=f"Cashback gerado automaticamente pela venda {venda.numero_unico}.",
                    )
                    carteira.saldo_disponivel = (
                        ClienteService._to_decimal_value(carteira.saldo_disponivel) + valor_gerado
                    ).quantize(Decimal("0.01"))
                    ClienteRepository.adicionar(credito)
                    ClienteRepository.flush()
                    ClienteRepository.adicionar(
                        MovimentoCarteiraCliente(
                            tenant_id=tenant_id,
                            carteira_id=carteira.id,
                            cliente_id=cliente.id,
                            credito_id=credito.id,
                            venda_id=venda.id,
                            funcionario_id=funcionario_id,
                            tipo=TipoMovimentoCarteiraCliente.CREDITO,
                            valor=valor_gerado,
                            descricao=f"Cashback gerado pela venda {venda.numero_unico}.",
                            data_movimento=TimeService.now_utc_naive(),
                        )
                    )

        venda.cashback_gerado = valor_gerado
        venda.cashback_percentual_aplicado = percentual_gerado
        venda.cashback_processado = True
        venda.cashback_payload = digest

        return {
            "cliente": cliente,
            "configuracao": configuracao,
            "cashback_utilizado": str(valor_utilizado),
            "cashback_gerado": str(valor_gerado),
        }

    @staticmethod
    def reverter_cashback_venda(venda, tenant_id, funcionario_id):
        cliente = getattr(venda, "cliente", None)
        if not cliente:
            return

        carteira = ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)
        movimentos_debito = ClienteRepository.listar_movimentos_carteira_por_venda(
            venda_id=venda.id,
            tenant_id=tenant_id,
            tipo=TipoMovimentoCarteiraCliente.DEBITO,
        )

        for movimento in movimentos_debito:
            credito = movimento.credito
            valor = ClienteService._to_decimal_value(movimento.valor)
            restored = sum((record.valor for record in MovimentoCarteiraCliente.query.filter_by(
                tenant_id=tenant_id, venda_id=venda.id, credito_id=movimento.credito_id,
                tipo=TipoMovimentoCarteiraCliente.ESTORNO).all()), Decimal("0.00"))
            valor -= restored
            if valor <= 0:
                continue
            if credito:
                credito.saldo_disponivel = (
                    ClienteService._to_decimal_value(credito.saldo_disponivel) + valor
                ).quantize(Decimal("0.01"))
            carteira.saldo_disponivel = (
                ClienteService._to_decimal_value(carteira.saldo_disponivel) + valor
            ).quantize(Decimal("0.01"))
            ClienteRepository.adicionar(
                MovimentoCarteiraCliente(
                    tenant_id=tenant_id,
                    carteira_id=carteira.id,
                    cliente_id=cliente.id,
                    credito_id=credito.id if credito else None,
                    venda_id=venda.id,
                    funcionario_id=funcionario_id,
                    tipo=TipoMovimentoCarteiraCliente.ESTORNO,
                    valor=valor,
                    descricao=f"Restituicao de cashback pelo cancelamento da venda {venda.numero_unico}.",
                    data_movimento=TimeService.now_utc_naive(),
                )
            )

        credito_gerado = ClienteRepository.buscar_credito_por_venda_origem(venda.id, tenant_id)
        ClienteService._aplicar_expiracoes_cliente(cliente.id, tenant_id)
        if not credito_gerado:
            return
        if credito_gerado.cancelado_em:
            return
        if credito_gerado.expirado_em and not ClienteService._credito_tem_consumo(credito_gerado, tenant_id):
            credito_gerado.cancelado_em = TimeService.now_utc_naive()
            return

        saldo_credito = ClienteService._to_decimal_value(credito_gerado.saldo_disponivel)
        if saldo_credito < ClienteService._to_decimal_value(credito_gerado.valor_original):
            raise ValueError("Nao e possivel cancelar a venda porque o cashback gerado por ela ja foi utilizado.")

        if saldo_credito > Decimal("0.00"):
            carteira.saldo_disponivel = (
                ClienteService._to_decimal_value(carteira.saldo_disponivel) - saldo_credito
            ).quantize(Decimal("0.01"))
            credito_gerado.saldo_disponivel = Decimal("0.00")
            credito_gerado.cancelado_em = TimeService.now_utc_naive()
            ClienteRepository.adicionar(
                MovimentoCarteiraCliente(
                    tenant_id=tenant_id,
                    carteira_id=carteira.id,
                    cliente_id=cliente.id,
                    credito_id=credito_gerado.id,
                    venda_id=venda.id,
                    funcionario_id=funcionario_id,
                    tipo=TipoMovimentoCarteiraCliente.ESTORNO,
                    valor=ClienteService._to_decimal_value(credito_gerado.valor_original),
                    descricao=f"Estorno do cashback gerado pela venda {venda.numero_unico}.",
                    data_movimento=TimeService.now_utc_naive(),
                )
            )

    @staticmethod
    def calcular_limite_resgate_cashback(configuracao, valor_base_venda):
        base_venda = ClienteService._to_decimal_value(valor_base_venda)
        percentual_limite = ClienteService._to_decimal_value(
            getattr(configuracao, "cashback_percentual_limite_resgate_venda", 100)
        )

        if base_venda <= Decimal("0.00") or percentual_limite <= Decimal("0.00"):
            return Decimal("0.00")

        return (base_venda * percentual_limite / Decimal("100")).quantize(Decimal("0.01"))

    @staticmethod
    def restaurar_cashback_parcial_da_venda(venda, valor_restaurar, tenant_id, funcionario_id):
        valor = ClienteService._to_non_negative_decimal(valor_restaurar, "cashback a restituir")
        if valor <= Decimal("0.00") or not getattr(venda, "cliente", None):
            return Decimal("0.00")

        cliente = venda.cliente
        carteira = ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)
        movimentos_debito = ClienteRepository.listar_movimentos_carteira_por_venda(
            venda_id=venda.id,
            tenant_id=tenant_id,
            tipo=TipoMovimentoCarteiraCliente.DEBITO,
        )
        total_debitos = sum(
            (ClienteService._to_decimal_value(item.valor) for item in movimentos_debito),
            Decimal("0.00"),
        )
        if total_debitos <= Decimal("0.00"):
            return Decimal("0.00")

        balances = []
        for movement in movimentos_debito:
            restored = sum((record.valor for record in MovimentoCarteiraCliente.query.filter_by(
                tenant_id=tenant_id, venda_id=venda.id, credito_id=movement.credito_id,
                tipo=TipoMovimentoCarteiraCliente.ESTORNO,
            ).all()), Decimal("0.00"))
            balances.append(movement.valor - restored)
        portions = allocate_money(valor, balances)
        for movimento, parcela in zip(movimentos_debito, portions):
            if parcela <= Decimal("0.00"):
                continue

            credito = movimento.credito
            if credito:
                credito.saldo_disponivel = (
                    ClienteService._to_decimal_value(credito.saldo_disponivel) + parcela
                ).quantize(Decimal("0.01"))
            carteira.saldo_disponivel = (
                ClienteService._to_decimal_value(carteira.saldo_disponivel) + parcela
            ).quantize(Decimal("0.01"))
            ClienteRepository.adicionar(
                MovimentoCarteiraCliente(
                    tenant_id=tenant_id,
                    carteira_id=carteira.id,
                    cliente_id=cliente.id,
                    credito_id=credito.id if credito else None,
                    venda_id=venda.id,
                    funcionario_id=funcionario_id,
                    tipo=TipoMovimentoCarteiraCliente.ESTORNO,
                    valor=parcela,
                    descricao=f"Restituicao parcial de cashback pela devolucao de item da venda {venda.numero_unico}.",
                    data_movimento=TimeService.now_utc_naive(),
                )
            )
        ClienteRepository.flush()
        ClienteService._aplicar_expiracoes_cliente(cliente.id, tenant_id)
        return valor

    @staticmethod
    def _credito_tem_consumo(credito, tenant_id):
        debits = MovimentoCarteiraCliente.query.filter_by(tenant_id=tenant_id, credito_id=credito.id,
            tipo=TipoMovimentoCarteiraCliente.DEBITO).all()
        for debit in debits:
            restored = sum((record.valor for record in MovimentoCarteiraCliente.query.filter_by(
                tenant_id=tenant_id, credito_id=credito.id, venda_id=debit.venda_id,
                tipo=TipoMovimentoCarteiraCliente.ESTORNO).all()), Decimal("0.00"))
            if debit.valor > restored:
                return True
        return False

    @staticmethod
    def ajustar_cashback_gerado_por_cancelamento_item(venda, valor_cancelamento_liquido, tenant_id, funcionario_id):
        cliente = getattr(venda, "cliente", None)
        percentual = ClienteService._to_decimal_value(getattr(venda, "cashback_percentual_aplicado", 0))
        if not cliente or percentual <= Decimal("0.00"):
            return Decimal("0.00")

        valor_cancelamento = ClienteService._to_non_negative_decimal(valor_cancelamento_liquido, "valor de cancelamento")
        if valor_cancelamento <= Decimal("0.00"):
            return Decimal("0.00")

        base = ClienteService._to_decimal_value(venda.total) + ClienteService._to_decimal_value(venda.cashback_utilizado)
        restante = max(base - ClienteService._to_decimal_value(venda.valor_cancelado), Decimal("0.00"))
        original = (ClienteService._to_decimal_value(venda.total) * percentual / Decimal("100")).quantize(Decimal("0.01"))
        alvo = (original * restante / base).quantize(Decimal("0.01")) if base else Decimal("0.00")
        valor_estorno = ClienteService._to_decimal_value(venda.cashback_gerado) - alvo
        if valor_estorno <= Decimal("0.00"):
            return Decimal("0.00")

        credito = ClienteRepository.buscar_credito_por_venda_origem(venda.id, tenant_id)
        if not credito:
            return Decimal("0.00")

        saldo_credito = ClienteService._to_decimal_value(credito.saldo_disponivel)
        if credito.expirado_em and not ClienteService._credito_tem_consumo(credito, tenant_id):
            credito.valor_original -= valor_estorno
            venda.cashback_gerado -= valor_estorno
            if credito.valor_original == 0:
                credito.cancelado_em = TimeService.now_utc_naive()
            return valor_estorno
        if saldo_credito < valor_estorno:
            raise ValueError("Nao e possivel cancelar o item porque o cashback gerado por esta venda ja foi utilizado.")

        carteira = ClienteService._obter_ou_criar_carteira(cliente.id, tenant_id)
        credito.valor_original = (
            ClienteService._to_decimal_value(credito.valor_original) - valor_estorno
        ).quantize(Decimal("0.01"))
        credito.saldo_disponivel = (
            ClienteService._to_decimal_value(credito.saldo_disponivel) - valor_estorno
        ).quantize(Decimal("0.01"))
        carteira.saldo_disponivel = (
            ClienteService._to_decimal_value(carteira.saldo_disponivel) - valor_estorno
        ).quantize(Decimal("0.01"))
        venda.cashback_gerado = (
            ClienteService._to_decimal_value(getattr(venda, "cashback_gerado", 0)) - valor_estorno
        ).quantize(Decimal("0.01"))
        ClienteRepository.adicionar(
            MovimentoCarteiraCliente(
                tenant_id=tenant_id,
                carteira_id=carteira.id,
                cliente_id=cliente.id,
                credito_id=credito.id,
                venda_id=venda.id,
                funcionario_id=funcionario_id,
                tipo=TipoMovimentoCarteiraCliente.ESTORNO,
                valor=valor_estorno,
                descricao=f"Reducao do cashback gerado pela venda {venda.numero_unico} apos cancelamento parcial.",
                data_movimento=TimeService.now_utc_naive(),
            )
        )
        return valor_estorno

    @staticmethod
    def calcular_saldo_disponivel(cliente_id, tenant_id):
        if ClienteService._aplicar_expiracoes_cliente(cliente_id, tenant_id):
            ClienteRepository.salvar()
        carteira = ClienteService._obter_ou_criar_carteira(cliente_id, tenant_id)
        return ClienteService._to_decimal_value(carteira.saldo_disponivel)

    @staticmethod
    def _formatar_moeda(value):
        valor = ClienteService._to_decimal_value(value).quantize(Decimal("0.01"))
        sinal = "-" if valor < Decimal("0.00") else ""
        valor_abs = abs(valor)
        inteiro, decimal = f"{valor_abs:.2f}".split(".")
        inteiro_formatado = f"{int(inteiro):,}".replace(",", ".")
        return f"{sinal}R$ {inteiro_formatado},{decimal}"

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "on", "sim", "yes"}

    @staticmethod
    def _to_tipo_pessoa(value):
        if not value:
            return TipoPessoa.FISICA
        try:
            return TipoPessoa[(value or "").strip().upper()]
        except KeyError as exc:
            raise ValueError("Tipo de pessoa invalido.") from exc

    @staticmethod
    def _to_canal(value):
        if isinstance(value, CanalMensagemCliente):
            return value
        try:
            return CanalMensagemCliente[(value or "").strip().upper()]
        except KeyError as exc:
            raise ValueError("Canal de mensagem invalido.") from exc

    @staticmethod
    def _to_int(value, field_name):
        from app.services.money_service import positive_integer
        return positive_integer(value, field_name)

    @staticmethod
    def _to_positive_int(value, field_name):
        if value in (None, ""):
            raise ValueError(f"Informe {field_name}.")
        try:
            valor = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Valor invalido para {field_name}.") from exc
        if valor <= 0:
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")
        return valor

    @staticmethod
    def _to_non_negative_int(value, field_name):
        if value in (None, ""):
            return 0
        try:
            valor = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Valor invalido para {field_name}.") from exc
        if valor < 0:
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")
        return valor

    @staticmethod
    def _to_non_negative_decimal(value, field_name, maximo=None):
        if value in (None, ""):
            return Decimal("0.00")
        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Valor invalido para {field_name}.") from exc
        if valor < 0:
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")
        valor = valor.quantize(Decimal("0.01"))
        if maximo is not None and valor > maximo:
            raise ValueError(f"{field_name.capitalize()} nao pode ser maior que {str(maximo)}.")
        return valor

    @staticmethod
    def _to_decimal_value(value):
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.01"))
        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _to_optional_date(value):
        if value in (None, ""):
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("Data invalida. Use o formato YYYY-MM-DD.") from exc

    @staticmethod
    def _normalizar_documento(value):
        digits = "".join(char for char in str(value or "") if char.isdigit())
        return digits or None

    @staticmethod
    def _normalizar_telefone(value):
        texto = str(value or "").strip()
        if not texto:
            return None
        digits = "".join(char for char in texto if char.isdigit() or char == "+")
        return digits or texto

    @staticmethod
    def _normalizar_email(value):
        texto = (value or "").strip().lower()
        return texto or None

    @staticmethod
    def _normalizar_url(value):
        texto = (value or "").strip()
        return texto or None

    @staticmethod
    def _obter_ou_criar_carteira(cliente_id, tenant_id):
        carteira = ClienteRepository.obter_carteira_por_cliente(cliente_id, tenant_id)
        if carteira:
            return carteira

        carteira = CarteiraCliente(
            tenant_id=tenant_id,
            cliente_id=cliente_id,
            saldo_disponivel=Decimal("0.00"),
        )
        ClienteRepository.adicionar(carteira)
        ClienteRepository.flush()
        return carteira

    @staticmethod
    def _obter_ou_criar_configuracao_empresa(empresa_id, tenant_id):
        configuracao = ClienteRepository.buscar_configuracao_empresa(empresa_id, tenant_id)
        if configuracao:
            return configuracao

        configuracao = ConfiguracaoClienteEmpresa(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            cashback_ativo=False,
            cashback_percentual=Decimal("0.00"),
            cashback_percentual_limite_resgate_venda=Decimal("100.00"),
            cashback_validade_dias=30,
            cashback_valor_minimo_resgate=Decimal("0.00"),
            cancelamento_venda_limite_horas=24,
            cancelamento_item_limite_horas=24,
            cancelamento_movimento_limite_horas=24,
            email_habilitado=False,
            smtp_port=587,
            smtp_tls=True,
            smtp_ssl=False,
            whatsapp_habilitado=False,
            sms_habilitado=False,
            request_timeout_segundos=15,
        )
        ClienteRepository.adicionar(configuracao)
        ClienteRepository.flush()
        return configuracao

    @staticmethod
    def _clonar_configuracao_empresa(configuracao):
        clone = ConfiguracaoClienteEmpresa(
            tenant_id=configuracao.tenant_id,
            empresa_id=configuracao.empresa_id,
            cashback_ativo=bool(configuracao.cashback_ativo),
            cashback_percentual=ClienteService._to_decimal_value(configuracao.cashback_percentual),
            cashback_percentual_limite_resgate_venda=ClienteService._to_decimal_value(
                getattr(configuracao, "cashback_percentual_limite_resgate_venda", 100)
            ),
            cashback_validade_dias=int(configuracao.cashback_validade_dias or 30),
            cashback_valor_minimo_resgate=ClienteService._to_decimal_value(configuracao.cashback_valor_minimo_resgate),
            cancelamento_venda_limite_horas=int(configuracao.cancelamento_venda_limite_horas or 24),
            cancelamento_item_limite_horas=int(configuracao.cancelamento_item_limite_horas or 24),
            cancelamento_movimento_limite_horas=int(configuracao.cancelamento_movimento_limite_horas or 24),
            email_habilitado=bool(configuracao.email_habilitado),
            email_remetente=configuracao.email_remetente,
            email_remetente_nome=configuracao.email_remetente_nome,
            smtp_host=configuracao.smtp_host,
            smtp_port=int(configuracao.smtp_port or 587),
            smtp_usuario=configuracao.smtp_usuario,
            smtp_senha=FieldCrypto.decrypt(configuracao.smtp_senha),
            smtp_tls=bool(configuracao.smtp_tls),
            smtp_ssl=bool(configuracao.smtp_ssl),
            whatsapp_habilitado=bool(configuracao.whatsapp_habilitado),
            whatsapp_api_url=configuracao.whatsapp_api_url,
            whatsapp_token=FieldCrypto.decrypt(configuracao.whatsapp_token),
            whatsapp_remetente=configuracao.whatsapp_remetente,
            sms_habilitado=bool(configuracao.sms_habilitado),
            sms_api_url=configuracao.sms_api_url,
            sms_token=FieldCrypto.decrypt(configuracao.sms_token),
            sms_remetente=configuracao.sms_remetente,
            request_timeout_segundos=int(configuracao.request_timeout_segundos or 15),
        )
        empresa = getattr(configuracao, "empresa", None)
        clone._empresa_nome_fallback = empresa.nome_fantasia if empresa else getattr(configuracao, "_empresa_nome_fallback", None)
        return clone

    @staticmethod
    def _aplicar_payload_configuracao(configuracao, data, encrypt_sensitive=True):
        configuracao.cashback_ativo = ClienteService._to_bool(data.get("cashback_ativo", configuracao.cashback_ativo))
        configuracao.cashback_percentual = ClienteService._to_non_negative_decimal(
            data.get("cashback_percentual", configuracao.cashback_percentual),
            "percentual de cashback",
            maximo=Decimal("100.00"),
        )
        configuracao.cashback_percentual_limite_resgate_venda = ClienteService._to_non_negative_decimal(
            data.get(
                "cashback_percentual_limite_resgate_venda",
                getattr(configuracao, "cashback_percentual_limite_resgate_venda", Decimal("100.00")),
            ),
            "limite percentual de resgate por venda",
            maximo=Decimal("100.00"),
        )
        configuracao.cashback_validade_dias = ClienteService._to_positive_int(
            data.get("cashback_validade_dias", configuracao.cashback_validade_dias),
            "validade do cashback",
        )
        configuracao.cashback_valor_minimo_resgate = ClienteService._to_non_negative_decimal(
            data.get("cashback_valor_minimo_resgate", configuracao.cashback_valor_minimo_resgate),
            "valor minimo para resgate",
        )
        configuracao.cancelamento_venda_limite_horas = ClienteService._to_non_negative_int(
            data.get("cancelamento_venda_limite_horas", configuracao.cancelamento_venda_limite_horas),
            "tempo de cancelamento da venda",
        )
        configuracao.cancelamento_item_limite_horas = ClienteService._to_non_negative_int(
            data.get("cancelamento_item_limite_horas", configuracao.cancelamento_item_limite_horas),
            "tempo de cancelamento do item",
        )
        configuracao.cancelamento_movimento_limite_horas = ClienteService._to_non_negative_int(
            data.get("cancelamento_movimento_limite_horas", configuracao.cancelamento_movimento_limite_horas),
            "tempo de cancelamento da movimentacao",
        )
        configuracao.email_habilitado = ClienteService._to_bool(data.get("email_habilitado", configuracao.email_habilitado))
        configuracao.email_remetente = ClienteService._normalizar_email(data.get("email_remetente", configuracao.email_remetente))
        configuracao.email_remetente_nome = (data.get("email_remetente_nome", configuracao.email_remetente_nome) or "").strip() or None
        configuracao.smtp_host = (data.get("smtp_host", configuracao.smtp_host) or "").strip() or None
        configuracao.smtp_port = ClienteService._to_positive_int(data.get("smtp_port", configuracao.smtp_port or 587), "porta SMTP")
        configuracao.smtp_usuario = (data.get("smtp_usuario", configuracao.smtp_usuario) or "").strip() or None
        if "smtp_senha" in data:
            smtp_senha = (data.get("smtp_senha") or "").strip() or None
            configuracao.smtp_senha = FieldCrypto.encrypt(smtp_senha) if encrypt_sensitive else smtp_senha
        configuracao.smtp_tls = ClienteService._to_bool(data.get("smtp_tls", configuracao.smtp_tls))
        configuracao.smtp_ssl = ClienteService._to_bool(data.get("smtp_ssl", configuracao.smtp_ssl))
        if ClienteService._to_bool(data.get("whatsapp_habilitado", False)):
            raise ValueError("WhatsApp desativado neste escopo; utilize email.")
        configuracao.whatsapp_habilitado = False
        configuracao.whatsapp_api_url = ClienteService._normalizar_url(data.get("whatsapp_api_url", configuracao.whatsapp_api_url))
        if "whatsapp_token" in data:
            whatsapp_token = (data.get("whatsapp_token") or "").strip() or None
            configuracao.whatsapp_token = FieldCrypto.encrypt(whatsapp_token) if encrypt_sensitive else whatsapp_token
        configuracao.whatsapp_remetente = (data.get("whatsapp_remetente", configuracao.whatsapp_remetente) or "").strip() or None
        configuracao.sms_habilitado = ClienteService._to_bool(data.get("sms_habilitado", configuracao.sms_habilitado))
        configuracao.sms_api_url = ClienteService._normalizar_url(data.get("sms_api_url", configuracao.sms_api_url))
        if "sms_token" in data:
            sms_token = (data.get("sms_token") or "").strip() or None
            configuracao.sms_token = FieldCrypto.encrypt(sms_token) if encrypt_sensitive else sms_token
        configuracao.sms_remetente = (data.get("sms_remetente", configuracao.sms_remetente) or "").strip() or None
        configuracao.request_timeout_segundos = ClienteService._to_positive_int(
            data.get("request_timeout_segundos", configuracao.request_timeout_segundos or 15),
            "timeout das integracoes",
        )

        ClienteService._validar_consistencia_configuracao(configuracao)

    @staticmethod
    def _obter_destinatario_cliente(cliente, canal):
        if canal == CanalMensagemCliente.EMAIL:
            destino = cliente.email
        elif canal == CanalMensagemCliente.WHATSAPP:
            destino = cliente.whatsapp or cliente.telefone
        else:
            destino = cliente.telefone or cliente.whatsapp

        destinatario = (destino or "").strip()
        if not destinatario:
            raise ValueError("O cliente nao possui contato cadastrado para o canal selecionado.")
        return destinatario

    @staticmethod
    def _validar_canal_habilitado(configuracao, canal):
        if canal == CanalMensagemCliente.EMAIL:
            if not configuracao.email_habilitado:
                raise ValueError("Canal de email desabilitado para esta empresa.")
            if not configuracao.smtp_host:
                raise ValueError("Host SMTP nao configurado.")
            if not configuracao.email_remetente:
                raise ValueError("Email remetente nao configurado.")
            return

        if canal == CanalMensagemCliente.WHATSAPP:
            if not configuracao.whatsapp_habilitado:
                raise ValueError("Canal de WhatsApp desabilitado para esta empresa.")
            if not configuracao.whatsapp_api_url:
                raise ValueError("Endpoint de WhatsApp nao configurado.")
            return

        if not configuracao.sms_habilitado:
            raise ValueError("Canal de SMS desabilitado para esta empresa.")
        if not configuracao.sms_api_url:
            raise ValueError("Endpoint de SMS nao configurado.")

    @staticmethod
    def _validar_opt_in(cliente, canal):
        if canal == CanalMensagemCliente.EMAIL and not cliente.aceita_email:
            raise ValueError("O cliente nao autorizou comunicacao por email.")
        if canal == CanalMensagemCliente.SMS and not cliente.aceita_sms:
            raise ValueError("O cliente nao autorizou comunicacao por SMS.")
        if canal == CanalMensagemCliente.WHATSAPP and not cliente.aceita_whatsapp:
            raise ValueError("O cliente nao autorizou comunicacao por WhatsApp.")

    @staticmethod
    def _validar_consistencia_configuracao(configuracao):
        if configuracao.smtp_ssl and configuracao.smtp_tls:
            raise ValueError("Escolha apenas um modo de seguranca SMTP: TLS ou SSL.")

        if configuracao.email_habilitado:
            if not configuracao.smtp_host:
                raise ValueError("Informe o host SMTP para habilitar o envio de emails.")
            if not configuracao.email_remetente:
                raise ValueError("Informe o email remetente para habilitar o envio de emails.")

        if configuracao.whatsapp_habilitado and not configuracao.whatsapp_api_url:
            raise ValueError("Informe o endpoint HTTP do WhatsApp para habilitar o canal.")

        if configuracao.sms_habilitado and not configuracao.sms_api_url:
            raise ValueError("Informe o endpoint HTTP do SMS para habilitar o canal.")

    @staticmethod
    def _auditar_consentimento(cliente, before, source):
        from flask import g, has_request_context
        from app.services.cliente_privacidade_service import ClientePrivacidadeService
        after = {field: getattr(cliente, field) for field in ("aceita_email", "aceita_sms", "aceita_whatsapp")}
        if before != after:
            actor = getattr(g, "auth_user", None) if has_request_context() else None
            ClientePrivacidadeService.auditar(cliente, actor.id if actor else None, "CLIENTE_CONSENTIMENTO",
                {"antes": before, "depois": after, "origem": source})

    @staticmethod
    def serializar_cliente(cliente):
        carteira = getattr(cliente, "carteira", None)
        vendas = getattr(cliente, "vendas", []) or []
        total_vendido = sum(
            (ClienteService._to_decimal_value(item.total) for item in vendas),
            Decimal("0.00"),
        )

        return {
            "id": cliente.id,
            "nome": cliente.nome,
            "documento": cliente.documento,
            "tipo_pessoa": cliente.tipo_pessoa.value if cliente.tipo_pessoa else None,
            "email": cliente.email,
            "telefone": cliente.telefone,
            "whatsapp": cliente.whatsapp,
            "data_nascimento": cliente.data_nascimento.isoformat() if cliente.data_nascimento else None,
            "observacao": cliente.observacao,
            "aceita_email": bool(cliente.aceita_email),
            "aceita_sms": bool(cliente.aceita_sms),
            "aceita_whatsapp": bool(cliente.aceita_whatsapp),
            "ativo": bool(cliente.ativo),
            "saldo_cashback": str(ClienteService._to_decimal_value(carteira.saldo_disponivel if carteira else 0)),
            "quantidade_vendas": len(vendas),
            "total_vendido": str(total_vendido.quantize(Decimal("0.01"))),
            "criado_em": TimeService.serialize_utc_iso(cliente.criado_em),
        }

    @staticmethod
    def serializar_credito(credito):
        return {
            "id": credito.id,
            "empresa_id": credito.empresa_id,
            "empresa_nome": credito.empresa.nome_fantasia if credito.empresa else None,
            "venda_origem_id": credito.venda_origem_id,
            "venda_origem_numero": credito.venda_origem.numero_unico if credito.venda_origem else None,
            "valor_original": str(ClienteService._to_decimal_value(credito.valor_original)),
            "saldo_disponivel": str(ClienteService._to_decimal_value(credito.saldo_disponivel)),
            "data_expiracao": credito.data_expiracao.isoformat() if credito.data_expiracao else None,
            "cancelado_em": TimeService.serialize_utc_iso(credito.cancelado_em),
            "expirado_em": TimeService.serialize_utc_iso(credito.expirado_em),
            "observacao": credito.observacao,
        }

    @staticmethod
    def serializar_movimento_carteira(item):
        return {
            "id": item.id,
            "tipo": item.tipo.value if item.tipo else None,
            "valor": str(ClienteService._to_decimal_value(item.valor)),
            "descricao": item.descricao,
            "venda_id": item.venda_id,
            "credito_id": item.credito_id,
            "funcionario_nome": item.funcionario.nome if item.funcionario else None,
            "data_movimento": TimeService.serialize_utc_iso(item.data_movimento),
        }

    @staticmethod
    def serializar_venda_cliente(venda):
        return {
            "id": venda.id,
            "numero_unico": venda.numero_unico,
            "empresa_id": venda.empresa_id,
            "empresa_nome": venda.empresa.nome_fantasia if venda.empresa else None,
            "status": venda.status.value if venda.status else None,
            "subtotal": str(ClienteService._to_decimal_value(venda.subtotal)),
            "desconto": str(ClienteService._to_decimal_value(venda.desconto)),
            "cashback_utilizado": str(ClienteService._to_decimal_value(getattr(venda, "cashback_utilizado", 0))),
            "cashback_gerado": str(ClienteService._to_decimal_value(getattr(venda, "cashback_gerado", 0))),
            "valor_cancelado": str(ClienteService._to_decimal_value(getattr(venda, "valor_cancelado", 0))),
            "total": str(ClienteService._to_decimal_value(venda.total)),
            "data_venda": TimeService.serialize_utc_iso(venda.data_venda),
        }

    @staticmethod
    def serializar_configuracao_empresa(configuracao):
        empresa_nome = configuracao.empresa.nome_fantasia if configuracao.empresa else getattr(configuracao, "_empresa_nome_fallback", None)
        return {
            "id": configuracao.id,
            "empresa_id": configuracao.empresa_id,
            "empresa_nome": empresa_nome,
            "cashback_ativo": bool(configuracao.cashback_ativo),
            "cashback_percentual": str(ClienteService._to_decimal_value(configuracao.cashback_percentual)),
            "cashback_percentual_limite_resgate_venda": str(
                ClienteService._to_decimal_value(getattr(configuracao, "cashback_percentual_limite_resgate_venda", 100))
            ),
            "cashback_validade_dias": int(configuracao.cashback_validade_dias or 30),
            "cashback_valor_minimo_resgate": str(ClienteService._to_decimal_value(configuracao.cashback_valor_minimo_resgate)),
            "cancelamento_venda_limite_horas": int(configuracao.cancelamento_venda_limite_horas or 0),
            "cancelamento_item_limite_horas": int(configuracao.cancelamento_item_limite_horas or 0),
            "cancelamento_movimento_limite_horas": int(configuracao.cancelamento_movimento_limite_horas or 0),
            "email_habilitado": bool(configuracao.email_habilitado),
            "email_remetente": configuracao.email_remetente or "",
            "email_remetente_nome": configuracao.email_remetente_nome or "",
            "smtp_host": configuracao.smtp_host or "",
            "smtp_port": int(configuracao.smtp_port or 587),
            "smtp_usuario": configuracao.smtp_usuario or "",
            "smtp_senha": "",
            "smtp_senha_configurada": bool(configuracao.smtp_senha),
            "smtp_tls": bool(configuracao.smtp_tls),
            "smtp_ssl": bool(configuracao.smtp_ssl),
            "whatsapp_habilitado": False,
            "whatsapp_api_url": configuracao.whatsapp_api_url or "",
            "whatsapp_token": "",
            "whatsapp_token_configurado": bool(configuracao.whatsapp_token),
            "whatsapp_remetente": configuracao.whatsapp_remetente or "",
            "sms_habilitado": bool(configuracao.sms_habilitado),
            "sms_api_url": configuracao.sms_api_url or "",
            "sms_token": "",
            "sms_token_configurado": bool(configuracao.sms_token),
            "sms_remetente": configuracao.sms_remetente or "",
            "request_timeout_segundos": int(configuracao.request_timeout_segundos or 15),
        }

    @staticmethod
    def serializar_mensagem(item):
        return {
            "id": item.id,
            "empresa_id": item.empresa_id,
            "empresa_nome": item.empresa.nome_fantasia if item.empresa else None,
            "cliente_id": item.cliente_id,
            "canal": item.canal.value if item.canal else None,
            "destinatario": item.destinatario,
            "assunto": item.assunto,
            "conteudo": item.conteudo,
            "status": item.estado,
            "tentativas": item.tentativas,
            "proxima_tentativa": TimeService.serialize_utc_iso(item.proxima_tentativa),
            "erro": item.erro,
            "resposta_integracao": item.resposta_integracao,
            "funcionario_nome": item.funcionario.nome if item.funcionario else None,
            "enviado_em": TimeService.serialize_utc_iso(item.enviado_em),
            "criado_em": TimeService.serialize_utc_iso(item.criado_em),
        }
