from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError, DataError
from flask_migrate import downgrade, upgrade

from app.extensions import db
from app.models.db import (Cupom, Venda, PagamentoVenda, LancamentoFinanceiro, MovimentoEstoque,
    ProdutoEmpresa, EntregaAlerta, Cliente, TipoPessoa, TipoDesconto, TipoFinanceiro, ConfiguracaoClienteEmpresa,
    ConfiguracaoNotificacaoEstoque, RolePermission, Permission)
from app.services.cupom_service import CupomService
from app.services.alerta_service import AlertaService
from app.services.comunicacao_service import ComunicacaoService
from app.services.estoque_service import EstoqueService
from app.services.pdv_service import PdvService
from app.services.time_service import TimeService
from tests.test_sprint02_security import security_app, login, csrf_headers
from tests.test_sprint03_transactions import transaction_app, stock_setup, sale_payload, scope, parallel, product
from tests.test_sprint03_adversarial import snapshot


def coupon(**fields):
    return CupomService.criar({"nome": "Campanha", "codigo": "CAMPANHA", "tipo_desconto": "PERCENTUAL",
        "valor_desconto": "10", "data_validade": str(TimeService.today_br() + timedelta(days=7)), **fields}, 1, 1)


def customer():
    record = Cliente(tenant_id=1, nome="Cliente", tipo_pessoa=TipoPessoa.FISICA, documento="11122233344", ativo=True)
    db.session.add(record)
    db.session.commit()
    return record.id


def alert_setup():
    record_id, product_id = stock_setup(1)
    record = db.session.get(ProdutoEmpresa, record_id)
    record.estoque_minimo = 2
    config = ConfiguracaoNotificacaoEstoque.query.filter_by(tenant_id=1).one()
    config.email_habilitado = True
    config.email_destinatarios = "first@example.com;second@example.com;first@example.com"
    config.resumo_diario = True
    db.session.add(ConfiguracaoClienteEmpresa(tenant_id=1, empresa_id=1, email_habilitado=True,
        email_remetente="sender@example.com", smtp_host="smtp.example.com"))
    db.session.commit()
    return record_id, product_id


@pytest.mark.parametrize("mode,quantity,total,applied", [("VAREJO", 3, "30.00", "VAREJO"),
    ("ATACADO", 3, "24.00", "ATACADO"), ("AUTOMATICO", 2, "20.00", "VAREJO"),
    ("AUTOMATICO", 3, "24.00", "ATACADO")])
def test_pricing_contract_and_exact_payments(transaction_app, mode, quantity, total, applied):
    with transaction_app.app_context():
        record_id, product_id = stock_setup()
        db.session.get(ProdutoEmpresa, record_id).quantidade_minima_atacado = 3
        db.session.commit()
        payload = sale_payload(product_id, quantity)
        payload.update(modalidade_preco=mode)
        payload["pagamentos"][0]["valor"] = total
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        assert sale["total"] == total
        assert sale["itens"][0]["modalidade_preco_aplicada"] == applied
        assert sum(record.valor for record in PagamentoVenda.query.all()) == Decimal(total)
        assert sum(record.valor for record in LancamentoFinanceiro.query.all()) == Decimal(total)
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 10 - quantity


@pytest.mark.parametrize("quantity", ["1.1", "1.0", True, 0, -1, "NaN", "Infinity", None])
def test_invalid_quantities_leave_no_effects(transaction_app, quantity):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        payload = sale_payload(product_id)
        payload["itens"][0]["quantidade"] = quantity
        before = snapshot()
        with pytest.raises(ValueError):
            PdvService.criar_venda(payload, 1, scope(), 1)
        assert snapshot() == before


@pytest.mark.parametrize("permission,discount,accepted", [(None, "0.01", False),
    ("aplicar_desconto", "1.00", True), ("aplicar_desconto", "1.01", False),
    ("autorizar_desconto", "9.99", True)])
