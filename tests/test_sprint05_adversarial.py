from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
import json

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from app.extensions import db
from app.models.db import (AdiantamentoFuncionario, AuditLog, CarteiraCliente, Cliente,
    CreditoCashbackCliente, FechamentoCaixa, FuncionarioEmpresa, LancamentoFinanceiro,
    MensagemCliente, MovimentoCarteiraCliente, MovimentoEstoque, OperacaoIdempotente,
    ProdutoEmpresa, TipoFinanceiro, Venda, Permission, RolePermission)
from app.services.adiantamento_ciclo_service import AdiantamentoCicloService
from app.services.cliente_privacidade_service import ClientePrivacidadeService
from app.services.cliente_service import ClienteService
from app.services.financeiro_ciclo_service import FinanceiroCicloService
from app.services.financeiro_service import FinanceiroService
from app.services.mensagem_fila_service import MensagemFilaService, GatewaySimulado
from app.services.money_service import money
from app.services.pdv_service import PdvService
from app.services.time_service import TimeService
from tests.test_sprint02_security import security_app, login, csrf_headers
from tests.test_sprint03_transactions import transaction_app, scope, parallel, stock_setup, sale_payload
from tests.test_sprint05_cycles import client_setup, enqueue, manual_entry, advance_payload, transition


def test_rounded_money_cannot_overflow_storage():
    with pytest.raises(ValueError):
        money("9999999999.999", "valor")


@pytest.mark.parametrize("reversed_first", [False, True])
def test_ledger_reversal_marker_cannot_be_forged(transaction_app, reversed_first):
    with transaction_app.app_context():
        source = manual_entry()
        if reversed_first:
            FinanceiroCicloService.estornar(source["id"], {"motivo": "Correcao formal"}, 1, scope(), 1)
        db.session.remove()
        with pytest.raises(DBAPIError):
            with db.engine.begin() as connection:
                connection.execute(text("UPDATE lancamentos_financeiros SET revertido=:value WHERE id=:source"),
                    {"value": not reversed_first, "source": source["id"]})


def test_advance_approval_rechecks_employee_company_link(transaction_app):
    with transaction_app.app_context():
        record = AdiantamentoCicloService.solicitar(advance_payload(), 1, scope(), 1)
        FuncionarioEmpresa.query.filter_by(tenant_id=1, funcionario_id=1, empresa_id=1).delete()
        db.session.commit()
        with pytest.raises(ValueError):
            transition(record, "autorizar")
        assert LancamentoFinanceiro.query.count() == 0


@pytest.mark.parametrize("privacy_action", ["unsubscribe", "anonymize"])
def test_privacy_committed_after_claim_prevents_transport(transaction_app, monkeypatch, privacy_action):
    with transaction_app.app_context():
        customer_id = client_setup()
        message = enqueue(customer_id)
        commit = db.session.commit
        commits = []

        def privacy():
            with transaction_app.app_context():
                if privacy_action == "unsubscribe":
                    ClientePrivacidadeService.consentir(customer_id,
                        {"motivo": "Descadastro concorrente", "aceita_email": False}, 1, scope(), 1)
                else:
                    ClientePrivacidadeService.anonimizar(customer_id, {"motivo": "Pedido concorrente"}, 1, scope(), 1)

        def interleave_commit():
            commit()
            commits.append(True)
            if len(commits) == 1:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(privacy).result(timeout=10)

        gateway = GatewaySimulado()
        with monkeypatch.context() as patcher:
            patcher.setattr(db.session, "commit", interleave_commit)
            result = MensagemFilaService.entregar(message["id"], 1, scope(), 1, gateway)
        assert not gateway.aceites, result
        assert result["status"] == "CANCELADO"


