from datetime import timedelta
from decimal import Decimal
import smtplib
import subprocess
import sys

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models.db import (Cupom, EntregaAlerta, ConfiguracaoClienteEmpresa,
    ConfiguracaoNotificacaoEstoque, ProdutoEmpresa, Venda, ItemVenda, PagamentoVenda,
    MovimentoEstoque, LancamentoFinanceiro, OperacaoIdempotente, Permission, RolePermission,
    TipoFinanceiro, CreditoCashbackCliente, MovimentoCarteiraCliente, CarteiraCliente)
from app.services.alerta_service import AlertaService
from app.services.comunicacao_service import ComunicacaoService
from app.services.pdv_service import PdvService
from app.services.estoque_service import EstoqueService
from app.services.time_service import TimeService
from tests.test_sprint02_security import security_app, login, csrf_headers
from tests.test_sprint03_transactions import transaction_app, stock_setup, sale_payload, scope, parallel
from tests.test_sprint03_transactions import product
from tests.test_sprint03_adversarial import snapshot
from tests.test_sprint04_operations import coupon, customer, alert_setup


def pending_alert(monkeypatch):
    import app.services.alerta_service as module
    _, product_id = alert_setup()
    ConfiguracaoNotificacaoEstoque.query.one().email_destinatarios = "first@example.com"
    db.session.commit()
    with monkeypatch.context() as patcher:
        patcher.setattr(module, "after_commit", lambda callback: None)
        AlertaService.produtos(1, 1, [product_id])
    return EntregaAlerta.query.one().id


@pytest.mark.parametrize("boundary", ["tls", "allowlist"])
def test_pretransport_security_rejection_is_retryable(transaction_app, monkeypatch, boundary):
    with transaction_app.app_context():
        delivery_id = pending_alert(monkeypatch)
        configuration = ConfiguracaoClienteEmpresa.query.filter_by(empresa_id=1).one()
        configuration.smtp_tls = boundary != "tls"
        configuration.smtp_ssl = False
        db.session.commit()
        result = AlertaService.entregar(delivery_id, 1)
        assert result["status"] == "FALHOU", result
        assert result["tentativas"] == 1
        sent = []
        monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: sent.append(arguments))
        assert AlertaService.retentar(delivery_id, 1, scope())["status"] == "ENVIADO"
        assert len(sent) == 1


@pytest.mark.parametrize("boundary", ["claim", "before_transport", "after_transport", "ack"])
def test_worker_crash_boundaries_preserve_durable_delivery_state(transaction_app, monkeypatch, boundary):
    class WorkerCrash(BaseException):
        pass

    with transaction_app.app_context():
        delivery_id = pending_alert(monkeypatch)
        sent = []
        commit = db.session.commit
        commits = []

        def crash_commit():
            commits.append(1)
            if len(commits) == (1 if boundary == "claim" else 2):
                raise WorkerCrash()
            return commit()

        def send(**arguments):
            if boundary == "before_transport":
                raise WorkerCrash()
            sent.append(arguments)
            if boundary == "after_transport":
                raise WorkerCrash()

        with monkeypatch.context() as patcher:
            patcher.setattr(ComunicacaoService, "enviar", send)
            if boundary in ("claim", "ack"):
                patcher.setattr(db.session, "commit", crash_commit)
            with pytest.raises(WorkerCrash):
                AlertaService.entregar(delivery_id, 1)
        db.session.remove()
        record = db.session.get(EntregaAlerta, delivery_id)
        assert record.status == ("PENDENTE" if boundary == "claim" else "INCERTO")
        assert len(sent) == int(boundary in ("after_transport", "ack"))
        monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: sent.append(arguments))
        AlertaService.entregar(delivery_id, 1, retentar=True)
        assert len(sent) == int(boundary != "before_transport")


@pytest.mark.parametrize("error,status", [
    (smtplib.SMTPRecipientsRefused({"first@example.com": (550, b"PRIVATE")}), "FALHOU"),
    (smtplib.SMTPDataError(550, b"PRIVATE"), "FALHOU"),
    (smtplib.SMTPServerDisconnected("PRIVATE"), "INCERTO"),
    (TimeoutError("PRIVATE"), "INCERTO"),
])
def test_transport_rejection_and_ambiguity_do_not_leak_or_duplicate(transaction_app, monkeypatch, error, status):
    with transaction_app.app_context():
        delivery_id = pending_alert(monkeypatch)
        calls = []

        def send(**arguments):
            calls.append(arguments)
            raise error

        monkeypatch.setattr(ComunicacaoService, "enviar", send)
        result = AlertaService.entregar(delivery_id, 1)
        assert result["status"] == status and "PRIVATE" not in result["erro"]
        AlertaService.entregar(delivery_id, 1)
        assert len(calls) == 1