def test_manual_discount_permissions_and_limits(transaction_app, permission, discount, accepted):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        _, product_id = stock_setup()
        ids = [record.id for record in Permission.query.filter(Permission.codigo.in_(
            ["aplicar_desconto", "autorizar_desconto"]), Permission.tenant_id == 1).all()
            if record.codigo != permission and not (permission == "autorizar_desconto" and record.codigo == "aplicar_desconto")]
        RolePermission.query.filter(RolePermission.permission_id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        payload = sale_payload(product_id)
        payload["desconto_manual"] = discount
        payload["pagamentos"][0]["valor"] = str(Decimal(10) - Decimal(discount))
    response = client.post("/api/pdv/vendas", json=payload, headers=csrf_headers(client))
    assert response.status_code == (201 if accepted else 400), response.json
    with transaction_app.app_context():
        assert Venda.query.count() == int(accepted)


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity", "-1", "0", "0.001", "10000000000"])
def test_coupon_invalid_money_is_atomic(transaction_app, value):
    with transaction_app.app_context():
        before = snapshot()
        with pytest.raises(ValueError):
            coupon(valor_desconto=value)
        assert snapshot() == before


@pytest.mark.parametrize("rules", [{"limite_usos": "1.2"}, {"limite_por_cliente": 0},
    {"empresa_id": 3}, {"cliente_id": 999}, {"data_inicio": "2100-01-01"}, {"desconto_maximo": "0"},
    {"valor_minimo": "NaN"}, {"desconto_maximo": "Infinity"}, {"valor_desconto": "100.01"}])
def test_coupon_invalid_rules_do_not_persist(transaction_app, rules):
    with transaction_app.app_context():
        with pytest.raises(ValueError):
            coupon(**rules)
        assert Cupom.query.count() == 0


@pytest.mark.parametrize("rules", [{"data_inicio": str(TimeService.today_br() + timedelta(days=1))},
    {"empresa_id": 2}, {"valor_minimo": "10.01"}, {"limite_por_cliente": 1}])
def test_sale_enforces_coupon_period_company_minimum_identity(transaction_app, rules):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        coupon(**rules)
        payload = sale_payload(product_id)
        payload.update(cupom_codigo="CAMPANHA")
        payload["pagamentos"][0]["valor"] = "9.00"
        before = snapshot()
        with pytest.raises(ValueError):
            PdvService.criar_venda(payload, 1, scope(), 1)
        assert snapshot() == before


def test_coupon_rounding_cap_customer_and_historical_usage(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        cliente_id = customer()
        cupom = coupon(cliente_id=cliente_id, limite_por_cliente=1, valor_desconto="33.35", desconto_maximo="3.34")
        payload = sale_payload(product_id)
        payload.update(cliente_id=cliente_id, cupom_codigo="CAMPANHA")
        payload["pagamentos"][0]["valor"] = "6.66"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        assert sale["desconto"] == "3.34"
        assert PdvService.criar_venda(payload, 1, scope(), 1) == sale
        PdvService.cancelar_venda(sale["id"], {"idempotency_key": "cancel"}, 1, scope(), 1)
        payload["idempotency_key"] = "new-sale"
        with pytest.raises(ValueError, match="por cliente"):
            PdvService.criar_venda(payload, 1, scope(), 1)
        with pytest.raises(ValueError, match="historico"):
            CupomService.deletar(cupom.id, 1)
        assert CupomService.serializar(cupom)["usos"] == 1


def test_coupon_last_use_is_serialized_in_postgresql(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        coupon(limite_usos=1)

    def sell(number):
        payload = sale_payload(product_id, key=f"coupon-{number}")
        payload.update(cupom_codigo="CAMPANHA")
        payload["pagamentos"][0]["valor"] = "9.00"
        return PdvService.criar_venda(payload, 1, scope(), 1)

    results = parallel(transaction_app, sell, count=4)
    assert sum(isinstance(result, dict) for result in results) == 1
    with transaction_app.app_context():
        assert Venda.query.count() == MovimentoEstoque.query.count() == 1
        assert ProdutoEmpresa.query.one().estoque_atual == 9


def test_coupon_use_rollback_then_retry(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        coupon(limite_usos=1)
        payload = sale_payload(product_id)
        payload.update(cupom_codigo="CAMPANHA")
        payload["pagamentos"][0]["valor"] = "9"
        before = snapshot()

        def fail(*args):
            raise RuntimeError("injected finance")

        event.listen(LancamentoFinanceiro, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                PdvService.criar_venda(payload, 1, scope(), 1)
        finally:
            event.remove(LancamentoFinanceiro, "after_insert", fail)
        assert snapshot() == before
        assert PdvService.criar_venda(payload, 1, scope(), 1)["total"] == "9.00"


@pytest.mark.parametrize("payments", [["0.001", "10"], ["4.99", "5"], ["5", "5.01"], ["NaN", "10"]])
def test_split_payments_reject_loss_creation_or_zero(transaction_app, payments):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        payload = sale_payload(product_id)
        forma_id = payload["pagamentos"][0]["forma_pagamento_id"]
        payload["pagamentos"] = [{"forma_pagamento_id": forma_id, "valor": value} for value in payments]
        before = snapshot()
        with pytest.raises(ValueError):
            PdvService.criar_venda(payload, 1, scope(), 1)
        assert snapshot() == before


def test_zero_total_cannot_silently_discard_payments(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        payload = sale_payload(product_id)
        payload["desconto_manual"] = "10"
        with pytest.raises(ValueError, match="zero"):
            PdvService.criar_venda(payload, 1, scope(), 1)
        payload["pagamentos"] = []
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        assert sale["total"] == "0.00" and PagamentoVenda.query.count() == 0


def test_receipt_reprints_have_no_business_side_effects(transaction_app):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        _, product_id = stock_setup()
        sale = PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        before = snapshot()
    responses = [client.get(f"/api/pdv/vendas/{sale['id']}/comprovante") for attempt in range(3)]
    assert all(response.status_code == 200 and sale["numero_unico"].encode() in response.data for response in responses)
    assert len({response.data for response in responses}) == 1
    with transaction_app.app_context():
        assert snapshot() == before


def test_alerts_concurrent_queue_no_duplicate_recipients_or_daily_summary(transaction_app, monkeypatch):
    delivered = []
    monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: delivered.append(arguments["destinatario"]))
    with transaction_app.app_context():
        record_id, _ = alert_setup()
        db.session.get(ProdutoEmpresa, record_id).data_validade = TimeService.today_br()
        db.session.commit()
    parallel(transaction_app, lambda number: AlertaService.rotina(1, 1, scope()), count=3)
    with transaction_app.app_context():
        entries = EntregaAlerta.query.all()
        assert len(entries) == len(delivered) == 6
        assert all(record.status == "ENVIADO" and record.tentativas == 1 for record in entries)
        assert {record.destinatario for record in entries} == {"first@example.com", "second@example.com"}


def test_alert_partial_recipient_failure_only_retries_failed_delivery(transaction_app, monkeypatch):
    delivered = []

    def send(**arguments):
        if arguments["destinatario"] == "second@example.com":
            raise ConnectionRefusedError("PRIVATE failure")
        delivered.append(arguments["destinatario"])

    monkeypatch.setattr(ComunicacaoService, "enviar", send)
    with transaction_app.app_context():
        _, product_id = alert_setup()
        AlertaService.produtos(1, 1, [product_id])
        failed = EntregaAlerta.query.filter_by(status="FALHOU").one()
        successful = EntregaAlerta.query.filter_by(status="ENVIADO").one()
        assert "PRIVATE" not in failed.erro
        monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: delivered.append(arguments["destinatario"]))
        assert AlertaService.retentar(failed.id, 1, scope())["status"] == "ENVIADO"
        AlertaService.retentar(successful.id, 1, scope())
        assert delivered == ["first@example.com", "second@example.com"]
        assert failed.tentativas == 2


def test_alert_transport_timeout_is_uncertain_and_not_resent(transaction_app, monkeypatch):
    def send(**arguments):
        raise TimeoutError("PRIVATE timeout after possible acceptance")

    monkeypatch.setattr(ComunicacaoService, "enviar", send)
    with transaction_app.app_context():
        _, product_id = alert_setup()
        AlertaService.produtos(1, 1, [product_id])
        record = EntregaAlerta.query.first()
        assert record.status == "INCERTO" and "PRIVATE" not in record.erro
        with pytest.raises(ValueError, match="incerta"):
            AlertaService.retentar(record.id, 1, scope())
        assert AlertaService.entregar(record.id, 1, retentar=True)["tentativas"] == 1


def test_sale_and_alert_outbox_rollback_together(transaction_app, monkeypatch):
    delivered = []
    monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: delivered.append(arguments))
    with transaction_app.app_context():
        _, product_id = alert_setup()
        before = snapshot()

        def fail(*args):
            raise RuntimeError("outbox failure")

        event.listen(EntregaAlerta, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="outbox"):
                PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        finally:
            event.remove(EntregaAlerta, "after_insert", fail)
        assert snapshot() == before and delivered == []
        PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        assert len(delivered) == 2 and EntregaAlerta.query.count() == 2


def test_alert_history_http_scope_csrf_and_whatsapp_disabled(transaction_app):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    headers = csrf_headers(client)
    with transaction_app.app_context():
        alert_setup()
    assert client.post("/api/estoque/notificacoes/processar", json={"empresa_id": 1}).status_code == 401
    assert client.get("/api/estoque/notificacoes/historico?empresa_id=3").status_code == 400
    response = client.put("/api/estoque/notificacoes/configuracao", json={"whatsapp_habilitado": True}, headers=headers)
    assert response.status_code == 400 and "desativado" in response.json["message"]
    page = client.get("/api/estoque/alertas/view")
    assert b'alert-whatsapp-habilitado' not in page.data and b'alertas-historico' in page.data
    with transaction_app.app_context(), pytest.raises(ValueError, match="desativado"):
        ComunicacaoService.enviar(SimpleNamespace(), "WHATSAPP", "5511999999999", "title", "body")


@pytest.mark.parametrize("column,value", [("valor_minimo", "'NaN'::numeric"),
    ("desconto_maximo", "'Infinity'::numeric"), ("limite_usos", "0"), ("empresa_id", "3")])
def test_coupon_database_guards(transaction_app, column, value):
    with transaction_app.app_context():
        coupon()
        db.session.remove()
        with pytest.raises((IntegrityError, DataError)), db.engine.begin() as connection:
            connection.execute(text(f"UPDATE cupons SET {column}={value}"))


def test_migration_invalid_legacy_coupon_aborts_without_data_loss(transaction_app):
    with transaction_app.app_context():
        coupon()
        db.session.remove()
        downgrade(revision="6f7a8b9c0d1e")
        try:
            with db.engine.begin() as connection:
                connection.execute(text("UPDATE cupons SET valor_desconto=101"))
            with pytest.raises(IntegrityError):
                upgrade()
            with db.engine.connect() as connection:
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "6f7a8b9c0d1e"
                assert connection.execute(text("SELECT valor_desconto FROM cupons")).scalar_one() == 101
        finally:
            with db.engine.begin() as connection:
                connection.execute(text("UPDATE cupons SET valor_desconto=10"))
            upgrade()


@pytest.mark.parametrize("subtotal,percent,maximum,expected", [("0.05", "10", None, "0.01"),
    ("10.00", "33.35", None, "3.34"), ("10.00", "90", "1.99", "1.99"),
    ("0.01", "100", None, "0.01")])
def test_coupon_half_up_rounding_in_cents(subtotal, percent, maximum, expected):
    record = SimpleNamespace(valor_desconto=Decimal(percent), tipo_desconto=TipoDesconto.PERCENTUAL,
        desconto_maximo=Decimal(maximum) if maximum else None)
    assert PdvService._calcular_desconto_cupom(record, Decimal(subtotal)) == Decimal(expected)


def test_pending_alert_survives_worker_loss_and_cli_retries(transaction_app, monkeypatch):
    import app.services.alerta_service as module
    delivered = []
    monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: delivered.append(arguments))
    with transaction_app.app_context():
        _, product_id = alert_setup()
        with monkeypatch.context() as patcher:
            patcher.setattr(module, "after_commit", lambda callback: None)
            AlertaService.produtos(1, 1, [product_id])
        assert delivered == []
        assert EntregaAlerta.query.filter_by(status="PENDENTE").count() == 2
    result = transaction_app.test_cli_runner().invoke(args=["processar-alertas", "--tenant-id", "1"])
    assert result.exit_code == 0, result.output
    with transaction_app.app_context():
        assert EntregaAlerta.query.filter_by(status="PENDENTE").count() == 0
        assert len(delivered) == EntregaAlerta.query.filter_by(status="ENVIADO", empresa_id=1).count() == 4
        assert EntregaAlerta.query.filter_by(status="FALHOU", empresa_id=2).count() == 2


def test_successful_delivery_ack_failure_does_not_duplicate(transaction_app, monkeypatch):
    delivered = []
    monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: delivered.append(arguments))
    with transaction_app.app_context():
        _, product_id = alert_setup()
        ConfiguracaoNotificacaoEstoque.query.filter_by(tenant_id=1).one().email_destinatarios = "first@example.com"
        db.session.commit()
        commit = db.session.commit
        attempts = []

        def fail_ack():
            attempts.append(1)
            if len(attempts) == 3:
                raise RuntimeError("injected acknowledgement commit failure")
            return commit()

        with monkeypatch.context() as patcher:
            patcher.setattr(db.session, "commit", fail_ack)
            AlertaService.produtos(1, 1, [product_id])
        assert len(delivered) == 1
        record = EntregaAlerta.query.one()
        assert record.status == "INCERTO"
        AlertaService.entregar(record.id, 1, retentar=True)
        assert len(delivered) == 1


def test_customer_coupon_limit_concurrent_sales(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        cliente_id = customer()
        coupon(limite_por_cliente=1)

    def sell(number):
        payload = sale_payload(product_id, key=f"customer-{number}")
        payload.update(cliente_id=cliente_id, cupom_codigo="CAMPANHA", cashback_ativado=False)
        payload["pagamentos"][0]["valor"] = "9"
        return PdvService.criar_venda(payload, 1, scope(), 1)

    results = parallel(transaction_app, sell, count=3)
    assert sum(isinstance(result, dict) for result in results) == 1
    with transaction_app.app_context():
        assert Venda.query.one().cliente_id == cliente_id


def test_automatic_wholesale_uses_combined_quantity_across_lines(transaction_app):
    with transaction_app.app_context():
        record_id, product_id = stock_setup()
        db.session.get(ProdutoEmpresa, record_id).quantidade_minima_atacado = 3
        db.session.commit()
        payload = sale_payload(product_id, quantity=3)
        payload["modalidade_preco"] = "AUTOMATICO"
        payload["itens"] = [{"produto_id": product_id, "quantidade": count} for count in (1, 2)]
        payload["pagamentos"][0]["valor"] = "24"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        assert sale["total"] == "24.00"
        assert all(item["modalidade_preco_aplicada"] == "ATACADO" for item in sale["itens"])


def test_full_cancel_after_partial_is_atomic_idempotent_and_conserves_money(transaction_app):
    with transaction_app.app_context():
        record_id, product_id = stock_setup()
        payload = sale_payload(product_id, quantity=3)
        payload.update(desconto_manual="0.01")
        payload["pagamentos"][0]["valor"] = "29.99"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"],
            {"quantidade": 1, "idempotency_key": "partial"}, 1, scope(), 1)
        before = snapshot()

        def fail(*args):
            raise RuntimeError("remaining refund failure")

        event.listen(LancamentoFinanceiro, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="remaining"):
                PdvService.cancelar_venda(sale["id"], {"idempotency_key": "remaining"}, 1, scope(), 1)
        finally:
            event.remove(LancamentoFinanceiro, "after_insert", fail)
        assert snapshot() == before
        result = PdvService.cancelar_venda(sale["id"], {"idempotency_key": "remaining"}, 1, scope(), 1)
        assert PdvService.cancelar_venda(sale["id"], {"idempotency_key": "remaining"}, 1, scope(), 1) == result
        assert result["status"] == "CANCELADA" and result["valor_cancelado"] == "29.99"
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 10
        assert sum(entry.valor for entry in LancamentoFinanceiro.query.filter_by(tipo=TipoFinanceiro.SAIDA)) == Decimal("29.99")


def test_global_coupon_usage_cannot_be_hidden_by_company_scope(transaction_app):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        _, product_id = stock_setup()
        second = product("Outra loja", empresa_id=2)
        second.estoque_atual = 2
        db.session.commit()
        coupon(limite_usos=1)
        payload = sale_payload(second.produto_id)
        payload.update(empresa_id=2, cupom_codigo="CAMPANHA")
        payload["pagamentos"][0]["valor"] = "9"
        PdvService.criar_venda(payload, 1, scope(), 1)
        permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_todas_empresas").one()
        RolePermission.query.filter_by(permission_id=permission.id).delete(synchronize_session=False)
        db.session.commit()
        payload = sale_payload(product_id, key="restricted-sale")
        payload.update(cupom_codigo="campanha")
        payload["pagamentos"][0]["valor"] = "9"
    response = client.post("/api/pdv/vendas", json=payload, headers=csrf_headers(client))
    assert response.status_code == 400 and "Limite" in response.json["message"]
    with transaction_app.app_context():
        assert Venda.query.count() == 1


@pytest.mark.parametrize("days,expired,near", [(-1, 1, 0), (0, 0, 1), (30, 0, 1), (31, 0, 0)])
def test_expiry_alert_boundaries_use_brazil_calendar(transaction_app, days, expired, near):
    with transaction_app.app_context():
        record_id, _ = stock_setup()
        db.session.get(ProdutoEmpresa, record_id).data_validade = TimeService.today_br() + timedelta(days=days)
        db.session.commit()
        result = EstoqueService.listar_notificacoes(1, scope(), 1, 30)
        assert result["resumo"]["vencidos"] == expired
        assert result["resumo"]["proximos_vencimento"] == near


def test_simultaneous_retries_send_each_delivery_once(transaction_app, monkeypatch):
    with transaction_app.app_context():
        _, product_id = alert_setup()
        ConfiguracaoClienteEmpresa.query.filter_by(empresa_id=1).one().email_habilitado = False
        db.session.commit()
        AlertaService.produtos(1, 1, [product_id])
        entrega_id = EntregaAlerta.query.first().id
        ConfiguracaoClienteEmpresa.query.filter_by(empresa_id=1).one().email_habilitado = True
        db.session.commit()
    delivered = []
    monkeypatch.setattr(ComunicacaoService, "enviar", lambda **arguments: delivered.append(arguments))
    parallel(transaction_app, lambda number: AlertaService.retentar(entrega_id, 1, scope()), count=4)
    assert len(delivered) == 1
    with transaction_app.app_context():
        record = db.session.get(EntregaAlerta, entrega_id)
        assert record.status == "ENVIADO" and record.tentativas == 2
