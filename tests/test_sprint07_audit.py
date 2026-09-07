from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.db import CategoriaFinanceira, CreditoCashbackCliente, FormaPagamento, Permission, ProdutoEmpresa, Venda
from app.repositorys.cliente_repository import ClienteRepository
from app.repositorys.pdv_repository import PdvRepository
from app.services.cliente_service import ClienteService
from app.services.cupom_service import CupomService
from app.services.estoque_service import EstoqueService
from app.services.financeiro_ciclo_service import FinanceiroCicloService
from app.services.financeiro_service import FinanceiroService
from app.services.time_service import TimeService
from tests.test_sprint02_security import security_app, login, csrf_headers
from tests.test_sprint03_adversarial import snapshot
from tests.test_sprint03_transactions import transaction_app, stock_setup, sale_payload, scope, employee, import_rows
from tests.test_sprint05_cycles import client_setup, manual_entry
from app.services.pdv_service import PdvService


@pytest.mark.parametrize("target", ["product_company", "product_category", "employee_company",
    "employee_role", "stock", "role_permission", "platform_company"])
@pytest.mark.parametrize("invalid", [True, 1.5])
def test_http_identifiers_never_select_a_different_record(transaction_app, target, invalid):
    client = transaction_app.test_client()
    auth_scope = "platform" if target == "platform_company" else "tenant"
    assert login(client, scope=auth_scope).status_code == 302
    with transaction_app.app_context():
        if target.startswith("product_"):
            from app.services.categoria_service import CategoriaService
            category = CategoriaService.criar({"nome": "Categoria auditada"}, 1)
            route = "/api/produtos/"
            payload = {"nome": "Produto auditado", "empresa_id": 1, "categoria_id": category.id}
            field = "empresa_id" if target == "product_company" else "categoria_id"
            payload[field] = invalid if isinstance(invalid, bool) else payload[field] + 0.5
        elif target.startswith("employee_"):
            route, payload = "/api/funcionarios/", employee(empresa_ids=[1])
            field = "empresa_id" if target == "employee_company" else "role_id"
            payload[field] = invalid if isinstance(invalid, bool) else payload[field] + 0.5
        elif target == "stock":
            stock_id, _ = stock_setup()
            route = "/api/estoque/movimentos/manual"
            payload = {"produto_empresa_id": invalid if isinstance(invalid, bool) else stock_id + 0.5,
                "tipo_movimento": "ENTRADA", "motivo": "AJUSTE", "quantidade": 1}
        elif target == "role_permission":
            permission = Permission.query.filter_by(tenant_id=1, codigo="visualizar_produto").one()
            route = "/api/roles/"
            payload = {"nome": "Perfil auditado", "codigo": "auditado",
                "permission_ids": [invalid if isinstance(invalid, bool) else permission.id + 0.5]}
        else:
            route = "/api/platform/tenants/1/admins"
            payload = {**employee(empresa_ids=[1]), "empresa_id": invalid}
        before = snapshot()
    response = client.post(route, json=payload, headers=csrf_headers(client))
    assert response.status_code == 400, response.json
    with transaction_app.app_context():
        assert snapshot() == before


def test_string_identifiers_preserve_valid_employee_product_and_stock_flow(transaction_app):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    with transaction_app.app_context():
        payload = employee(empresa_id="1", empresa_ids=["1"])
        payload["role_id"] = str(payload["role_id"])
    response = client.post("/api/funcionarios/", json=payload, headers=csrf_headers(client))
    assert response.status_code == 201, response.json
    response = client.post("/api/produtos/", json={"nome": "Produto auditado", "empresa_id": "1",
        "valor_varejo": "10.00"}, headers=csrf_headers(client))
    assert response.status_code == 201, response.json
    stock_id = response.json["data"]["id"]
    response = client.post("/api/estoque/movimentos/manual", json={"produto_empresa_id": str(stock_id),
        "tipo_movimento": "ENTRADA", "motivo": "AJUSTE", "quantidade": 2}, headers=csrf_headers(client))
    assert response.status_code == 201, response.json
    with transaction_app.app_context():
        assert db.session.get(ProdutoEmpresa, stock_id).estoque_atual == 2


