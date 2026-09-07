from playwright.sync_api import expect

from app.extensions import db
from app.models.db import AdiantamentoFuncionario, LancamentoFinanceiro
from tests.test_sprint02_security import security_app
from tests.test_sprint03_transactions import transaction_app
from tests.test_sprint04_browser import browser_page


def test_browser_lost_advance_ack_replays_without_duplicate(browser_page, transaction_app):
    page = browser_page
    page.goto("http://127.0.0.1:8765/api/operacoes/view", wait_until="networkidle")
    expect(page.locator("#ciclo-status")).to_have_text("Operacao concluida.")
    page.locator("#ciclo-motivo").fill("Retentativa apos resposta perdida")
    page.locator("#ciclo-valor").fill("0.01")
    requests = []

    def lose_response(route):
        requests.append(route.request.post_data_json)
        response = route.fetch()
        assert response.status == 200
        if len(requests) == 1:
            route.abort("failed")
        else:
            route.fulfill(response=response)

    page.route("**/api/adiantamentos/solicitar", lose_response)
    button = page.get_by_role("button", name="Solicitar adiantamento", exact=True)
    button.click()
    expect(page.locator("#ciclo-status")).to_contain_text("Failed to fetch")
    button.click()
    expect(page.locator("#ciclo-adiantamentos")).to_contain_text("PENDENTE")
    assert len(requests) == 2 and requests[0] == requests[1]
    assert requests[0]["idempotency_key"]
    page.get_by_role("button", name="Autorizar", exact=True).click()
    expect(page.locator("#ciclo-adiantamentos")).to_contain_text("AUTORIZADO")
    with transaction_app.app_context():
        assert AdiantamentoFuncionario.query.count() == 1
        entry = LancamentoFinanceiro.query.one()
        assert str(entry.valor) == "0.01"
