from datetime import timedelta
from decimal import Decimal
import json

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from app.extensions import db
from app.models.db import (AdiantamentoFuncionario, AuditLog, CarteiraCliente, Cliente, CreditoCashbackCliente,
    FechamentoCaixa, FormaPagamento, LancamentoFinanceiro, MensagemCliente, MovimentoCarteiraCliente,
    MovimentoEstoque, ProdutoEmpresa, TipoFinanceiro, Venda)
from app.services.adiantamento_ciclo_service import AdiantamentoCicloService
from app.services.adiantamento_service import AdiantamentoService
from app.services.cliente_privacidade_service import ClientePrivacidadeService
from app.services.cliente_service import ClienteService
from app.services.financeiro_ciclo_service import FinanceiroCicloService
from app.services.financeiro_service import FinanceiroService
from app.services.mensagem_fila_service import MensagemFilaService, GatewaySimulado
from app.services.money_service import positive_integer
from app.services.pdv_service import PdvService
from app.services.time_service import TimeService
from tests.test_sprint02_security import security_app, login, csrf_headers
from tests.test_sprint03_transactions import transaction_app, stock_setup, sale_payload, scope, parallel


def client_setup():
    customer = ClienteService.criar({"nome": "Pessoa privada", "email": "pessoa@example.test", "documento": "654321",
        "telefone": "11999999999", "aceita_email": True}, 1)
    config = ClienteService.obter_modelo_configuracao_empresa(1, 1)
    config.email_habilitado = True
    config.smtp_host = "smtp.example.test"
    config.email_remetente = "loja@example.test"
    config.cashback_ativo = True
    config.cashback_percentual = 10
    db.session.add(config)
    db.session.commit()
    return customer.id


def enqueue(customer_id, key="message-1"):
    return ClienteService.enviar_mensagem(customer_id, {"empresa_id": 1, "canal": "EMAIL",
        "assunto": "Novidade", "conteudo": "Conteudo privado", "idempotency_key": key}, 1, scope(), 1)


def advance_payload(**fields):
    return {"empresa_id": 1, "funcionario_id": 1, "tipo_adiantamento": "DINHEIRO",
        "valor_total": "12.34", "idempotency_key": "advance-1", **fields}


def transition(record, action):
    return AdiantamentoCicloService.transicionar(record["id"], {"acao": action, "revisao": record["revisao"],
        "motivo": "Solicitacao conferida", "idempotency_key": f"{action}-{record['revisao']}"}, 1, scope(), 1)


@pytest.mark.parametrize("value", [True, False, 1.5, 1.0, "1.5", "NaN", -1, 0, 2147483648, None])
def test_strict_identifiers(value):
    with pytest.raises(ValueError):
        positive_integer(value, "Identificador")


@pytest.mark.parametrize("product", [False, True])
def test_advance_full_cycle_preserves_ledger_and_stock(transaction_app, product):
    with transaction_app.app_context():
        stock_id, product_id = stock_setup(5)
        payload = advance_payload(**({"tipo_adiantamento": "PRODUTO", "produto_id": product_id, "quantidade": 2} if product else {}))
        record = AdiantamentoCicloService.solicitar(payload, 1, scope(), 1)
        assert record["status"] == "PENDENTE"
        assert LancamentoFinanceiro.query.count() == 0 and MovimentoEstoque.query.count() == 0
        assert AdiantamentoCicloService.solicitar(payload, 1, scope(), 1) == record
        record = transition(record, "autorizar")
        assert record["status"] == "AUTORIZADO" and LancamentoFinanceiro.query.count() == 1
        record = transition(record, "baixar")
        assert LancamentoFinanceiro.query.count() == 1
        with pytest.raises(ValueError):
            transition(record, "estornar")
        record = transition(record, "reverter_baixa")
        record = transition(record, "estornar")
        assert record["status"] == "ESTORNADO"
        assert db.session.get(ProdutoEmpresa, stock_id).estoque_atual == 5
        entries = LancamentoFinanceiro.query.order_by(LancamentoFinanceiro.id).all()
        assert len(entries) == 2 and entries[1].lancamento_origem_id == entries[0].id
        assert entries[0].valor == entries[1].valor
        assert AdiantamentoService.obter_resumo_folha(1, scope())["totais"]["adiantado"] == "0.00"
        assert AuditLog.query.filter(AuditLog.action.like("ADIANTAMENTO_%")).count() == 5