@pytest.fixture
def brazil_clock(monkeypatch):
    day = TimeService.today_br().replace(day=2)
    midnight = TimeService.local_date_start_to_utc_naive(day).replace(tzinfo=timezone.utc)
    end = midnight + timedelta(days=1)
    state = {"now": end - timedelta(hours=2), "day": day, "midnight": midnight, "end": end}
    monkeypatch.setattr(TimeService, "now_utc", staticmethod(lambda: state["now"]))

    class ServerDate(date):
        @classmethod
        def today(cls):
            return day + timedelta(days=1)

    for module in ("app.repositorys.cliente_repository", "app.repositorys.pdv_repository",
        "app.services.estoque_service", "app.services.import_export_service"):
        monkeypatch.setattr(module + ".date", ServerDate, raising=False)
    return state


def test_cashback_remains_spendable_until_brazil_midnight(transaction_app, brazil_clock):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(5)
        source = PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        credit = CreditoCashbackCliente.query.filter_by(venda_origem_id=source["id"]).one()
        credit.data_expiracao = brazil_clock["day"]
        credit_id = credit.id
        db.session.commit()
        brazil_clock["now"] = brazil_clock["end"] - timedelta(seconds=1)
        wallet = ClienteService.obter_carteira(customer_id, 1, scope())
        assert wallet["carteira"]["saldo_disponivel"] == "1.00"
        assert [record["id"] for record in wallet["carteira"]["creditos_disponiveis"]] == [credit_id]
        config = ClienteService.obter_modelo_configuracao_empresa(1, 1)
        config.cashback_percentual = 0
        db.session.commit()
        payload = {**sale_payload(product_id, key="spend"), "cliente_id": customer_id,
            "cashback_utilizado": "0.50"}
        payload["pagamentos"][0]["valor"] = "9.50"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        assert sale["cashback_utilizado"] == "0.50"
        assert db.session.get(CreditoCashbackCliente, credit_id).saldo_disponivel == Decimal("0.50")
        brazil_clock["now"] = brazil_clock["end"]
        assert ClienteService.obter_carteira(customer_id, 1, scope())["carteira"]["saldo_disponivel"] == "0.00"
        assert ClienteRepository.listar_creditos_disponiveis(customer_id, 1) == []


def test_coupon_import_and_selection_share_brazil_expiry_date(transaction_app, brazil_clock):
    with transaction_app.app_context():
        row = {"nome": "Ultimo dia", "codigo": "ULTIMODIA", "data_validade": brazil_clock["day"].isoformat(),
            "tipo_desconto": "PERCENTUAL", "valor_desconto": "10", "ativo": "SIM"}
        result = import_rows("cupons", [row])
        assert result["confirmado"] and result["sucesso"] == 1, result
        coupons = PdvRepository.listar_cupons_ativos(1)
        assert len(coupons) == 1 and CupomService.serializar(coupons[0])["status"] == "ATIVO"
        brazil_clock["now"] = brazil_clock["end"]
        assert PdvRepository.listar_cupons_ativos(1) == []
        assert import_rows("cupons", [{**row, "codigo": "VENCIDO"}])["falhas"] == 1