@pytest.mark.parametrize("boundary", ["claim", "before_transport", "after_transport", "ack"])
def test_message_worker_crash_boundaries(transaction_app, monkeypatch, boundary):
    class Crash(BaseException):
        pass

    class Transport:
        def enviar(self, message):
            if boundary == "before_transport":
                raise Crash()
            calls.append(message.id)
            if boundary == "after_transport":
                raise Crash()

    with transaction_app.app_context():
        message = enqueue(client_setup())
        calls = []
        commits = []
        commit = db.session.commit

        def crash_commit():
            commits.append(True)
            if len(commits) == (1 if boundary == "claim" else 2):
                raise Crash()
            commit()

        with monkeypatch.context() as patcher:
            if boundary in ("claim", "ack"):
                patcher.setattr(db.session, "commit", crash_commit)
            with pytest.raises(Crash):
                MensagemFilaService.entregar(message["id"], 1, scope(), 1, Transport())
        db.session.remove()
        record = db.session.get(MensagemCliente, message["id"])
        assert record.estado == ("PENDENTE" if boundary == "claim" else "INCERTO")
        gateway = GatewaySimulado()
        MensagemFilaService.entregar(record.id, 1, scope(), 1, gateway)
        assert len(calls) + len(gateway.aceites) == int(boundary != "before_transport")


@pytest.mark.parametrize("model,event_name", [(MovimentoEstoque, "after_insert"),
    (LancamentoFinanceiro, "after_insert"), (AdiantamentoFuncionario, "after_update"),
    (AuditLog, "after_insert"), (OperacaoIdempotente, "after_insert")])
@pytest.mark.parametrize("action", ["autorizar", "estornar"])
def test_advance_failure_at_every_persisted_boundary(transaction_app, model, event_name, action):
    with transaction_app.app_context():
        stock_id, product_id = stock_setup(5)
        record = AdiantamentoCicloService.solicitar(advance_payload(tipo_adiantamento="PRODUTO",
            produto_id=product_id, quantidade=2), 1, scope(), 1)
        if action == "estornar":
            record = transition(record, "autorizar")
        tables = (MovimentoEstoque, LancamentoFinanceiro, AuditLog, OperacaoIdempotente)
        before = {table: table.query.count() for table in tables}
        stock_before = db.session.get(ProdutoEmpresa, stock_id).estoque_atual

        def fail(*arguments):
            raise RuntimeError("injected boundary")

        event.listen(model, event_name, fail)
        try:
            with pytest.raises(RuntimeError, match="injected boundary"):
                transition(record, action)
        finally:
            event.remove(model, event_name, fail)
        assert before == {table: table.query.count() for table in tables}
        assert db.session.get(ProdutoEmpresa, stock_id).estoque_atual == stock_before
        assert db.session.get(AdiantamentoFuncionario, record["id"]).status == record["status"]
        result = transition(record, action)
        assert result["status"] == ("AUTORIZADO" if action == "autorizar" else "ESTORNADO")
        assert transition(record, action) == result


@pytest.mark.parametrize("boundary", ["ledger", "audit", "idempotency", "commit"])
def test_formal_reversal_failure_is_atomic(transaction_app, monkeypatch, boundary):
    with transaction_app.app_context():
        source = manual_entry()
        data = {"motivo": "Reversao com falha", "idempotency_key": "reversal-fault"}
        model = {"ledger": LancamentoFinanceiro, "audit": AuditLog, "idempotency": OperacaoIdempotente}.get(boundary)

        def fail(*arguments):
            raise RuntimeError("injected reversal")

        with monkeypatch.context() as patcher:
            if model:
                event.listen(model, "after_insert", fail)
            else:
                patcher.setattr(db.session, "commit", fail)
            try:
                with pytest.raises(RuntimeError, match="injected reversal"):
                    FinanceiroCicloService.estornar(source["id"], data, 1, scope(), 1)
            finally:
                if model:
                    event.remove(model, "after_insert", fail)
        assert LancamentoFinanceiro.query.count() == 1
        assert not db.session.get(LancamentoFinanceiro, source["id"]).revertido
        result = FinanceiroCicloService.estornar(source["id"], data, 1, scope(), 1)
        assert FinanceiroCicloService.estornar(source["id"], data, 1, scope(), 1) == result
        assert LancamentoFinanceiro.query.count() == 2