def test_advance_cancel_and_concurrent_approval(transaction_app):
    with transaction_app.app_context():
        record = AdiantamentoCicloService.solicitar(advance_payload(), 1, scope(), 1)
    results = parallel(transaction_app, lambda index: transition(record, "autorizar"), 3)
    assert all(result["status"] == "AUTORIZADO" for result in results)
    with transaction_app.app_context():
        assert LancamentoFinanceiro.query.count() == 1
        other = AdiantamentoCicloService.solicitar(advance_payload(idempotency_key="other"), 1, scope(), 1)
        assert transition(other, "cancelar")["status"] == "CANCELADO"
        assert LancamentoFinanceiro.query.count() == 1


def test_advance_failure_after_ledger_insert_rolls_back(transaction_app):
    with transaction_app.app_context():
        record = AdiantamentoCicloService.solicitar(advance_payload(), 1, scope(), 1)
        def fail(*args):
            raise RuntimeError("injected ledger")
        event.listen(LancamentoFinanceiro, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError):
                transition(record, "autorizar")
        finally:
            event.remove(LancamentoFinanceiro, "after_insert", fail)
        assert LancamentoFinanceiro.query.count() == 0
        assert db.session.get(AdiantamentoFuncionario, record["id"]).status == "PENDENTE"
        assert transition(record, "autorizar")["status"] == "AUTORIZADO"


def manual_entry():
    category = FinanceiroService.listar_auxiliares(1, scope())["categorias"]
    category_id = category["ENTRADA"][0]["id"]
    payment = FormaPagamento.query.filter_by(tenant_id=1, nome="Dinheiro").one()
    return FinanceiroService.criar_lancamento_manual({"empresa_id": 1, "categoria_id": category_id,
        "forma_pagamento_id": payment.id, "tipo": "ENTRADA", "descricao": "Ajuste sintetico", "valor": "12.34"}, 1, scope(), 1)


def test_financial_reversal_and_audited_closure(transaction_app):
    with transaction_app.app_context():
        source = manual_entry()
        data = {"motivo": "Correcao conferida", "idempotency_key": "reverse-1"}
        reversal = FinanceiroCicloService.estornar(source["id"], data, 1, scope(), 1)
        assert FinanceiroCicloService.estornar(source["id"], data, 1, scope(), 1) == reversal
        assert reversal["lancamento_origem_id"] == source["id"]
        assert FinanceiroService.obter_relatorio_fluxo_caixa(1, scope())["totais"]["saldo"] == "0.00"
        closure = FinanceiroService.criar_fechamento({"empresa_id": 1, "valor_inicial": "10", "valor_final": "10"}, 1, scope(), 1)
        reopened = FinanceiroCicloService.ajustar_fechamento(closure["id"], {"acao": "reabrir", "revisao": 1, **data}, 1, scope(), 1)
        assert reopened["status"] == "REABERTO"
        with pytest.raises(ValueError):
            FinanceiroCicloService.ajustar_fechamento(closure["id"], {"acao": "fechar", "revisao": 1, **data}, 1, scope(), 1)
        closed = FinanceiroCicloService.ajustar_fechamento(closure["id"], {"acao": "fechar", "revisao": 2,
            "motivo": "Contagem confirmada", "valor_inicial": "10", "valor_final": "11"}, 1, scope(), 1)
        assert closed["diferenca"] == "1.00" and closed["conciliacao"]["pdv"]["conciliado"]
        log = AuditLog.query.filter_by(action="CAIXA_FECHAR").one()
        assert json.loads(log.details)["antes"]["valor_final"] == "10.00"
        assert LancamentoFinanceiro.query.count() == 2


