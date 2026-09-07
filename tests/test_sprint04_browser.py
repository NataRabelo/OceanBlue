import json
from pathlib import Path
import subprocess
import sys
import time
from decimal import Decimal

import pytest
from playwright.sync_api import sync_playwright, expect

from app.extensions import db
from app.models.db import (ProdutoEmpresa, ConfiguracaoNotificacaoEstoque, ConfiguracaoClienteEmpresa,
    Venda, LancamentoFinanceiro, TipoFinanceiro, CarteiraCliente, CreditoCashbackCliente, EntregaAlerta)
from tests.test_sprint02_security import security_app, PASSWORD
from tests.test_sprint03_transactions import transaction_app, stock_setup
from tests.test_sprint04_operations import coupon, customer, alert_setup


@pytest.fixture
def browser_page(transaction_app, request):
    with transaction_app.app_context():
        ConfiguracaoNotificacaoEstoque.query.filter_by(tenant_id=1).one().popup_ao_entrar = False
        db.session.commit()
    directory = Path("/tmp/e2e") / request.node.name
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "server.log").open("w") as logfile:
        server = subprocess.Popen([sys.executable, "-m", "gunicorn", "wsgi:app", "--bind", "127.0.0.1:8765",
            "--workers", "2", "--access-logfile", "-", "--forwarded-allow-ips", ""], stdout=logfile, stderr=subprocess.STDOUT)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
                context = browser.new_context(viewport={"width": 1440, "height": 1100})
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
                page = context.new_page()
                errors, external = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def local_only(route):
                    if route.request.url.startswith("http://127.0.0.1:8765/"):
                        route.continue_()
                    else:
                        external.append(route.request.url)
                        route.abort()

                context.route("**/*", local_only)
                deadline = time.monotonic() + 25
                while True:
                    try:
                        page.goto("http://127.0.0.1:8765/login", wait_until="networkidle")
                        break
                    except Exception:
                        if server.poll() is not None or time.monotonic() >= deadline:
                            raise
                        time.sleep(0.2)
                page.locator("#tenant").fill("Tenant 1")
                page.locator('[name="usuario"]').fill("same-user")
                page.locator('[name="senha"]').fill(PASSWORD)
                page.locator('button[type="submit"]').click()
                page.wait_for_url("**/home")
                try:
                    yield page
                    assert not errors, errors
                    assert not external, external
                finally:
                    page.screenshot(path=str(directory / "screen.png"), full_page=True)
                    (directory / "page.html").write_text(page.content(), encoding="utf-8")
                    (directory / "browser.json").write_text(json.dumps({"version": browser.version,
                        "errors": errors, "external_requests": external}), encoding="utf-8")
                    context.tracing.stop(path=str(directory / "trace.zip"))
                    browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