@pytest.mark.parametrize("state,invalid_action", [
    (state, action) for state, allowed in {
        "PENDENTE": {"autorizar", "cancelar"}, "AUTORIZADO": {"baixar", "estornar"},
        "BAIXADO": {"reverter_baixa"}, "CANCELADO": set(), "ESTORNADO": set(),
    }.items() for action in {"autorizar", "cancelar", "baixar", "estornar", "reverter_baixa"} - allowed
])
def test_all_invalid_advance_transitions(transaction_app, state, invalid_action):
    with transaction_app.app_context():
        record = AdiantamentoCicloService.solicitar(advance_payload(), 1, scope(), 1)
        path = {"PENDENTE": [], "AUTORIZADO": ["autorizar"], "BAIXADO": ["autorizar", "baixar"],
            "CANCELADO": ["cancelar"], "ESTORNADO": ["autorizar", "estornar"]}[state]
        for action in path:
            record = transition(record, action)
        count = LancamentoFinanceiro.query.count()
        with pytest.raises(ValueError):
            transition(record, invalid_action)
        assert LancamentoFinanceiro.query.count() == count
        assert db.session.get(AdiantamentoFuncionario, record["id"]).status == state


def test_closure_conflicting_revision_race_and_replay(transaction_app):
    with transaction_app.app_context():
        manual_entry()
        closure = FinanceiroService.criar_fechamento({"empresa_id": 1, "valor_inicial": "0", "valor_final": "12.34"}, 1, scope(), 1)

    def reopen(index):
        return FinanceiroCicloService.ajustar_fechamento(closure["id"], {"acao": "reabrir", "revisao": 1,
            "motivo": "Corrida de revisao", "idempotency_key": f"open-{index}"}, 1, scope(), 1)

    results = parallel(transaction_app, reopen, 3)
    assert sum(isinstance(result, dict) for result in results) == 1
    with transaction_app.app_context():
        data = {"acao": "fechar", "revisao": 2, "motivo": "Ajuste conferido", "valor_inicial": "0",
            "valor_final": "12.35", "idempotency_key": "close"}
        result = FinanceiroCicloService.ajustar_fechamento(closure["id"], data, 1, scope(), 1)
        assert FinanceiroCicloService.ajustar_fechamento(closure["id"], data, 1, scope(), 1) == result
        with pytest.raises(ValueError, match="outros dados"):
            FinanceiroCicloService.ajustar_fechamento(closure["id"], {**data, "valor_final": "99"}, 1, scope(), 1)
        assert result["diferenca"] == "0.01" and result["revisao"] == 3