@pytest.mark.parametrize("command", ["DELETE FROM lancamentos_financeiros", "UPDATE lancamentos_financeiros SET valor=99"])
def test_ledger_rejects_destructive_changes(transaction_app, command):
    with transaction_app.app_context():
        manual_entry()
        db.session.remove()
        with pytest.raises(DBAPIError):
            with db.engine.begin() as connection:
                connection.execute(text(command))
        assert LancamentoFinanceiro.query.one().valor == Decimal("12.34")


def test_cashback_queue_and_sale_are_one_transaction(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        stock_id, product_id = stock_setup(4)
        def fail(*args):
            raise RuntimeError("injected outbox")
        event.listen(MensagemCliente, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError):
                PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        finally:
            event.remove(MensagemCliente, "after_insert", fail)
        assert Venda.query.count() == 0 and CreditoCashbackCliente.query.count() == 0
        assert db.session.get(ProdutoEmpresa, stock_id).estoque_atual == 4
        sale = PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        assert sale["email_venda"]["status"] == "PENDENTE"
        assert MensagemCliente.query.count() == 1
        assert FinanceiroCicloService.conciliar(1, scope(), 1)["conciliado"]


@pytest.mark.parametrize("result,expected", [("sucesso", "ENVIADO"), ("recusa", "FALHOU"), ("timeout", "INCERTO")])
def test_queue_gateway_outcomes_concurrency_and_replay(transaction_app, result, expected):
    gateway = GatewaySimulado(result)
    with transaction_app.app_context():
        customer_id = client_setup()
        message = enqueue(customer_id)
        assert enqueue(customer_id)["id"] == message["id"]
        with pytest.raises(ValueError):
            MensagemFilaService.enfileirar(customer_id, 1, "EMAIL", "Diferente", "Conteudo", "message-1", 1, 1)
    parallel(transaction_app, lambda index: MensagemFilaService.entregar(message["id"], 1, scope(), 1, gateway), 3)
    with transaction_app.app_context():
        record = db.session.get(MensagemCliente, message["id"])
        assert record.estado == expected and record.tentativas == 1
        assert len(gateway.aceites) == (1 if result == "sucesso" else 0)
        assert MensagemFilaService.entregar(record.id, 1, scope(), 1, gateway)["tentativas"] == 1


def test_queue_backoff_exhaustion_and_default_block(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        message = enqueue(customer_id)
        for attempt in range(1, 6):
            record = db.session.get(MensagemCliente, message["id"])
            record.proxima_tentativa = TimeService.now_utc_naive() - timedelta(seconds=1)
            db.session.commit()
            result = MensagemFilaService.entregar(record.id, 1, scope(), 1)
            assert result["tentativas"] == attempt
        assert result["status"] == "ESGOTADO"
        assert MensagemFilaService.processar(1, scope(), 1) == []


def test_consent_export_anonymization_preserves_obligations(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(2)
        PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        exported = ClientePrivacidadeService.exportar(customer_id, 1, scope(), 1)
        assert exported["cliente"]["email"] == "pessoa@example.test" and len(exported["vendas"]) == 1
        ClientePrivacidadeService.consentir(customer_id, {"motivo": "Pedido do titular", "aceita_email": False}, 1, scope(), 1)
        assert MensagemCliente.query.one().estado == "CANCELADO"
        result = ClientePrivacidadeService.anonimizar(customer_id, {"motivo": "Pedido do titular"}, 1, scope(), 1)
        assert result["email"] is None and result["documento"] is None and not result["ativo"]
        assert Venda.query.count() == LancamentoFinanceiro.query.count() == CreditoCashbackCliente.query.count() == 1
        message = MensagemCliente.query.one()
        assert message.destinatario == "anonimizado" and "Pessoa privada" not in message.conteudo
        with pytest.raises(ValueError):
            ClienteService.atualizar(customer_id, {"nome": "Reativar", "ativo": True}, 1)


def test_cashback_expiration_concurrency_and_consumption(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(5)
        first = PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        credit = CreditoCashbackCliente.query.one()
        credit.data_expiracao = TimeService.today_br() - timedelta(days=1)
        db.session.commit()
    results = parallel(transaction_app, lambda index: ClientePrivacidadeService.expirar(1), 3)
    assert sum(result["clientes_atualizados"] for result in results) == 1
    with transaction_app.app_context():
        assert CarteiraCliente.query.one().saldo_disponivel == 0
        assert MovimentoCarteiraCliente.query.count() == 2
        payload = {**sale_payload(product_id, key="spend-expired"), "cliente_id": customer_id, "cashback_utilizado": "1"}
        payload["pagamentos"][0]["valor"] = "9"
        with pytest.raises(ValueError, match="insuficiente"):
            PdvService.criar_venda(payload, 1, scope(), 1)
        assert Venda.query.count() == 1


@pytest.mark.parametrize("route", ["/api/financeiro/lancamentos/1/estornar", "/api/financeiro/fechamentos/1/ajustar",
    "/api/adiantamentos/solicitar", "/api/adiantamentos/1/transicao", "/api/clientes/1/consentimento",
    "/api/clientes/1/anonimizar", "/api/clientes/mensagens/processar", "/api/clientes/cashback/expirar"])
def test_new_mutations_require_csrf(transaction_app, route):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    assert client.post(route, json={}).status_code in (400, 401, 403)


def test_http_tenant_privacy_and_finance_isolation(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        source = manual_entry()
    client = transaction_app.test_client()
    assert login(client, tenant="Tenant 2").status_code == 302
    assert client.get(f"/api/clientes/{customer_id}/exportar").status_code == 400
    assert client.post(f"/api/financeiro/lancamentos/{source['id']}/estornar", json={"motivo": "Ataque externo"}, headers=csrf_headers(client)).status_code == 400
    with transaction_app.app_context():
        assert not db.session.get(LancamentoFinanceiro, source["id"]).revertido


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "0.001", "-0.01", "10000000000"])
def test_advance_refuses_invalid_money_without_effects(transaction_app, value):
    with transaction_app.app_context():
        with pytest.raises(ValueError):
            AdiantamentoCicloService.solicitar(advance_payload(valor_total=value), 1, scope(), 1)
        assert AdiantamentoFuncionario.query.count() == 0


@pytest.mark.parametrize("partial", [False, True])
def test_expired_unused_credit_does_not_prevent_sale_cancellation(transaction_app, partial):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(5)
        sale = PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        credit = CreditoCashbackCliente.query.one()
        credit.data_expiracao = TimeService.today_br() - timedelta(days=1)
        db.session.commit()
        ClientePrivacidadeService.expirar(1)
        if partial:
            PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"], {"quantidade": 1}, 1, scope(), 1)
        else:
            PdvService.cancelar_venda(sale["id"], {}, 1, scope(), 1)
        assert CarteiraCliente.query.one().saldo_disponivel == 0
        assert FinanceiroCicloService.conciliar(1, scope(), 1)["conciliado"]


def test_cashback_spend_partial_full_cancel_reconciles(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(8)
        PdvService.criar_venda({**sale_payload(product_id, key="earn"), "cliente_id": customer_id}, 1, scope(), 1)
        payload = {**sale_payload(product_id, quantity=3, key="spend"), "cliente_id": customer_id, "cashback_utilizado": "1.00"}
        payload["pagamentos"][0]["valor"] = "29.00"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"], {"quantidade": 1}, 1, scope(), 1)
        assert FinanceiroCicloService.conciliar(1, scope(), 1)["conciliado"]
        PdvService.cancelar_venda(sale["id"], {}, 1, scope(), 1)
        assert FinanceiroCicloService.conciliar(1, scope(), 1)["conciliado"]
        assert CarteiraCliente.query.one().saldo_disponivel == Decimal("1.00")


def test_cashback_processing_is_idempotent_and_checks_payload(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(4)
        sale = PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        model = db.session.get(Venda, sale["id"])
        result = ClienteService.processar_cashback_da_venda(model, customer_id, 1, Decimal("0.00"), 1, 1)
        assert result["cashback_gerado"] == "1.00"
        assert CreditoCashbackCliente.query.count() == MovimentoCarteiraCliente.query.count() == 1
        with pytest.raises(ValueError):
            ClienteService.processar_cashback_da_venda(model, customer_id, 1, Decimal("0.10"), 1, 1)


def test_queue_lost_confirmation_never_retries_uncertain(transaction_app, monkeypatch):
    with transaction_app.app_context():
        customer_id = client_setup()
        message = enqueue(customer_id)
        commit = db.session.commit
        commits = []
        def fail_confirmation():
            commits.append(True)
            if len(commits) == 2:
                raise RuntimeError("Lost confirmation")
            commit()
        gateway = GatewaySimulado()
        with monkeypatch.context() as patcher:
            patcher.setattr(db.session, "commit", fail_confirmation)
            with pytest.raises(RuntimeError):
                MensagemFilaService.entregar(message["id"], 1, scope(), 1, gateway)
        assert gateway.aceites == {message["id"]}
        assert MensagemFilaService.entregar(message["id"], 1, scope(), 1, gateway)["status"] == "INCERTO"
        assert db.session.get(MensagemCliente, message["id"]).tentativas == 1


def test_anonymized_idempotent_sale_cannot_reveal_customer_again(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(4)
        payload = {**sale_payload(product_id), "cliente_id": customer_id}
        PdvService.criar_venda(payload, 1, scope(), 1)
        ClientePrivacidadeService.anonimizar(customer_id, {"motivo": "Pedido do titular"}, 1, scope(), 1)
        replay = PdvService.criar_venda(payload, 1, scope(), 1)
        assert replay["cliente_documento"] is None and "Pessoa privada" not in json.dumps(replay)


def test_reports_do_not_silently_drop_records_above_1000(transaction_app):
    with transaction_app.app_context():
        original = manual_entry()
        entry = db.session.get(LancamentoFinanceiro, original["id"])
        for number in range(1001):
            db.session.add(LancamentoFinanceiro(tenant_id=1, empresa_id=1, categoria_id=entry.categoria_id,
                forma_pagamento_id=entry.forma_pagamento_id, tipo=TipoFinanceiro.ENTRADA,
                descricao=f"Registro {number}", valor=Decimal("0.01")))
        db.session.commit()
        report = FinanceiroService.obter_relatorio_fluxo_caixa(1, scope(), empresa_id=1)
        assert report["totais"]["registros"] == 1002 and report["totais"]["saldo"] == "22.35"


@pytest.mark.parametrize("permission,route,method", [
    ("estornar_financeiro", "/api/financeiro/lancamentos/1/estornar", "post"),
    ("reabrir_caixa", "/api/financeiro/fechamentos/1/ajustar", "post"),
    ("autorizar_adiantamento", "/api/adiantamentos/1/transicao", "post"),
    ("gerenciar_privacidade_cliente", "/api/clientes/1/exportar", "get"),
    ("enviar_mensagem_cliente", "/api/clientes/mensagens/processar", "post")])
def test_new_permissions_revalidated_in_existing_session(transaction_app, permission, route, method):
    from app.models.db import Permission, RolePermission
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        record = Permission.query.filter_by(tenant_id=1, codigo=permission).one()
        RolePermission.query.filter_by(tenant_id=1, permission_id=record.id).delete()
        db.session.commit()
    response = getattr(client, method)(route, headers=csrf_headers(client))
    assert response.status_code == 403