@pytest.mark.parametrize("model", [Venda, ItemVenda, PagamentoVenda, MovimentoEstoque,
    LancamentoFinanceiro, CreditoCashbackCliente, MovimentoCarteiraCliente, EntregaAlerta, OperacaoIdempotente])
def test_coupon_cashback_sale_rollback_at_each_boundary(transaction_app, monkeypatch, model):
    with transaction_app.app_context():
        _, product_id = alert_setup()
        customer_id = customer()
        coupon(limite_usos=1)
        configuration = ConfiguracaoClienteEmpresa.query.filter_by(empresa_id=1).one()
        configuration.cashback_ativo = True
        configuration.cashback_percentual = 10
        db.session.commit()
        payload = sale_payload(product_id)
        payload.update(cliente_id=customer_id, cupom_codigo="CAMPANHA")
        payload["pagamentos"][0]["valor"] = "9"
        sent = []
        monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: sent.append(arguments))
        before = snapshot()

        def fail(*arguments):
            raise RuntimeError("injected persisted boundary")

        event.listen(model, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="persisted boundary"):
                PdvService.criar_venda(payload, 1, scope(), 1)
        finally:
            event.remove(model, "after_insert", fail)
        assert snapshot() == before and not sent
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        after = snapshot()
        assert PdvService.criar_venda(payload, 1, scope(), 1) == sale
        assert snapshot() == after
        assert Venda.query.count() == 1 and ProdutoEmpresa.query.one().estoque_atual == 0
        assert CarteiraCliente.query.one().saldo_disponivel == Decimal("0.90")


@pytest.mark.parametrize("mode,quantity,total", [("VAREJO", 3, "30"),
    ("AUTOMATICO", 2, "20"), ("AUTOMATICO", 3, "24"), ("ATACADO", 3, "24")])
def test_duplicate_lines_last_stock_concurrency_and_reconciliation(transaction_app, mode, quantity, total):
    with transaction_app.app_context():
        record_id, product_id = stock_setup(quantity)
        db.session.get(ProdutoEmpresa, record_id).quantidade_minima_atacado = 3
        db.session.commit()

    def sell(number):
        payload = sale_payload(product_id, key=f"last-stock-{number}")
        payload.update(modalidade_preco=mode,
            itens=[{"produto_id": product_id, "quantidade": 1} for index in range(quantity)])
        payload["pagamentos"][0]["valor"] = total
        return PdvService.criar_venda(payload, 1, scope(), 1)

    results = parallel(transaction_app, sell, count=3)
    assert sum(isinstance(result, dict) for result in results) == 1
    with transaction_app.app_context():
        sale = Venda.query.one()
        assert sale.total == Decimal(total)
        assert ProdutoEmpresa.query.one().estoque_atual == 0
        assert sum(record.quantidade for record in MovimentoEstoque.query.all()) == quantity
        PdvService.cancelar_venda(sale.id, {"idempotency_key": "cancel-all"}, 1, scope(), 1)
        assert ProdutoEmpresa.query.one().estoque_atual == quantity
        assert sum(record.valor if record.tipo == TipoFinanceiro.ENTRADA else -record.valor
            for record in LancamentoFinanceiro.query.all()) == 0


@pytest.mark.parametrize("days,accepted", [(-1, False), (0, True), (1, True)])
def test_coupon_expiry_at_brazil_day_boundary(transaction_app, monkeypatch, days, accepted):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        today = TimeService.today_br()
        coupon(data_inicio=str(today), data_validade=str(today + timedelta(days=1)))
        monkeypatch.setattr(TimeService, "today_br", lambda: today + timedelta(days=1-days))
        payload = sale_payload(product_id)
        payload["cupom_codigo"] = "CAMPANHA"
        payload["pagamentos"][0]["valor"] = "9"
        before = snapshot()
        if accepted:
            assert PdvService.criar_venda(payload, 1, scope(), 1)["total"] == "9.00"
        else:
            with pytest.raises(ValueError):
                PdvService.criar_venda(payload, 1, scope(), 1)
            assert snapshot() == before


@pytest.mark.parametrize("field,value", [("desconto_manual", "0.01"),
    ("modalidade_preco", "AUTOMATICO"), ("cupom_codigo", "OTHER"), ("cashback_ativado", False)])
def test_sale_replay_divergent_payload_leaves_all_tables_unchanged(transaction_app, field, value):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        payload = sale_payload(product_id)
        PdvService.criar_venda(payload, 1, scope(), 1)
        before = snapshot()
        with pytest.raises(ValueError, match="outros dados"):
            PdvService.criar_venda({**payload, field: value}, 1, scope(), 1)
        assert snapshot() == before