def test_reconciliation_over_1000_and_local_midnight(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup(2)
        sale = PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        original = db.session.get(Venda, sale["id"])
        day = TimeService.today_br().replace(day=2)
        midnight = TimeService.local_date_start_to_utc_naive(day)
        original.data_venda = midnight
        entry = LancamentoFinanceiro.query.one()
        for number in range(1001):
            clone = Venda(tenant_id=1, empresa_id=1, tipo_operacao_id=original.tipo_operacao_id,
                numero_unico=f"bulk-{number}", total=Decimal("0.01"), subtotal=Decimal("0.01"),
                data_venda=midnight if number < 1000 else midnight - timedelta(seconds=1))
            db.session.add(clone)
            db.session.flush()
            db.session.add(LancamentoFinanceiro(tenant_id=1, empresa_id=1, venda_id=clone.id,
                categoria_id=entry.categoria_id, forma_pagamento_id=entry.forma_pagamento_id,
                tipo=TipoFinanceiro.ENTRADA, valor=Decimal("0.01"), descricao="Centavo sintetico"))
        db.session.commit()
        report = FinanceiroCicloService.conciliar(1, scope(), 1, day.isoformat(), day.isoformat())
        assert len(report["vendas"]) == 1001 and report["pdv_liquido"] == "20.00"
        assert report["financeiro_liquido"] == "20.00" and report["conciliado"]
        previous = (day - timedelta(days=1)).isoformat()
        assert len(FinanceiroCicloService.conciliar(1, scope(), 1, previous, previous)["vendas"]) == 1


def test_message_history_respects_company_scope_http(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        visible = enqueue(customer_id)
        MensagemFilaService.enfileirar(customer_id, 2, "EMAIL", "Segredo empresa 2", "Segredo empresa 2", "branch-2", 1, 1)
        permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_todas_empresas").one()
        RolePermission.query.filter_by(tenant_id=1, permission_id=permission.id).delete()
        db.session.commit()
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    response = client.get(f"/api/clientes/{customer_id}/mensagens")
    assert response.status_code == 200
    assert [record["id"] for record in response.json["data"]] == [visible["id"]]
    assert "Segredo empresa 2" not in response.text


def test_send_revalidates_permission_after_claim(transaction_app, monkeypatch):
    with transaction_app.app_context():
        message = enqueue(client_setup())
        commits = []
        commit = db.session.commit

        def revoke():
            with transaction_app.app_context():
                permission = Permission.query.filter_by(tenant_id=1, codigo="enviar_mensagem_cliente").one()
                RolePermission.query.filter_by(tenant_id=1, permission_id=permission.id).delete()
                db.session.commit()

        def interleave_commit():
            commit()
            commits.append(True)
            if len(commits) == 1:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(revoke).result(timeout=10)

        gateway = GatewaySimulado()
        with monkeypatch.context() as patcher:
            patcher.setattr(db.session, "commit", interleave_commit)
            with pytest.raises(PermissionError):
                MensagemFilaService.entregar(message["id"], 1, scope(), 1, gateway)
        assert not gateway.aceites
        assert db.session.get(MensagemCliente, message["id"]).estado == "INCERTO"


def test_cashback_use_expire_cancel_race(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(5)
        earned = PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        CreditoCashbackCliente.query.one().data_expiracao = TimeService.today_br() - timedelta(days=1)
        db.session.commit()

    def action(index):
        if index == 0:
            return ClientePrivacidadeService.expirar(1)
        if index == 1:
            return PdvService.cancelar_venda(earned["id"], {}, 1, scope(), 1)
        payload = {**sale_payload(product_id, key="spend-race"), "cliente_id": customer_id, "cashback_utilizado": "1"}
        payload["pagamentos"][0]["valor"] = "9"
        return PdvService.criar_venda(payload, 1, scope(), 1)

    results = parallel(transaction_app, action, 3)
    assert isinstance(results[2], str)
    with transaction_app.app_context():
        assert CarteiraCliente.query.one().saldo_disponivel == 0
        assert CreditoCashbackCliente.query.one().saldo_disponivel == 0
        assert Venda.query.count() == 1
        assert FinanceiroCicloService.conciliar(1, scope(), 1)["conciliado"]


def test_daily_limit_concurrency_and_due_backoff(transaction_app, monkeypatch):
    fixed = datetime(2026, 3, 2, 12)
    monkeypatch.setattr(TimeService, "now_utc_naive", staticmethod(lambda: fixed))
    with transaction_app.app_context():
        customer_id = client_setup()
        template = enqueue(customer_id)
        record = db.session.get(MensagemCliente, template["id"])
        for number in range(998):
            db.session.add(MensagemCliente(tenant_id=1, empresa_id=1, cliente_id=customer_id,
                canal=record.canal, destinatario=record.destinatario, assunto="Limite", conteudo="Sintetico",
                chave=f"seed-{number}", criado_em=fixed, estado="CANCELADO"))
        db.session.commit()
    results = parallel(transaction_app, lambda index: enqueue(customer_id, f"limit-{index}"), 3)
    assert sum(isinstance(result, dict) for result in results) == 1
    with transaction_app.app_context():
        assert MensagemCliente.query.count() == 1000
        gateway = GatewaySimulado("recusa")
        result = MensagemFilaService.entregar(template["id"], 1, scope(), 1, gateway)
        assert result["status"] == "FALHOU"
        record = db.session.get(MensagemCliente, template["id"])
        assert record.proxima_tentativa == fixed + timedelta(seconds=60)
        assert MensagemFilaService.entregar(record.id, 1, scope(), 1, gateway)["tentativas"] == 1
        monkeypatch.setattr(TimeService, "now_utc_naive", staticmethod(lambda: fixed + timedelta(seconds=60)))
        assert MensagemFilaService.entregar(record.id, 1, scope(), 1, gateway)["tentativas"] == 2


@pytest.mark.parametrize("assignment", ["valor=99", "tipo='SAIDA'", "empresa_id=2", "tenant_id=2",
    "descricao='alterado'", "data_lancamento=now()", "lancamento_origem_id=id", "funcionario_id=NULL"])
def test_ledger_direct_identity_and_value_edits_are_rejected(transaction_app, assignment):
    with transaction_app.app_context():
        source = manual_entry()
        db.session.remove()
        with pytest.raises(DBAPIError):
            with db.engine.begin() as connection:
                connection.execute(text(f"UPDATE lancamentos_financeiros SET {assignment} WHERE id=:source"), {"source": source["id"]})


@pytest.mark.parametrize("boundary", ["customer", "message", "cache", "audit", "commit"])
def test_privacy_failure_rolls_back_all_operational_copies(transaction_app, monkeypatch, boundary):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(3)
        payload = {**sale_payload(product_id), "cliente_id": customer_id}
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        model = {"customer": Cliente, "message": MensagemCliente, "cache": OperacaoIdempotente, "audit": AuditLog}.get(boundary)
        event_name = "after_insert" if boundary == "audit" else "after_update"

        def fail(*arguments):
            raise RuntimeError("injected privacy")

        with monkeypatch.context() as patcher:
            if model:
                event.listen(model, event_name, fail)
            else:
                patcher.setattr(db.session, "commit", fail)
            try:
                with pytest.raises(RuntimeError, match="injected privacy"):
                    ClientePrivacidadeService.anonimizar(customer_id, {"motivo": "Pedido do titular"}, 1, scope(), 1)
            finally:
                if model:
                    event.remove(model, event_name, fail)
        assert db.session.get(Cliente, customer_id).email == "pessoa@example.test"
        assert MensagemCliente.query.one().destinatario == "pessoa@example.test"
        assert PdvService.criar_venda(payload, 1, scope(), 1) == sale
        ClientePrivacidadeService.anonimizar(customer_id, {"motivo": "Pedido do titular"}, 1, scope(), 1)
        exported = ClientePrivacidadeService.exportar(customer_id, 1, scope(), 1)
        replay = PdvService.criar_venda(payload, 1, scope(), 1)
        serialized = json.dumps([exported, replay, [operation.resposta for operation in OperacaoIdempotente.query.all()]])
        assert "pessoa@example.test" not in serialized and "654321" not in serialized and "Pessoa privada" not in serialized
        assert Venda.query.count() == 1 and LancamentoFinanceiro.query.count() == 1


@pytest.mark.parametrize("boundary", ["message", "audit", "commit"])
def test_queue_creation_failure_is_atomic(transaction_app, monkeypatch, boundary):
    with transaction_app.app_context():
        customer_id = client_setup()
        model = {"message": MensagemCliente, "audit": AuditLog}.get(boundary)

        def fail(*arguments):
            raise RuntimeError("injected queue")

        with monkeypatch.context() as patcher:
            if model:
                event.listen(model, "after_insert", fail)
            else:
                patcher.setattr(db.session, "commit", fail)
            try:
                with pytest.raises(RuntimeError, match="injected queue"):
                    enqueue(customer_id)
            finally:
                if model:
                    event.remove(model, "after_insert", fail)
        assert MensagemCliente.query.count() == 0
        assert AuditLog.query.filter_by(action="MENSAGEM_ENFILEIRADA").count() == 0
        message = enqueue(customer_id)
        assert enqueue(customer_id) == message


@pytest.mark.parametrize("boundary", ["closure", "audit", "cache", "commit"])
def test_closure_adjustment_failure_is_atomic(transaction_app, monkeypatch, boundary):
    with transaction_app.app_context():
        closure = FinanceiroService.criar_fechamento({"empresa_id": 1, "valor_inicial": "0", "valor_final": "0"}, 1, scope(), 1)
        model = {"closure": FechamentoCaixa, "audit": AuditLog, "cache": OperacaoIdempotente}.get(boundary)
        event_name = "after_update" if boundary == "closure" else "after_insert"
        data = {"acao": "reabrir", "revisao": 1, "motivo": "Correcao de caixa", "idempotency_key": "reopen-fault"}

        def fail(*arguments):
            raise RuntimeError("injected closure")

        with monkeypatch.context() as patcher:
            if model:
                event.listen(model, event_name, fail)
            else:
                patcher.setattr(db.session, "commit", fail)
            try:
                with pytest.raises(RuntimeError, match="injected closure"):
                    FinanceiroCicloService.ajustar_fechamento(closure["id"], data, 1, scope(), 1)
            finally:
                if model:
                    event.remove(model, event_name, fail)
        record = db.session.get(FechamentoCaixa, closure["id"])
        assert record.status == "FECHADO" and record.revisao == 1
        assert not OperacaoIdempotente.query.filter_by(chave="reopen-fault").first()
        assert FinanceiroCicloService.ajustar_fechamento(closure["id"], data, 1, scope(), 1)["revisao"] == 2


@pytest.mark.parametrize("field,value", [("empresa_id", True), ("empresa_id", 1.5), ("funcionario_id", False),
    ("funcionario_id", "1.0"), ("valor_total", "NaN"), ("valor_total", "Infinity"),
    ("valor_total", "-Infinity"), ("valor_total", "9999999999.999"), ("valor_total", "1e10000")])
def test_advance_api_rejects_extremes_without_effects(transaction_app, field, value):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    response = client.post("/api/adiantamentos/solicitar", json=advance_payload(**{field: value}), headers=csrf_headers(client))
    assert response.status_code == 400
    with transaction_app.app_context():
        assert AdiantamentoFuncionario.query.count() == LancamentoFinanceiro.query.count() == 0


def test_reconciliation_detects_extra_entry_and_refuses_close(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup(2)
        sale = PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        original = LancamentoFinanceiro.query.one()
        db.session.add(LancamentoFinanceiro(tenant_id=1, empresa_id=1, venda_id=sale["id"],
            categoria_id=original.categoria_id, forma_pagamento_id=original.forma_pagamento_id,
            tipo=TipoFinanceiro.ENTRADA, valor=Decimal("0.01"), descricao="Divergencia injetada"))
        db.session.commit()
        report = FinanceiroCicloService.conciliar(1, scope(), 1)
        assert not report["conciliado"] and report["vendas"][0]["diferenca"] == "0.01"
        with pytest.raises(ValueError, match="Divergencia"):
            FinanceiroService.criar_fechamento({"empresa_id": 1, "valor_inicial": "0", "valor_final": "10.01"}, 1, scope(), 1)
        assert FechamentoCaixa.query.count() == 0


def test_partial_batch_transport_never_duplicates_confirmed_or_uncertain(transaction_app):
    class Transport:
        def enviar(self, message):
            calls.append(message.id)
            if message.id == uncertain:
                raise TimeoutError("PRIVATE TRANSPORT RESPONSE")

    calls = []
    with transaction_app.app_context():
        customer_id = client_setup()
        messages = [enqueue(customer_id, f"partial-{index}") for index in range(3)]
        uncertain = messages[1]["id"]
        results = MensagemFilaService.processar(1, scope(), 1, gateway=Transport())
        assert [result["status"] for result in results] == ["ENVIADO", "INCERTO", "ENVIADO"]
        assert "PRIVATE" not in json.dumps(results)
        assert MensagemFilaService.processar(1, scope(), 1, gateway=Transport()) == []
        assert calls == [message["id"] for message in messages]
