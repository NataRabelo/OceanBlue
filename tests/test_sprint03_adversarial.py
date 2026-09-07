from decimal import Decimal

import pytest
from sqlalchemy import event, text

from app.extensions import db
from app.models.db import (
    CategoriaProduto, Funcionario, FuncionarioEmpresa, ItemVenda, LancamentoFinanceiro,
    MovimentoEstoque, OperacaoIdempotente, PagamentoVenda, Produto, ProdutoEmpresa,
    Tenant, TipoFinanceiro, Venda, Cliente, ConfiguracaoClienteEmpresa, CarteiraCliente,
    CreditoCashbackCliente, MovimentoCarteiraCliente, TipoMovimentoCarteiraCliente,
)
from app.services.cliente_service import ClienteService
from app.services.estoque_service import EstoqueService
from app.services.financeiro_service import FinanceiroService
from app.services.funcionario_service import FuncionarioService
from app.services.pdv_service import PdvService
from app.services.produto_service import ProdutoService
from tests.test_sprint02_security import security_app, login, csrf_headers
from tests.test_sprint03_transactions import (
    transaction_app, stock_setup, sale_payload, scope, parallel, product, employee,
    import_rows, LAYOUT_ROWS,
)


def snapshot():
    return {
        table.name: db.session.execute(db.select(table).order_by(*table.primary_key.columns)).all()
        for table in db.metadata.sorted_tables
    }


@pytest.mark.parametrize("model", [Venda, ItemVenda, PagamentoVenda, MovimentoEstoque, LancamentoFinanceiro, OperacaoIdempotente])
def test_sale_rollback_at_each_persisted_stage(transaction_app, model):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        payload = sale_payload(product_id)
        before = snapshot()

        def fail(*arguments):
            raise RuntimeError("injected persisted stage")

        event.listen(model, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                PdvService.criar_venda(payload, 1, scope(), 1)
        finally:
            event.remove(model, "after_insert", fail)
        assert snapshot() == before
        assert PdvService.criar_venda(payload, 1, scope(), 1)["total"] == "10.00"
        assert Venda.query.count() == OperacaoIdempotente.query.count() == 1


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("model,event_name", [(Venda, "after_update"), (MovimentoEstoque, "after_insert"),
    (LancamentoFinanceiro, "after_insert"), (OperacaoIdempotente, "after_insert")])
def test_cancel_rollback_at_each_persisted_stage(transaction_app, partial, model, event_name):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        sale = PdvService.criar_venda(sale_payload(product_id, quantity=2), 1, scope(), 1)
        before = snapshot()

        def cancel():
            payload = {"idempotency_key": "cancel", "quantidade": 1}
            if partial:
                return PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"], payload, 1, scope(), 1)
            return PdvService.cancelar_venda(sale["id"], payload, 1, scope(), 1)

        def fail(*arguments):
            raise RuntimeError("injected cancel stage")

        event.listen(model, event_name, fail)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                cancel()
        finally:
            event.remove(model, event_name, fail)
        assert snapshot() == before
        cancel()
        assert OperacaoIdempotente.query.count() == 2


def test_cashback_without_customer_cannot_reduce_payment(transaction_app):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        record_id, product_id = stock_setup()
        payload = sale_payload(product_id)
        payload["cashback_utilizado"] = "9.99"
        payload["pagamentos"][0]["valor"] = "0.01"
    response = client.post("/api/pdv/vendas", json=payload, headers=csrf_headers(client))
    assert response.status_code == 400, response.json
    with transaction_app.app_context():
        assert Venda.query.count() == PagamentoVenda.query.count() == MovimentoEstoque.query.count() == 0
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 10


@pytest.mark.parametrize("discount", ["0.01", "0.02", "29.99"])
@pytest.mark.parametrize("separate_items", [False, True])
def test_partial_refunds_conserve_every_cent(transaction_app, discount, separate_items):
    with transaction_app.app_context():
        record_id, product_id = stock_setup()
        payload = sale_payload(product_id, quantity=3)
        if separate_items:
            payload["itens"] = [{"produto_id": product_id, "quantidade": 1} for number in range(3)]
        payload["desconto_manual"] = discount
        expected = Decimal("30") - Decimal(discount)
        payload["pagamentos"][0]["valor"] = str(expected)
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        item_ids = [record["id"] for record in sale["itens"]]
        for number in range(3):
            item_id = item_ids[number if separate_items else 0]
            sale = PdvService.cancelar_item_venda(sale["id"], item_id,
                {"quantidade": 1, "idempotency_key": f"refund-{number}"}, 1, scope(), 1)
        refunds = LancamentoFinanceiro.query.filter_by(tipo=TipoFinanceiro.SAIDA).all()
        assert sum((entry.valor for entry in refunds), Decimal(0)) == expected
        assert Decimal(sale["valor_cancelado"]) == expected
        assert sale["status"] == "CANCELADA"
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 10


def test_two_sales_for_last_unit_with_distinct_keys(transaction_app):
    with transaction_app.app_context():
        record_id, product_id = stock_setup(1)
    results = parallel(transaction_app, lambda number: PdvService.criar_venda(
        sale_payload(product_id, key=f"last-{number}"), 1, scope(), 1))
    assert sum(isinstance(result, dict) for result in results) == 1
    with transaction_app.app_context():
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 0
        assert Venda.query.count() == ItemVenda.query.count() == PagamentoVenda.query.count() == 1
        assert MovimentoEstoque.query.count() == LancamentoFinanceiro.query.count() == OperacaoIdempotente.query.count() == 1


def test_concurrent_same_key_different_payload(transaction_app):
    with transaction_app.app_context():
        record_id, product_id = stock_setup()
    results = parallel(transaction_app, lambda number: PdvService.criar_venda(
        sale_payload(product_id, quantity=number + 1), 1, scope(), 1))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert any("outros dados" in result for result in results if isinstance(result, str))
    with transaction_app.app_context():
        assert Venda.query.count() == OperacaoIdempotente.query.count() == 1
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 10 - ItemVenda.query.one().quantidade


def test_simultaneous_full_and_partial_cancellation(transaction_app):
    with transaction_app.app_context():
        record_id, product_id = stock_setup()
        sale = PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)

    def cancel(number):
        if number:
            return PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"],
                {"quantidade": 1, "idempotency_key": "partial"}, 1, scope(), 1)
        return PdvService.cancelar_venda(sale["id"], {"idempotency_key": "full"}, 1, scope(), 1)

    parallel(transaction_app, cancel)
    with transaction_app.app_context():
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 10
        assert MovimentoEstoque.query.count() == LancamentoFinanceiro.query.count() == 2
        assert Venda.query.one().status.value == "CANCELADA"