def test_reports_cash_closure_and_series_use_same_brazil_day(transaction_app, brazil_clock):
    with transaction_app.app_context():
        stock_id, product_id = stock_setup(10)
        db.session.get(ProdutoEmpresa, stock_id).valor_compra = Decimal("3.00")
        db.session.commit()
        moments = [brazil_clock["midnight"] - timedelta(seconds=1), brazil_clock["midnight"],
            brazil_clock["end"] - timedelta(seconds=1), brazil_clock["end"]]
        sales = []
        for index, moment in enumerate(moments):
            brazil_clock["now"] = moment
            sales.append(PdvService.criar_venda(sale_payload(product_id, key=f"boundary-{index}"), 1, scope(), 1))
        brazil_clock["now"] = moments[2]
        day = brazil_clock["day"].isoformat()
        flow = FinanceiroService.obter_relatorio_fluxo_caixa(1, scope(), 1, day, day)
        assert {entry["venda_id"] for entry in flow["lancamentos"]} == {sales[1]["id"], sales[2]["id"]}
        assert flow["totais"]["entradas"] == "20.00"
        dashboard = FinanceiroService.obter_dashboard(1, scope(), 1, periodo_dias=1)
        assert dashboard["kpis"]["faturamento"] == dashboard["kpis"]["entradas"] == "20.00"
        assert dashboard["kpis"]["lucro_bruto"] == "14.00"
        assert dashboard["serie_diaria"] == [{"data": day, "entradas": "20.00", "saidas": "0.00"}]
        assert dashboard["mensal_resumo"] == [{"competencia": day[:7], "entradas": "20.00", "saidas": "0.00", "saldo": "20.00"}]
        assert dashboard["caixa_hoje"]["saldo_esperado"] == "20.00"
        ranking = EstoqueService.listar_produtos_mais_vendidos(1, scope(), 1, "periodo", day, day)
        assert ranking["itens"][0]["quantidade"] == 2
        assert PdvRepository.contar_vendas_do_dia(1, 1, brazil_clock["day"]) == 2
        closure = FinanceiroService.criar_fechamento({"empresa_id": 1, "data_fechamento": day,
            "valor_inicial": "0", "valor_final": "20"}, 1, scope(), 1)
        assert closure["diferenca"] == "0.00"


@pytest.mark.parametrize("period", ["semana", "mes", "periodo"])
def test_stock_default_period_uses_brazil_today(transaction_app, brazil_clock, period):
    with transaction_app.app_context():
        result = EstoqueService.listar_produtos_mais_vendidos(1, scope(), 1, periodo=period)
        day = brazil_clock["day"]
        assert result["periodo"]["data_fim"] == day.isoformat()
        assert result["periodo"]["data_inicio"] == (day - timedelta(days=6) if period == "semana" else day.replace(day=1)).isoformat()


def test_monthly_series_does_not_move_late_evening_to_next_month(transaction_app, brazil_clock):
    with transaction_app.app_context():
        brazil_clock["now"] = datetime(2026, 9, 1, 1, tzinfo=timezone.utc)
        manual_entry()
        dashboard = FinanceiroService.obter_dashboard(1, scope(), 1, periodo_dias=1)
        assert dashboard["mensal_resumo"] == [{"competencia": "2026-08", "entradas": "12.34", "saidas": "0.00", "saldo": "12.34"}]
        assert dashboard["serie_diaria"] == [{"data": "2026-08-31", "entradas": "12.34", "saidas": "0.00"}]


def test_partial_returns_reduce_rankings_revenue_cost_and_demand(transaction_app):
    with transaction_app.app_context():
        stock_id, product_id = stock_setup(10)
        db.session.get(ProdutoEmpresa, stock_id).valor_compra = Decimal("3.00")
        db.session.commit()
        payload = {**sale_payload(product_id, quantity=3), "desconto_manual": "3.00"}
        payload["pagamentos"][0]["valor"] = "27.00"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"],
            {"quantidade": 1, "idempotency_key": "partial"}, 1, scope(), 1)
        dashboard = FinanceiroService.obter_dashboard(1, scope(), 1)
        assert dashboard["kpis"]["faturamento"] == dashboard["kpis"]["saldo"] == "18.00"
        assert dashboard["kpis"]["ticket_medio"] == "18.00"
        assert dashboard["kpis"]["lucro_bruto"] == "12.00"
        assert dashboard["recomendacoes_compra"][0]["quantidade_vendida"] == 2
        reports = [EstoqueService.listar_produtos_mais_vendidos(1, scope(), 1),
            FinanceiroService.obter_relatorio_produtos_vendidos(1, scope(), 1)]
        for report in reports:
            assert len(report["itens"]) == 1
            assert report["itens"][0]["quantidade"] == 2
            assert report["itens"][0]["faturamento"] == "20.00"
        assert FinanceiroCicloService.conciliar(1, scope(), 1)["conciliado"]
        PdvService.cancelar_venda(sale["id"], {"idempotency_key": "full"}, 1, scope(), 1)
        assert EstoqueService.listar_produtos_mais_vendidos(1, scope(), 1)["itens"] == []
        assert FinanceiroService.obter_relatorio_produtos_vendidos(1, scope(), 1)["itens"] == []


