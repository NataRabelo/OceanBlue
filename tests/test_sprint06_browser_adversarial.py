import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from tests.test_sprint02_security import security_app
from tests.test_sprint03_transactions import transaction_app
from tests.test_sprint04_browser import browser_page


PAGES = ["auditoria", "operacoes"]
ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture(params=PAGES)
def operational_page(browser_page, request):
    page = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{ORIGIN}/api/{request.param}/view", wait_until="networkidle")
    status = page.locator("#audit-status" if request.param == "auditoria" else "#ciclo-status")
    expect(status).to_contain_text("eventos nesta página." if request.param == "auditoria" else "Operacao concluida.")
    return page


def open_sidebar(page):
    opener = page.locator(".tenant-topbar [data-sidebar-toggle]")
    opener.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".sidebar-mobile-close")).to_be_focused()
    expect(opener).to_have_attribute("aria-expanded", "true")
    return opener


def assert_visible_focus(locator):
    expect(locator).to_be_focused()
    expect(locator).to_have_css("outline-style", "solid")
    expect(locator).to_have_css("outline-width", "3px")
    assert locator.evaluate("element => { const bounds = element.getBoundingClientRect(); return bounds.top >= 0 && bounds.bottom <= innerHeight && bounds.left >= 0 && bounds.right <= innerWidth; }")


def test_mobile_sidebar_keyboard_round_trip(operational_page):
    page = operational_page
    opener = open_sidebar(page)
    close = page.locator(".sidebar-mobile-close")
    last_link = page.locator("#tenantSidebar a[href]").last
    page.keyboard.press("Shift+Tab")
    expect(last_link).to_be_focused()
    assert_visible_focus(last_link)
    page.keyboard.press("Tab")
    expect(close).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#tenantSidebar a[href]").first).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#tenantSidebar")).to_be_hidden()
    expect(opener).to_have_attribute("aria-expanded", "false")
    assert_visible_focus(opener)
    page.keyboard.press("Tab")
    expect(page.locator("[data-back-button]")).to_be_focused()
    opener.focus()
    page.keyboard.press("Space")
    page.keyboard.press("Enter")
    expect(page.locator("#tenantSidebar")).to_be_hidden()
    expect(opener).to_be_focused()


@pytest.mark.parametrize("width", [320, 390, 767])
def test_mobile_sidebar_focus_fits_viewport(operational_page, width):
    page = operational_page
    page.set_viewport_size({"width": width, "height": 568})
    open_sidebar(page)
    sidebar = page.locator("#tenantSidebar")
    bounds = sidebar.bounding_box()
    assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width, bounds
    assert_visible_focus(page.locator(".sidebar-mobile-close"))
    links = sidebar.locator("a[href]")
    for index in range(links.count()):
        page.keyboard.press("Tab")
        assert_visible_focus(links.nth(index))
    page.keyboard.press("Escape")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def test_sidebar_focus_survives_breakpoint_changes(operational_page):
    page = operational_page
    opener = open_sidebar(page)
    page.set_viewport_size({"width": 1024, "height": 844})
    expect(page.locator(".sidebar-mobile-close")).to_be_hidden()
    expect(opener).to_be_focused()
    page.locator("#tenantSidebar a[href]").first.focus()
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator(".sidebar-mobile-close")).to_be_focused()
    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 1024, "height": 844})
    page.locator("#tenantSidebar a[href]").first.focus()
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#tenantSidebar")).to_be_hidden()
    expect(opener).to_be_focused()


def test_persisted_mobile_sidebar_receives_focus(operational_page):
    page = operational_page
    open_sidebar(page)
    page.reload(wait_until="networkidle")
    expect(page.locator("#tenantSidebar")).to_be_visible()
    expect(page.locator(".sidebar-mobile-close")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".tenant-topbar [data-sidebar-toggle]")).to_be_focused()


