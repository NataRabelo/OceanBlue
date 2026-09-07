from playwright.sync_api import expect

from app.extensions import db
from app.models.db import AdiantamentoFuncionario, Cliente, LancamentoFinanceiro, FechamentoCaixa
from app.services.financeiro_service import FinanceiroService
from tests.test_sprint02_security import security_app
from tests.test_sprint03_transactions import transaction_app, scope
from tests.test_sprint04_browser import browser_page
from tests.test_sprint05_cycles import client_setup, manual_entry


def test_browser_advance_reversal_closure_and_privacy(browser_page, transaction_app):
    page = browser_page
    with transaction_app.app_context():
        customer_id = client_setup()
        manual_entry()
        FinanceiroService.criar_fechamento({"empresa_id": 1, "valor_inicial": "0", "valor_final": "12.34"}, 1, scope(), 1)
    page.goto("http://127.0.0.1:8765/api/operacoes/view", wait_until="networkidle")
    expect(page.locator("#ciclo-status")).to_have_text("Operacao concluida.")
    page.locator("#ciclo-motivo").fill("Conferencia de teste completa")
    page.locator("#ciclo-valor").fill("12.34")
    page.get_by_role("button", name="Solicitar adiantamento", exact=True).click()
    expect(page.locator("#ciclo-adiantamentos")).to_contain_text("PENDENTE")
    for action, status in [("Autorizar", "AUTORIZADO"), ("Baixar em folha", "BAIXADO"), ("Reverter baixa", "AUTORIZADO"), ("Estornar vale", "ESTORNADO")]:
        page.get_by_role("button", name=action, exact=True).click()
        expect(page.locator("#ciclo-adiantamentos")).to_contain_text(status)
    page.get_by_role("button", name="Estornar", exact=True).first.click()
    expect(page.locator("#ciclo-lancamentos")).to_contain_text("estornado")
    page.get_by_role("button", name="Reabrir", exact=True).click()
    expect(page.locator("#ciclo-fechamentos")).to_contain_text("REABERTO")
    page.locator("#ciclo-final").fill("0.00")
    page.get_by_role("button", name="Fechar com ajuste", exact=True).click()
    expect(page.locator("#ciclo-fechamentos")).to_contain_text("revisao 3")
    with page.expect_download() as export:
        page.get_by_role("button", name="Exportar dados", exact=True).click()
    assert export.value.suggested_filename == f"cliente-{customer_id}.json"
    page.get_by_role("button", name="Descadastrar comunicacoes", exact=True).click()
    expect(page.locator("#ciclo-status")).to_have_text("Operacao concluida.")
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Anonimizar", exact=True).click()
    expect(page.locator("#ciclo-clientes")).to_have_text("Nenhum registro.")
    with transaction_app.app_context():
        assert AdiantamentoFuncionario.query.one().status == "ESTORNADO"
        assert LancamentoFinanceiro.query.count() == 4
        assert FechamentoCaixa.query.one().revisao == 3
        assert db.session.get(Cliente, customer_id).email is None
