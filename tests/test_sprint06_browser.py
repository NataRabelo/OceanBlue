import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.test_sprint02_security import security_app
from tests.test_sprint03_transactions import transaction_app
from tests.test_sprint04_browser import browser_page


@pytest.mark.parametrize("path", ["/api/auditoria/view", "/api/operacoes/view", "/api/pdv/view", "/api/financeiro/view", "/api/estoque/view"])
def test_mobile_accessibility_and_local_assets(browser_page, path):
    page = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("http://127.0.0.1:8765" + path, wait_until="networkidle")
    expect(page.locator("#screen-size-lock")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    bounds = page.locator("main").bounding_box()
    assert bounds["x"] <= 24 and bounds["width"] >= 340, bounds
    page.locator(".tenant-topbar [data-sidebar-toggle]").click()
    expect(page.locator(".sidebar-mobile-close")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#tenantSidebar")).to_be_hidden()
    page.add_script_tag(path="tests/vendor/axe.min.js")
    result = page.evaluate("async () => await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})")
    directory = Path("/tmp/e2e") / ("mobile-" + path.split("/")[-2])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "axe.json").write_text(json.dumps(result), encoding="utf-8")
    page.screenshot(path=str(directory / "screen.png"), full_page=True)
    assert not result["violations"], [(item["id"], [node["target"] for node in item["nodes"]]) for item in result["violations"]]
    page.keyboard.press("Control+Home")
    page.locator(".skip-link").focus()
    page.keyboard.press("Enter")
    expect(page.locator("main")).to_be_focused()


def test_mobile_sale_retry_and_reversal(browser_page, transaction_app):
    from tests.test_sprint04_browser import test_browser_sale_split_retry_partial_full_reprint
    browser_page.set_viewport_size({"width": 390, "height": 844})
    test_browser_sale_split_retry_partial_full_reprint(browser_page, transaction_app, False)
