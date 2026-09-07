from decimal import Decimal

from playwright.sync_api import expect

from app.extensions import db
from app.models.db import ProdutoEmpresa, Venda, LancamentoFinanceiro
from tests.test_sprint02_security import security_app
from tests.test_sprint03_transactions import transaction_app, stock_setup, product
from tests.test_sprint04_operations import coupon
from tests.test_sprint04_browser import browser_page


def test_browser_coupon_minimum_exact_cents_and_split_payment(browser_page, transaction_app):
    page = browser_page
    with transaction_app.app_context():
        record_id, _ = stock_setup(2)
        db.session.get(ProdutoEmpresa, record_id).valor_varejo = Decimal("0.10")
        db.session.get(ProdutoEmpresa, record_id).valor_atacado = Decimal("0.10")
        second = product("Setenta centavos", valor_varejo="0.70", valor_atacado="0.70")
        second.estoque_atual = 2
        coupon(valor_minimo="0.80")
        db.session.commit()
    page.goto("http://127.0.0.1:8765/api/pdv/view", wait_until="networkidle")
    page.locator("#pdv-empresa").select_option("1")
    page.locator("#pdv-modalidade-preco").select_option("VAREJO")
    buttons = page.locator("#pdv-produtos-grid button")
    buttons.nth(0).click()
    buttons.nth(1).click()
    expect(page.locator("#pdv-total-subtotal")).to_contain_text("0,80")
    page.locator("#pdv-cupom-codigo").fill("CAMPANHA")
    expect(page.locator("#pdv-total-geral")).to_contain_text("0,72")
    page.locator("#pdv-open-payment-modal").click()
    page.locator("#pdv-add-payment").click()
    page.locator(".pdv-payment-forma").nth(0).select_option(label="Dinheiro")
    page.locator(".pdv-payment-forma").nth(1).select_option(label="Pix")
    page.locator(".pdv-payment-valor").nth(0).fill("0,01")
    page.locator(".pdv-payment-valor").nth(1).fill("0,71")
    page.locator("#pdv-confirm-payment-modal").click()
    page.locator("#pdv-finalizar-venda").click()
    page.locator("#pdv-confirm-submit").click()
    expect(page.locator("#pdv-success-modal")).to_be_visible()
    with transaction_app.app_context():
        sale = Venda.query.one()
        assert sale.total == Decimal("0.72")
        assert sum(payment.valor for payment in sale.pagamentos) == sale.total
        assert sum(record.valor for record in LancamentoFinanceiro.query.all()) == sale.total
        assert all(record.estoque_atual == 1 for record in ProdutoEmpresa.query.all())