@pytest.mark.parametrize("operation", ["create", "edit", "delete"])
def test_coupon_mutations_require_csrf_and_permission(transaction_app, operation):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        record = coupon()
        record_id = record.id
        permission = Permission.query.filter_by(tenant_id=1, codigo={
            "create": "criar_cupom", "edit": "editar_cupom", "delete": "excluir_cupom"}[operation]).one()
        RolePermission.query.filter_by(permission_id=permission.id).delete(synchronize_session=False)
        db.session.commit()
        before = snapshot()
    method = {"create": client.post, "edit": client.put, "delete": client.delete}[operation]
    url = "/api/cupons/" + (str(record_id) if operation != "create" else "")
    assert method(url, json={}).status_code == 401
    assert method(url, json={}, headers=csrf_headers(client)).status_code == 403
    with transaction_app.app_context():
        after = snapshot()
        assert after["cupons"] == before["cupons"]


@pytest.mark.parametrize("permission", ["visualizar_todas_empresas", "gerenciar_alerta_estoque"])
def test_alert_retry_enforces_live_company_and_permission(transaction_app, monkeypatch, permission):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        delivery_id = pending_alert(monkeypatch)
        if permission == "visualizar_todas_empresas":
            record = EntregaAlerta(tenant_id=1, empresa_id=2, chave="foreign-company",
                assunto="Private", conteudo="Private", destinatario="first@example.com")
            db.session.add(record)
            db.session.commit()
            delivery_id = record.id
        record = Permission.query.filter_by(tenant_id=1, codigo=permission).one()
        RolePermission.query.filter_by(permission_id=record.id).delete(synchronize_session=False)
        db.session.commit()
    response = client.post(f"/api/estoque/notificacoes/{delivery_id}/retentar", json={}, headers=csrf_headers(client))
    assert response.status_code in (400, 403)
    with transaction_app.app_context():
        assert db.session.get(EntregaAlerta, delivery_id).tentativas == 0


@pytest.mark.parametrize("field", ["empresa_id", "produto_id", "cliente_id", "forma_pagamento_id"])
@pytest.mark.parametrize("malformed", ["fraction", "boolean"])
def test_sale_identifiers_cannot_be_truncated_into_another_record(transaction_app, field, malformed):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        customer_id = customer()
        payload = sale_payload(product_id)
        payload.update(cliente_id=customer_id, cashback_ativado=False)
        target = payload["itens"][0] if field == "produto_id" else (
            payload["pagamentos"][0] if field == "forma_pagamento_id" else payload)
        target[field] = target[field] + 0.9 if malformed == "fraction" else True
        before = snapshot()
        with pytest.raises(ValueError):
            PdvService.criar_venda(payload, 1, scope(), 1)
        assert snapshot() == before


@pytest.mark.parametrize("boundary", ["claim", "before_transport", "after_transport"])
def test_real_worker_process_exit_releases_locks_without_duplicate_delivery(transaction_app, monkeypatch, tmp_path, boundary):
    with transaction_app.app_context():
        delivery_id = pending_alert(monkeypatch)
        db.session.remove()
    marker = tmp_path / "transport.txt"
    result = subprocess.run([sys.executable, "-m", "tests.alert_worker_probe", str(delivery_id),
        boundary, str(marker)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 73, result.stderr
    assert marker.exists() == (boundary == "after_transport")
    sent = []
    monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: sent.append(arguments))
    with transaction_app.app_context():
        record = db.session.get(EntregaAlerta, delivery_id)
        assert record.status == ("PENDENTE" if boundary == "claim" else "INCERTO")
        AlertaService.entregar(delivery_id, 1, retentar=True)
        assert len(sent) == int(boundary == "claim")


def test_daily_summary_counts_beyond_visual_limit_and_rolls_over_day(transaction_app, monkeypatch):
    import app.services.alerta_service as module
    with transaction_app.app_context():
        alert_setup()
        for number in range(13):
            record = product(f"Ruptura {number}")
            record.estoque_atual = 0
        db.session.commit()
        monkeypatch.setattr(module, "after_commit", lambda callback: None)
        AlertaService.rotina(1, 1, scope())
        data = EstoqueService.listar_notificacoes(1, scope(), 1)
        assert data["resumo"]["estoque_baixo"] + data["resumo"]["sem_estoque"] == 14
        assert len(data["sem_estoque"]) == 12
        summaries = EntregaAlerta.query.filter(EntregaAlerta.chave.like("resumo:%")).all()
        assert len(summaries) == 2
        assert all("estoque_baixo: 1" in record.conteudo and "sem_estoque: 13" in record.conteudo for record in summaries)
        before = snapshot()
        AlertaService.rotina(1, 1, scope())
        assert snapshot() == before
        tomorrow = TimeService.today_br() + timedelta(days=1)
        monkeypatch.setattr(TimeService, "today_br", lambda: tomorrow)
        AlertaService.rotina(1, 1, scope())
        assert EntregaAlerta.query.filter(EntregaAlerta.chave.like("resumo:%")).count() == 4