@pytest.mark.parametrize("cashback", [False, True])
def test_browser_sale_split_retry_partial_full_reprint(browser_page, transaction_app, cashback):
    page = browser_page
    with transaction_app.app_context():
        record_id, _ = stock_setup(6)
        db.session.get(ProdutoEmpresa, record_id).quantidade_minima_atacado = 3
        coupon()
        cliente_id = customer() if cashback else None
        if cashback:
            db.session.add(ConfiguracaoClienteEmpresa(tenant_id=1, empresa_id=1, cashback_ativo=True,
                cashback_percentual=10, cashback_validade_dias=30))
        db.session.commit()
    page.goto("http://127.0.0.1:8765/api/pdv/view", wait_until="networkidle")
    page.locator("#pdv-empresa").select_option("1")
    add = page.locator("#pdv-produtos-grid button").first
    for number in range(3):
        add.click()
    expect(page.locator("#pdv-total-subtotal")).to_contain_text("24,00")
    page.locator("#pdv-modalidade-preco").select_option("VAREJO")
    expect(page.locator("#pdv-total-subtotal")).to_contain_text("30,00")
    page.locator("#pdv-modalidade-preco").select_option("ATACADO")
    expect(page.locator("#pdv-total-subtotal")).to_contain_text("24,00")
    page.locator("#pdv-modalidade-preco").select_option("AUTOMATICO")
    if cliente_id:
        page.locator("#pdv-cliente").select_option(str(cliente_id))
    page.locator("#pdv-cupom-codigo").fill("CAMPANHA")
    expect(page.locator("#pdv-total-geral")).to_contain_text("21,60")
    page.locator("#pdv-open-payment-modal").click()
    page.locator("#pdv-add-payment").click()
    forms = page.locator(".pdv-payment-forma")
    forms.nth(0).select_option(label="Dinheiro")
    forms.nth(1).select_option(label="Pix")
    page.locator(".pdv-payment-valor").nth(0).fill("5,00")
    page.locator(".pdv-payment-valor").nth(1).fill("16,60")
    page.locator("#pdv-confirm-payment-modal").click()
    page.locator("#pdv-finalizar-venda").click()
    requests = []

    def lose_first_response(route):
        if route.request.method != "POST":
            route.continue_()
            return
        requests.append(route.request.post_data_json)
        response = route.fetch()
        assert response.status == 201, response.text()
        if len(requests) == 1:
            route.abort("failed")
        else:
            route.fulfill(response=response)

    page.route("**/api/pdv/vendas", lose_first_response)
    page.locator("#pdv-confirm-submit").click()
    expect(page.locator("#pdv-confirm-submit")).to_be_enabled()
    page.locator("#pdv-confirm-submit").click()
    expect(page.locator("#pdv-success-modal")).to_be_visible()
    page.unroute("**/api/pdv/vendas", lose_first_response)
    assert len(requests) == 2 and requests[0] == requests[1] and requests[0]["idempotency_key"]
    with transaction_app.app_context():
        sale = Venda.query.one()
        sale_id = sale.id
        assert sale.total == Decimal("21.60")
        assert sum(payment.valor for payment in sale.pagamentos) == sale.total
        assert ProdutoEmpresa.query.one().estoque_atual == 3
        if cashback:
            assert CarteiraCliente.query.one().saldo_disponivel == Decimal("2.16")
    with page.expect_popup() as popup_info:
        page.locator("#pdv-success-print").click()
    receipt = popup_info.value
    receipt.wait_for_load_state()
    expect(receipt.locator("body")).to_contain_text("21.60")
    receipt.close()
    page.locator('[data-close-modal="pdv-success-modal"]').click()
    page.locator("#pdv-open-sales-modal").click()
    page.locator(f'button[onclick="abrirModalVenda({sale_id}, false)"]').click()
    page.get_by_role("button", name="Cancelar item", exact=True).click()
    expect(page.locator("#pdv-sale-detail-content")).to_contain_text("Cancelado 1")
    with transaction_app.app_context():
        sale = db.session.get(Venda, sale_id)
        assert sale.valor_cancelado == Decimal("7.20")
        assert ProdutoEmpresa.query.one().estoque_atual == 4
    page.locator("#pdv-sale-cancel-reason").fill("Devolucao restante E2E")
    page.locator("#pdv-sale-cancel-button").click()
    expect(page.locator("#pdv-sale-modal")).to_be_hidden()
    with transaction_app.app_context():
        assert Venda.query.one().status.value == "CANCELADA"
        assert ProdutoEmpresa.query.one().estoque_atual == 6
        assert sum(entry.valor if entry.tipo == TipoFinanceiro.ENTRADA else -entry.valor
            for entry in LancamentoFinanceiro.query.all()) == 0
        if cashback:
            assert CarteiraCliente.query.one().saldo_disponivel == 0
            assert CreditoCashbackCliente.query.one().saldo_disponivel == 0


def test_browser_coupon_create_and_alert_history_retry(browser_page, transaction_app):
    page = browser_page
    page.goto("http://127.0.0.1:8765/api/cupons/view", wait_until="networkidle")
    page.get_by_role("button", name="Novo cupom", exact=True).click()
    page.locator("#cadastro-nome").fill("Cupom E2E")
    page.locator("#cadastro-codigo").fill("E2E")
    page.locator("#cadastro-valor_desconto").fill("10,00")
    page.locator("#cadastro-empresa_id").select_option("1")
    page.locator("#cadastro-limite_usos").fill("2")
    page.locator("#cadastro-valor_minimo").fill("20.00")
    page.locator("#cadastro-desconto_maximo").fill("5.00")
    with page.expect_response(lambda response: response.url.endswith("/api/cupons/") and response.request.method == "POST") as created:
        page.locator('#form-cadastro button[type="submit"]').click()
    assert created.value.status == 201, created.value.text()
    expect(page.locator("#modal-cadastro")).to_be_hidden()
    expect(page.locator("#cupom-table-body")).to_contain_text("Cupom E2E")
    with transaction_app.app_context():
        alert_setup()
        ConfiguracaoClienteEmpresa.query.filter_by(empresa_id=1).one().email_habilitado = False
        db.session.commit()
    page.goto("http://127.0.0.1:8765/api/estoque/alertas/view", wait_until="networkidle")
    page.locator("#filtro-empresa").select_option("1")
    page.locator("#alertas-executar").click()
    expect(page.locator("#alertas-historico")).to_contain_text("FALHOU")
    expect(page.locator("#alertas-historico")).to_contain_text("Resumo diario")
    page.locator("#alertas-historico button").first.click()
    expect(page.locator("#alertas-historico")).to_contain_text("2 tentativa(s)")
    page.locator("#alertas-executar").click()
    with transaction_app.app_context():
        assert EntregaAlerta.query.count() == 4
    page.locator("#btn-config-alertas").click()
    expect(page.get_by_text("WhatsApp desativado neste escopo. Utilize email.")).to_be_visible()