def test_returned_item_disappears_from_rankings_while_sale_remains_active(transaction_app):
    with transaction_app.app_context():
        _, product_id = stock_setup(10)
        from tests.test_sprint03_transactions import product
        other = product("Outro produto")
        other.estoque_atual = 2
        other_id = other.produto_id
        db.session.commit()
        payload = sale_payload(product_id)
        payload["itens"].append({"produto_id": other_id, "quantidade": 1})
        payload["pagamentos"][0]["valor"] = "20.00"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        item_id = next(item["id"] for item in sale["itens"] if item["produto_id"] == product_id)
        PdvService.cancelar_item_venda(sale["id"], item_id, {"quantidade": 1}, 1, scope(), 1)
        assert db.session.get(Venda, sale["id"]).status.value == "FINALIZADA"
        for report in (EstoqueService.listar_produtos_mais_vendidos(1, scope(), 1),
            FinanceiroService.obter_relatorio_produtos_vendidos(1, scope(), 1)):
            assert [item["produto_id"] for item in report["itens"]] == [other_id]


def test_dashboard_partial_return_with_cashback_matches_reconciliation(transaction_app):
    with transaction_app.app_context():
        customer_id = client_setup()
        _, product_id = stock_setup(10)
        PdvService.criar_venda({**sale_payload(product_id), "cliente_id": customer_id}, 1, scope(), 1)
        payload = {**sale_payload(product_id, quantity=2, key="cashback-spend"),
            "cliente_id": customer_id, "cashback_utilizado": "1.00"}
        payload["pagamentos"][0]["valor"] = "19.00"
        sale = PdvService.criar_venda(payload, 1, scope(), 1)
        PdvService.cancelar_item_venda(sale["id"], sale["itens"][0]["id"], {"quantidade": 1}, 1, scope(), 1)
        reconciliation = FinanceiroCicloService.conciliar(1, scope(), 1)
        dashboard = FinanceiroService.obter_dashboard(1, scope(), 1)
        assert reconciliation["conciliado"] and reconciliation["pdv_liquido"] == "19.50"
        assert dashboard["kpis"]["faturamento"] == dashboard["kpis"]["saldo"] == "19.50"


@pytest.mark.parametrize("entity,model,row", [
    ("formas_pagamento", FormaPagamento, {"nome": "Pix", "ativo": "NAO"}),
    ("categorias_financeiras", CategoriaFinanceira,
        {"nome": "Outras entradas", "tipo_categoria": "ENTRADA", "ativo": "NAO"}),
])
def test_operational_lookup_preserves_imported_deactivation(transaction_app, entity, model, row):
    with transaction_app.app_context():
        result = import_rows(entity, [row])
        assert result["confirmado"] and result["atualizadas"] == 1
        record = model.query.filter_by(tenant_id=1, nome=row["nome"]).one()
        record_id = record.id
        assert not record.ativo
        FinanceiroService.listar_auxiliares(1, scope())
        PdvService.listar_auxiliares(1, scope())
        db.session.expire_all()
        assert not db.session.get(model, record_id).ativo


@pytest.mark.parametrize("company", [None, 1])
def test_empty_dashboard_http_is_valid_with_and_without_company(transaction_app, company):
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    response = client.get("/api/financeiro/dashboard", query_string={"empresa_id": company} if company else {})
    assert response.status_code == 200, response.json
    dashboard = response.json["data"]
    assert dashboard["kpis"]["vendas"] == 0
    for key in ("faturamento", "entradas", "saidas", "saldo", "lucro_bruto"):
        assert dashboard["kpis"][key] == "0.00"
    assert dashboard["mensal_resumo"] == []
    assert dashboard["recomendacoes_compra"] == []
    assert len(dashboard["serie_diaria"]) == 30
    assert all(row["entradas"] == row["saidas"] == "0.00" for row in dashboard["serie_diaria"])