@pytest.mark.parametrize("entity", LAYOUT_ROWS)
def test_each_layout_invalid_middle_row_preserves_existing_data(transaction_app, entity):
    with transaction_app.app_context():
        row = LAYOUT_ROWS[entity]
        assert import_rows(entity, [row])["confirmado"]
        before = snapshot()
        result = import_rows(entity, [{**row, "ativo": "NAO"}, {**row, "nome": "", "ativo": "SIM"}, row])
        assert result["falhas"] == 1 and result["validas"] == 2 and not result["confirmado"]
        assert snapshot() == before


@pytest.mark.parametrize("entity", LAYOUT_ROWS)
def test_duplicate_concurrent_batches_are_updates_without_duplicate_effects(transaction_app, entity):
    results = parallel(transaction_app, lambda number: import_rows(entity, [LAYOUT_ROWS[entity]]))
    assert all(result["confirmado"] for result in results)
    assert sum(result["criadas"] for result in results) == 1
    if entity == "produtos":
        with transaction_app.app_context():
            assert Produto.query.count() == ProdutoEmpresa.query.count() == MovimentoEstoque.query.count() == 1
            assert ProdutoEmpresa.query.one().estoque_atual == 3


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity", "9999999999.999", "1e1000"])
def test_money_boundary_is_client_error_and_atomic(transaction_app, value):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    response = client.post("/api/produtos/", json={"nome": "Invalid", "empresa_id": 1,
        "valor_varejo": value, "valor_atacado": "0"}, headers=csrf_headers(client))
    assert response.status_code == 400, response.json
    with transaction_app.app_context():
        assert Produto.query.count() == ProdutoEmpresa.query.count() == 0


def test_product_update_preserves_barcode_when_omitted(transaction_app):
    with transaction_app.app_context():
        record = product(codigo_barras="1234567890123")
        updated = ProdutoService.atualizar(record.id, {"nome": "Changed", "empresa_id": 1}, 1, scope())
        assert updated.produto.codigo_barras == "1234567890123"


def test_employee_history_cannot_be_detached_by_delete(transaction_app):
    with transaction_app.app_context():
        record = FuncionarioService.criar(employee(empresa_ids=[1]), 1)
        record_id, employee_id = record.id, record.funcionario_id
        product("Historical", criado_por_funcionario_id=employee_id)
        historical_product = Produto.query.one()
        historical_product.criado_por_funcionario_id = employee_id
        db.session.commit()
        before = snapshot()
        with pytest.raises(ValueError, match="historico"):
            FuncionarioService.deletar(record_id, 1)
        assert snapshot() == before