@pytest.mark.parametrize("width", [390, 1440])
def test_user_disclosure_escape_and_tab_dismissal(operational_page, width):
    page = operational_page
    page.set_viewport_size({"width": width, "height": 844})
    button = page.locator("#userMenuBtn")
    dropdown = page.locator("#userDropdown")
    button.focus()
    page.keyboard.press("Enter")
    expect(dropdown).to_be_visible()
    page.keyboard.press("Tab")
    expect(dropdown.locator("a[href]").first).to_be_focused()
    page.keyboard.press("Escape")
    expect(dropdown).to_be_hidden()
    assert_visible_focus(button)
    expect(button).to_have_attribute("aria-controls", "userDropdown")
    expect(button).to_have_attribute("aria-expanded", "false")
    page.keyboard.press("Space")
    expect(button).to_have_attribute("aria-expanded", "true")
    dropdown.locator('button[type="submit"]').focus()
    page.keyboard.press("Tab")
    expect(dropdown).to_be_hidden()
    expect(page.locator("main input, main select").first).to_be_focused()
    expect(button).to_have_attribute("aria-expanded", "false")


def test_keyboard_skip_link_reaches_operational_controls(operational_page):
    page = operational_page
    page.keyboard.press("Tab")
    assert_visible_focus(page.locator(".skip-link"))
    page.keyboard.press("Enter")
    expect(page.locator("main")).to_be_focused()
    page.keyboard.press("Tab")
    assert_visible_focus(page.locator("main input, main select").first)


def test_cold_assets_local_and_loaded_page_offline_recovery(operational_page, request):
    page = operational_page
    responses, failures, external = [], [], []
    origin = urlsplit(ORIGIN).netloc

    def record_response(response):
        if urlsplit(response.url).path.startswith("/static/"):
            responses.append({"url": response.url, "status": response.status})

    def record_request(browser_request):
        if urlsplit(browser_request.url).netloc != origin:
            external.append(browser_request.url)

    page.on("response", record_response)
    page.on("requestfailed", lambda browser_request: failures.append(browser_request.url))
    page.on("request", record_request)
    page.reload(wait_until="networkidle")
    assert responses and all(response["status"] == 200 for response in responses), responses
    assert not external and not failures, (external, failures)
    assert page.locator("svg.lucide").count() > 0
    assert page.evaluate("Array.from(document.styleSheets).filter(sheet => sheet.href).every(sheet => sheet.cssRules.length > 0)")
    paths = {urlsplit(response["url"]).path for response in responses}
    assert {"/static/vendor/tailwind.css", "/static/vendor/lucide.min.js", "/static/css/core/operational.css", "/static/js/header/header.js"} <= paths
    is_audit = "/auditoria/" in page.url
    status = page.locator("#audit-status" if is_audit else "#ciclo-status")
    refresh = page.locator('#audit-filter button[type="submit"]' if is_audit else "#ciclo-atualizar")
    page.context.set_offline(True)
    try:
        opener = open_sidebar(page)
        page.keyboard.press("Escape")
        expect(opener).to_be_focused()
        refresh.focus()
        page.keyboard.press("Enter")
        expect(status).to_contain_text("Failed to fetch")
        expect(status).to_have_attribute("role", "status")
        expect(status).to_have_attribute("aria-live", "polite")
        expect(refresh).to_be_focused()
    finally:
        page.context.set_offline(False)
    page.keyboard.press("Enter")
    expect(status).to_contain_text("eventos nesta página." if is_audit else "Operacao concluida.")
    expect(refresh).to_be_focused()
    page.add_script_tag(path="tests/vendor/axe.min.js")
    result = page.evaluate("async () => await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})")
    directory = Path("/tmp/e2e") / request.node.name
    (directory / "assets-offline.json").write_text(json.dumps({"assets": responses, "external_requests": external, "failed_requests": failures, "axe_violations": result["violations"]}, indent=2), encoding="utf-8")
    assert not result["violations"], [(item["id"], [node["target"] for node in item["nodes"]]) for item in result["violations"]]
    assert not external, external