def customer_setup():
    customer = Cliente(tenant_id=1, nome="Customer")
    db.session.add(customer)
    config = ClienteService.obter_modelo_configuracao_empresa(1, 1)
    config.cashback_ativo = True
    config.cashback_percentual = Decimal("0.10")
    config.cashback_valor_minimo_resgate = 0
    config.cashback_percentual_limite_resgate_venda = 100
    db.session.add(config)
    db.session.commit()
    return customer.id


def test_refunds_do_not_overpay_individual_payment_sources(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        payload = sale_payload(product_id, quantity=3)
        payment = payload["pagamentos"][0]["forma_pagamento_id"]
        payload["desconto_manual"] = "29.97"
        payload["pagamentos"] = [{"forma_pagamento_id": payment, "valor": "0.01"} for number in range(3)]
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        for number in range(3):
            PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"],
                {"quantidade": 1, "idempotency_key": f"source-{number}"}, 1, scope(), 1)
        for source in LancamentoFinanceiro.query.filter_by(tipo=TipoFinanceiro.ENTRADA).all():
            refunds = LancamentoFinanceiro.query.filter_by(lancamento_origem_id=source.id).all()
            assert sum((refund.valor for refund in refunds), Decimal(0)) == source.valor


def test_partial_refunds_revoke_all_generated_cashback(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        customer_id = customer_setup()
        config = ConfiguracaoClienteEmpresa.query.filter_by(tenant_id=1, empresa_id=1).one()
        config.cashback_percentual = Decimal("0.04")
        db.session.commit()
        payload = {**sale_payload(product_id, quantity=3), "cliente_id": customer_id}
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        assert CreditoCashbackCliente.query.one().valor_original == Decimal("0.01")
        for number in range(3):
            PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"],
                {"quantidade": 1, "idempotency_key": f"earned-{number}"}, 1, scope(), 1)
        assert CarteiraCliente.query.one().saldo_disponivel == 0
        assert CreditoCashbackCliente.query.one().saldo_disponivel == 0
        assert db.session.get(Venda, sale["id"]).cashback_gerado == 0


def test_partial_refunds_restore_each_consumed_credit_exactly(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup(20)
        customer_id = customer_setup()
        for number in range(3):
            PdvService.criar_venda({**sale_payload(product_id, key=f"earn-{number}"), "cliente_id": customer_id}, 1, scope(), 1)
        assert CarteiraCliente.query.one().saldo_disponivel == Decimal("0.03")
        payload = {**sale_payload(product_id, quantity=3, key="spend"), "cliente_id": customer_id,
            "cashback_utilizado": "0.03"}
        payload["pagamentos"][0]["valor"] = "29.97"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        for number in range(3):
            PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"],
                {"quantidade": 1, "idempotency_key": f"restore-{number}"}, 1, scope(), 1)
        assert CarteiraCliente.query.one().saldo_disponivel == Decimal("0.03")
        for credit in CreditoCashbackCliente.query.filter(CreditoCashbackCliente.venda_origem_id != sale["id"]).all():
            assert credit.saldo_disponivel == credit.valor_original == Decimal("0.01")


@pytest.mark.parametrize("model", [CreditoCashbackCliente, MovimentoCarteiraCliente])
def test_cashback_insert_failure_rolls_back_sale_and_wallet(transaction_app, model):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        customer_id = customer_setup()
        before = snapshot()

        def fail(*arguments):
            raise RuntimeError("injected cashback")

        event.listen(model, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        finally:
            event.remove(model, "after_insert", fail)
        assert snapshot() == before


@pytest.mark.parametrize("entity,fields", [("produtos", {"empresa": "Empresa 2-1"}),
    ("funcionarios", {"empresa": "Empresa 2-1"})])
def test_import_foreign_company_rolls_back_every_row(transaction_app, entity, fields):
    with transaction_app.app_context():
        before = snapshot()
        result = import_rows(entity, [LAYOUT_ROWS[entity], {**LAYOUT_ROWS[entity], **fields}])
        assert not result["confirmado"] and result["falhas"] == 1
        assert snapshot() == before


@pytest.mark.parametrize("operation", ["sale", "cancel"])
def test_idempotency_replay_rechecks_company_access(transaction_app, operation):
    from app.services.acesso_empresa_service import AcessoEmpresaService
    with transaction_app.app_context():
        _, product_id = stock_setup()
        payload = sale_payload(product_id)
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        if operation == "cancel":
            PdvService.cancelar_venda(sale["id"], payload, 1, scope(), 1)
        before = snapshot()
        restricted = {**scope(), "empresa_ids": [2], "permission_codes": set()}
        with pytest.raises(PermissionError):
            if operation == "sale":
                PdvService.criar_venda(payload, 1, restricted, 1)
            else:
                PdvService.cancelar_venda(sale["id"], payload, 1, restricted, 1)
        assert snapshot() == before
