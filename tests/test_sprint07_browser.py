import json
import os
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Error, expect, sync_playwright

from app.extensions import db
from app.models.db import (
    AuditLog, ConfiguracaoNotificacaoEstoque, Funcionario,
    LancamentoFinanceiro, MovimentoEstoque, ProdutoEmpresa, Role, Venda,
)
from tests.test_sprint02_security import PASSWORD, security_app
from tests.test_sprint03_transactions import transaction_app


ORIGIN = "http://127.0.0.1:8767"
SCREEN_GROUPS = {
    "hubs": ["/home", "/pdv/home", "/estoque/home", "/financeiro/home", "/configuracoes/home"],
    "cadastros": ["/api/categorias/view", "/api/produtos/view", "/api/clientes/view", "/api/cupons/view"],
    "stock-sales": ["/api/pdv/view", "/api/estoque/view", "/api/estoque/indicadores/view", "/api/estoque/alertas/view"],
    "finance": ["/api/financeiro/view", "/api/financeiro/lancamentos/view", "/api/financeiro/relatorios/view", "/api/financeiro/boletos/view", "/api/adiantamentos/view"],
    "admin": ["/api/funcionarios/view", "/api/roles/view", "/api/permissions/view", "/api/fiscal/view", "/api/importacao-exportacao/view"],
    "operations": ["/api/auditoria/view", "/api/operacoes/view"],
}
HUBS = {
    "/api/pdv/view": "/pdv/home",
    "/api/estoque/view": "/estoque/home",
    "/api/estoque/indicadores/view": "/estoque/home",
    "/api/financeiro/view": "/financeiro/home",
    "/api/financeiro/lancamentos/view": "/financeiro/home",
    "/api/financeiro/relatorios/view": "/financeiro/home",
}


@pytest.fixture(scope="module")
def sprint07_reports(request):
    reports = {}

    class Reports:
        def pytest_runtest_logreport(self, report):
            if report.when == "call":
                reports[report.nodeid] = report

    plugin = Reports()
    request.config.pluginmanager.register(plugin)
    yield reports
    request.config.pluginmanager.unregister(plugin)


@pytest.fixture(scope="module")
def sprint07_server(migrated_database):
    with tempfile.TemporaryFile(mode="w+") as logfile:
        server = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "wsgi:app", "--bind", "127.0.0.1:8767",
             "--workers", "2", "--access-logfile", "-", "--forwarded-allow-ips", ""],
            stdout=logfile, stderr=subprocess.STDOUT,
        )
        try:
            yield SimpleNamespace(process=server, logfile=logfile)
        finally:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


@pytest.fixture(scope="module", params=["chromium", "firefox", "webkit"])
def sprint07_engine(request, sprint07_server):
    with sync_playwright() as playwright:
        browser = getattr(playwright, request.param).launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def sprint07_browser(transaction_app, request, sprint07_reports, sprint07_engine, sprint07_server):
    with transaction_app.app_context():
        ConfiguracaoNotificacaoEstoque.query.filter_by(tenant_id=1).one().popup_ao_entrar = False
        db.session.commit()
    directory = Path("/tmp/e2e/sprint07") / request.node.name
    directory.mkdir(parents=True, exist_ok=True)
    evidence = {"engine": sprint07_engine.browser_type.name, "version": sprint07_engine.version,
                "screens": [], "errors": [], "external_requests": [], "http_errors": []}
    context = sprint07_engine.new_context(
        viewport={"width": 1440, "height": 900}, locale="pt-BR", service_workers="block",
    )
    context.tracing.start(screenshots=True, snapshots=True, sources=False)

    def local_only(route):
        parsed = urlsplit(route.request.url)
        if parsed.scheme == "http" and parsed.netloc == "127.0.0.1:8767":
            route.continue_()
        else:
            evidence["external_requests"].append(route.request.url)
            route.abort()

    def deny_websocket(websocket):
        evidence["external_requests"].append(websocket.url)
        websocket.close()

    def record_response(response):
        if response.status >= 400:
            evidence["http_errors"].append({"path": urlsplit(response.url).path, "status": response.status})

    context.route("**/*", local_only)
    context.route_web_socket("**/*", deny_websocket)
    context.on("page", lambda opened: opened.on("pageerror", lambda error: evidence["errors"].append(str(error))))
    context.on("response", record_response)
    page = context.new_page()
    page.set_default_timeout(20000)
    page.set_default_navigation_timeout(30000)
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                response = page.goto(ORIGIN + "/login", wait_until="networkidle")
                assert response.status == 200
                break
            except Error:
                if sprint07_server.process.poll() is not None or time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
        login_browser(page)
        yield SimpleNamespace(page=page, evidence=evidence)
    finally:
        report = sprint07_reports.get(request.node.nodeid)
        passed = bool(report and report.passed and not evidence["errors"]
                      and not evidence["external_requests"] and not evidence["http_errors"])
        evidence["passed"] = passed
        evidence["viewport"] = page.viewport_size
        try:
            page.screenshot(path=str(directory / "sprint07-screen.png"))
            (directory / "browser.json").write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            if passed:
                context.tracing.stop()
                for filename in ("trace.zip", "page.html", "server.log", "screen.png"):
                    (directory / filename).unlink(missing_ok=True)
            else:
                context.tracing.stop(path=str(directory / "trace.zip"))
                (directory / "page.html").write_text(page.content(), encoding="utf-8")
                sprint07_server.logfile.seek(0)
                (directory / "server.log").write_text(sprint07_server.logfile.read(), encoding="utf-8")
        finally:
            context.close()
        assert not evidence["errors"], evidence["errors"]
        assert not evidence["external_requests"], evidence["external_requests"]
        assert not evidence["http_errors"], evidence["http_errors"]


def login_browser(page, username="same-user", tenant="Tenant 1", scope="tenant"):
    page.locator("#scope").select_option(scope)
    page.locator("#tenant").fill(tenant)
    page.locator('[name="usuario"]').fill(username)
    page.locator('[name="senha"]').fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_url(ORIGIN + ("/platform/home" if scope == "platform" else "/home"))
    page.wait_for_load_state("networkidle")


def logout_browser(page):
    page.locator("#userMenuBtn").click()
    page.locator('#userDropdown button[type="submit"]').click()
    page.wait_for_url(ORIGIN + "/login")


def navigate(page, path):
    if path in HUBS:
        navigate(page, HUBS[path])
        page.locator(f'main a[href="{path}"]').click()
    elif page.locator(f'#tenantSidebar a[href="{path}"]').count():
        if not page.locator("#tenantSidebar").is_visible():
            page.locator(".tenant-topbar [data-sidebar-toggle]").click()
        page.locator(f'#tenantSidebar a[href="{path}"]').click()
    else:
        response = page.goto(ORIGIN + path)
        assert response.status == 200, (path, response.status)
    page.wait_for_url(ORIGIN + path)
    page.wait_for_load_state("networkidle")
    expect(page.locator("main")).to_be_visible()
    if page.viewport_size["width"] < 768 and page.locator("#tenantSidebar").is_visible():
        page.keyboard.press("Escape")


def audit_screen(session, state=None):
    page = session.page
    if not page.evaluate("typeof axe !== 'undefined'"):
        page.add_script_tag(path="tests/vendor/axe.min.js")
    result = page.evaluate("""async () => {
        const result = await axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}
        });
        return {
            violations: result.violations.map(item => ({id: item.id,
                targets: item.nodes.map(node => node.target),
                summaries: item.nodes.map(node => node.failureSummary)})),
            rules_passed: result.passes.length,
            overflow: document.documentElement.scrollWidth > innerWidth + 1,
            title: document.title
        };
    }""")
    result.update(path=urlsplit(page.url).path, state=state, width=page.viewport_size["width"])
    session.evidence["screens"].append(result)
    return result


def scroll_page_for_header_audit(page):
    page.locator("main").focus()
    page.keyboard.press("PageDown")
    scroll = page.evaluate("""async () => {
        const scrollable = document.documentElement.scrollHeight > innerHeight + 1;
        let previous = window.scrollY;
        let stableFrames = 0;
        for (let frame = 0; frame < 120; frame++) {
            await new Promise(requestAnimationFrame);
            stableFrames = window.scrollY === previous ? stableFrames + 1 : 0;
            if (stableFrames >= 3 && (!scrollable || window.scrollY > 0)) {
                return {settled: true, scroll_y: window.scrollY};
            }
            previous = window.scrollY;
        }
        return {settled: false, scroll_y: window.scrollY,
            scroll_height: document.documentElement.scrollHeight, viewport_height: innerHeight};
    }""")
    assert scroll["settled"], scroll


def audit_navigation_geometry(session, state):
    page = session.page
    geometry = page.evaluate("""async () => {
        await new Promise(requestAnimationFrame);
        const header = document.querySelector('.tenant-topbar');
        const main = document.querySelector('main');
        const heading = main.querySelector('h1, h2, h3, h4, h5, h6, [role="heading"]');
        const headerBox = header.getBoundingClientRect();
        const mainBox = main.getBoundingClientRect();
        const headingBox = heading.getBoundingClientRect();
        const background = getComputedStyle(header).backgroundColor;
        const channels = background.match(/[\\d.]+/g).map(Number);
        const dropdown = document.querySelector('#userDropdown');
        const menuBox = dropdown.classList.contains('hidden') ? null : dropdown.getBoundingClientRect();
        const userButtonBox = document.querySelector('#userMenuBtn').getBoundingClientRect();
        const menuBackground = menuBox ? getComputedStyle(dropdown).backgroundColor : null;
        const menuChannels = menuBox ? menuBackground.match(/[\\d.]+/g).map(Number) : [];
        const relativeLuminance = components => {
            const [red, green, blue] = components.slice(0, 3).map(component => {
                const value = component / 255;
                return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
            });
            return red * 0.2126 + green * 0.7152 + blue * 0.0722;
        };
        const menuLabelColor = menuBox ? getComputedStyle(dropdown.querySelector('p')).color : null;
        const labelLuminance = menuBox ? relativeLuminance(menuLabelColor.match(/[\\d.]+/g).map(Number)) : 0;
        const menuLuminance = menuBox ? relativeLuminance(menuChannels) : 0;
        return {
            header_bottom: headerBox.bottom,
            main_top: mainBox.top,
            heading_top: headingBox.top,
            scroll_y: window.scrollY,
            header_background: background,
            header_opaque: (channels.length === 3 || channels[3] === 1)
                && getComputedStyle(header).opacity === '1',
            header_title_right: header.querySelector('.tenant-topbar__title').getBoundingClientRect().right,
            user_button_left: userButtonBox.left,
            user_menu_background: menuBackground,
            user_menu_label_color: menuLabelColor,
            user_menu_label_contrast: menuBox ? (Math.max(labelLuminance, menuLuminance) + 0.05)
                / (Math.min(labelLuminance, menuLuminance) + 0.05) : null,
            user_menu_opaque: !menuBox || ((menuChannels.length === 3 || menuChannels[3] === 1)
                && getComputedStyle(dropdown).opacity === '1'),
            user_menu_within_viewport: !menuBox || (menuBox.left >= 0 && menuBox.right <= innerWidth + 1
                && menuBox.top >= userButtonBox.bottom - 1 && menuBox.bottom <= innerHeight + 1),
            focused_element: document.activeElement.id || document.activeElement.tagName,
            content_occluded: mainBox.top < headerBox.bottom - 1 || headingBox.top < headerBox.bottom - 1
        };
    }""")
    geometry.update(path=urlsplit(page.url).path, state=state, width=page.viewport_size["width"])
    session.evidence.setdefault("navigation_geometry", []).append(geometry)
    probe_directory = os.environ.get("SPRINT07_VISUAL_PROBE_DIR")
    if (probe_directory and geometry["path"] == "/api/importacao-exportacao/view"
            and geometry["width"] == 320 and state in {"normal-scroll", "skip-to-content"}):
        directory = Path(probe_directory)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f'sprint07-{session.evidence["engine"]}-320-{state}.png'
        page.screenshot(path=str(directory / filename))
    if probe_directory and state == "user-dropdown":
        directory = Path(probe_directory)
        directory.mkdir(parents=True, exist_ok=True)
        variant = "home" if geometry["path"] == "/home" else "module"
        filename = f'sprint07-{session.evidence["engine"]}-{geometry["width"]}-user-dropdown-{variant}.png'
        page.screenshot(path=str(directory / filename))


def assert_audits(session):
    assert session.evidence["screens"]
    assert not [screen for screen in session.evidence["screens"] if screen["violations"] or screen["overflow"]]
    assert not [geometry for geometry in session.evidence.get("navigation_geometry", [])
                if (geometry["state"] != "normal-scroll" and geometry["content_occluded"])
                or not geometry["header_opaque"]
                or not geometry["user_menu_within_viewport"]
                or not geometry["user_menu_opaque"]
                or (geometry["user_menu_label_contrast"] is not None and geometry["user_menu_label_contrast"] < 4.5)
                or geometry["header_title_right"] > geometry["user_button_left"] + 1]


def submit_form(page, form, endpoint, method="POST", status=201):
    with page.expect_response(lambda response: urlsplit(response.url).path == endpoint and response.request.method == method) as saved:
        page.locator(f'{form} button[type="submit"]').click()
    assert saved.value.status == status, saved.value.text()
    page.wait_for_load_state("networkidle")
    return saved.value.json()["data"]


@pytest.mark.parametrize("width", [320, 768, 1440])
@pytest.mark.parametrize("group", SCREEN_GROUPS)
def test_all_screens_navigation_accessibility_responsive(sprint07_browser, group, width):
    session = sprint07_browser
    page = session.page
    page.set_viewport_size({"width": width, "height": 900})
    for path in SCREEN_GROUPS[group]:
        navigate(page, path)
        expect(page.locator("#screen-size-lock")).to_be_hidden()
        assert page.title().strip()
        assert page.locator("svg.lucide").count() > 0
        assert page.evaluate("Array.from(document.styleSheets).filter(sheet => sheet.href).every(sheet => sheet.cssRules.length > 0)")
        scroll_page_for_header_audit(page)
        audit_navigation_geometry(session, "normal-scroll")
        page.locator(".skip-link").focus()
        page.keyboard.press("Enter")
        expect(page.locator("main")).to_be_focused()
        audit_navigation_geometry(session, "skip-to-content")
        if width < 768:
            opener = page.locator(".tenant-topbar [data-sidebar-toggle]")
            opener.focus()
            page.keyboard.press("Enter")
            expect(page.locator(".sidebar-mobile-close")).to_be_focused()
            page.keyboard.press("Escape")
            expect(opener).to_be_focused()
            expect(page.locator("#tenantSidebar")).to_be_hidden()
            audit_navigation_geometry(session, "sidebar-focus-restored")
        audit_screen(session)
        if path in {"/home", "/api/importacao-exportacao/view"} and width in {320, 1440}:
            page.locator("#userMenuBtn").click()
            expect(page.locator("#userDropdown")).to_be_visible()
            expect(page.locator("#userDropdown")).to_have_css("opacity", "1")
            expect(page.locator("#userMenuBtn")).to_have_attribute("aria-expanded", "true")
            audit_screen(session, "user-dropdown")
            audit_navigation_geometry(session, "user-dropdown")
            page.keyboard.press("Escape")
            expect(page.locator("#userDropdown")).to_be_hidden()
            expect(page.locator("#userMenuBtn")).to_be_focused()
            audit_navigation_geometry(session, "user-menu-focus-restored")
    assert not session.evidence["http_errors"], session.evidence["http_errors"]
    assert_audits(session)


@pytest.mark.parametrize("width", [390, 1440])
def test_catalog_client_sale_stock_financial_audit_journey(sprint07_browser, transaction_app, width):
    session = sprint07_browser
    page = session.page
    page.set_viewport_size({"width": width, "height": 900})
    navigate(page, "/api/categorias/view")
    page.get_by_role("button", name="Nova categoria", exact=True).click()
    page.locator("#cadastro-nome").fill("Categoria Jornada 07")
    page.locator("#cadastro-descricao").fill("Catalogo criado no navegador")
    audit_screen(session, "create-category")
    category = submit_form(page, "#form-cadastro", "/api/categorias/")
    expect(page.locator("#categoria-table-body")).to_contain_text(category["nome"])

    navigate(page, "/api/produtos/view")
    page.get_by_role("button", name="Novo produto", exact=True).click()
    page.locator("#cadastro-nome").fill("Produto Jornada 07")
    page.locator("#cadastro-categoria_id").select_option(str(category["id"]))
    page.locator("#cadastro-empresa_id").select_option("1")
    page.locator("#cadastro-codigo_barras").fill("7891234567895")
    decimal_focus = page.evaluate("""async () => {
        const wholesale = document.querySelector('#cadastro-valor_atacado');
        const minimum = document.querySelector('#cadastro-quantidade_minima_atacado');
        wholesale.focus();
        const first = document.activeElement.id;
        minimum.focus();
        const immediate = document.activeElement.id;
        await new Promise(requestAnimationFrame);
        return {first, immediate, next_frame: document.activeElement.id};
    }""")
    session.evidence["decimal_focus"] = decimal_focus
    assert decimal_focus == {
        "first": "cadastro-valor_atacado",
        "immediate": "cadastro-quantidade_minima_atacado",
        "next_frame": "cadastro-quantidade_minima_atacado",
    }
    page.locator("#cadastro-valor_compra").fill("4,00")
    page.locator("#cadastro-valor_varejo").fill("12,50")
    page.locator("#cadastro-valor_atacado").fill("10,00")
    page.locator("#cadastro-quantidade_minima_atacado").fill("3")
    product_prices = page.locator("#form-cadastro").evaluate("""form => ({
        retail: form.querySelector('[name="valor_varejo"]').value,
        wholesale: form.querySelector('[name="valor_atacado"]').value,
        minimum: form.querySelector('[name="quantidade_minima_atacado"]').value
    })""")
    session.evidence["product_form_prices"] = product_prices
    assert product_prices == {"retail": "12,50", "wholesale": "10,00", "minimum": "3"}
    audit_screen(session, "create-product")
    product = submit_form(page, "#form-cadastro", "/api/produtos/")
    session.evidence["product_saved_prices"] = {
        key: product[key] for key in ("valor_varejo", "valor_atacado", "quantidade_minima_atacado")
    }
    assert Decimal(product["valor_varejo"]) == Decimal("12.50")
    assert Decimal(product["valor_atacado"]) == Decimal("10.00")
    assert product["quantidade_minima_atacado"] == 3
    expect(page.locator("#produto-table-body")).to_contain_text("Produto Jornada 07")

    navigate(page, "/api/clientes/view")
    page.get_by_role("button", name="Novo Cliente", exact=True).click()
    page.locator("#cliente-cadastro-nome").fill("Cliente Jornada 07")
    page.locator("#cliente-cadastro-documento").fill("52998224725")
    page.locator("#cliente-cadastro-email").fill("jornada07@example.test")
    page.locator("#cliente-cadastro-aceita-whatsapp").uncheck()
    audit_screen(session, "create-client")
    customer = submit_form(page, "#cliente-form-cadastro", "/api/clientes/")
    expect(page.locator("#cliente-table-body")).to_contain_text("Cliente Jornada 07")

    navigate(page, "/api/estoque/view")
    page.locator("#btn-nova-movimentacao").click()
    page.locator("#movimento-empresa_id").select_option("1")
    page.locator("#movimento-produto_empresa_id").select_option(str(product["id"]))
    page.locator("#movimento-quantidade").fill("7")
    page.locator("#movimento-observacao").fill("Entrada da jornada 07")
    audit_screen(session, "stock-entry")
    submit_form(page, "#form-movimentacao", "/api/estoque/movimentos/manual")
    expect(page.locator("#kpi-quantidade-total")).to_have_text("7")

    navigate(page, "/api/pdv/view")
    page.locator("#pdv-empresa").select_option("1")
    page.locator("#pdv-cliente").select_option(str(customer["id"]))
    product_button = page.locator(f'#pdv-produtos-grid button[onclick="adicionarAoCarrinho({product["produto_id"]})"]')
    product_button.click()
    product_button.click()
    expect(page.locator("#pdv-total-geral")).to_contain_text("25,00")
    page.locator("#pdv-open-payment-modal").click()
    page.locator(".pdv-payment-forma").select_option(label="Dinheiro")
    page.locator(".pdv-payment-valor").fill("25,00")
    audit_screen(session, "payment")
    page.locator("#pdv-confirm-payment-modal").click()
    finalize_state = page.locator("#pdv-finalizar-venda").evaluate("""button => ({
        disabled: button.disabled,
        transition_duration: getComputedStyle(button).transitionDuration
    })""")
    session.evidence["finalize_enabled_state"] = finalize_state
    assert finalize_state == {"disabled": False, "transition_duration": "0s"}
    page.locator("#pdv-finalizar-venda").click()
    audit_screen(session, "confirm-sale")
    with page.expect_response(lambda response: urlsplit(response.url).path == "/api/pdv/vendas" and response.request.method == "POST") as sold:
        page.locator("#pdv-confirm-submit").click()
    assert sold.value.status == 201, sold.value.text()
    expect(page.locator("#pdv-success-modal")).to_be_visible()
    with transaction_app.app_context():
        sale = Venda.query.one()
        sale_id = sale.id
        assert sale.cliente_id == customer["id"]
        assert sale.total == Decimal("25.00")
        assert ProdutoEmpresa.query.one().estoque_atual == 5
        assert MovimentoEstoque.query.count() == 2
        assert sum(entry.valor for entry in LancamentoFinanceiro.query.all()) == Decimal("25.00")
    with page.expect_popup() as receipt_info:
        page.locator("#pdv-success-print").click()
    receipt = receipt_info.value
    receipt.wait_for_load_state()
    expect(receipt.locator("body")).to_contain_text("Produto Jornada 07")
    expect(receipt.locator("body")).to_contain_text("25.00")
    receipt.close()
    page.locator('[data-close-modal="pdv-success-modal"]').click()

    navigate(page, "/api/estoque/view")
    expect(page.locator("#kpi-quantidade-total")).to_have_text("5")
    expect(page.locator("#movimento-table-body")).to_contain_text("Produto Jornada 07")
    expect(page.locator("#movimento-table-body")).to_contain_text("Saída")
    audit_screen(session, "stock-after-sale")
    navigate(page, "/api/financeiro/lancamentos/view")
    expect(page.locator("#financeiro-lancamentos-body")).to_contain_text("25,00")
    expect(page.locator("#financeiro-lancamentos-body")).to_contain_text("Dinheiro")
    expect(page.locator("#financeiro-lancamentos-body")).to_contain_text(str(sale_id))
    audit_screen(session, "financial-after-sale")
    navigate(page, "/api/auditoria/view")
    expect(page.locator("#audit-rows tr").first).to_be_visible()
    with transaction_app.app_context():
        audit = AuditLog.query.filter_by(tenant_id=1, action="pdv.sale_created", entity_id=str(sale_id)).one()
        assert audit.empresa_id == 1 and audit.status == "SUCCESS" and audit.request_id
    audit_text = page.locator("#audit-rows").inner_text()
    assert "pdv.sale_created" in audit_text and "SUCCESS" in audit_text
    assert "jornada07@example.test" not in audit_text and "52998224725" not in audit_text
    audit_screen(session, "audit-after-sale")
    session.evidence["journey"] = {"sale_id": sale_id, "total": "25.00", "remaining_stock": 5, "customer_id": customer["id"]}
    assert not session.evidence["http_errors"], session.evidence["http_errors"]
    assert_audits(session)


@pytest.mark.parametrize("width", [390, 1440])
def test_admin_role_employee_and_restricted_login_journey(sprint07_browser, transaction_app, width):
    session = sprint07_browser
    page = session.page
    page.set_viewport_size({"width": width, "height": 900})
    navigate(page, "/configuracoes/home")
    role_script = ORIGIN + "/static/js/modulos/role.js"
    pending_scripts = []

    def hold_role_script(route):
        pending_scripts.append(route)

    page.route(role_script, hold_role_script)
    try:
        with page.expect_request(role_script):
            page.locator('main a[href="/api/roles/view"]').click(no_wait_after=True)
        readiness = page.get_by_role("button", name="Nova Role", exact=True).evaluate("""button => ({
            disabled: button.disabled,
            initialized: Boolean(window.rolePage)
        })""")
        readiness["script_held"] = len(pending_scripts) == 1
        session.evidence["role_before_script"] = readiness
        assert readiness == {"disabled": True, "initialized": False, "script_held": True}
    finally:
        for route in pending_scripts:
            route.continue_()
        page.unroute(role_script, hold_role_script)
    expect(page.get_by_role("button", name="Nova Role", exact=True)).to_be_enabled()
    session.evidence["role_after_script"] = page.get_by_role("button", name="Nova Role", exact=True).evaluate("""button => ({
        disabled: button.disabled,
        initialized: Boolean(window.rolePage)
    })""")
    assert session.evidence["role_after_script"] == {"disabled": False, "initialized": True}
    page.get_by_role("button", name="Nova Role", exact=True).click()
    page.locator("#cadastro-nome").fill("Consulta Catalogo 07")
    page.locator("#cadastro-codigo").fill("consulta_catalogo_07")
    page.locator('[data-permission-code="visualizar_produto"]').check()
    audit_screen(session, "create-role")
    role = submit_form(page, "#form-cadastro", "/api/roles/")
    expect(page.locator("#role-table-body")).to_contain_text("Consulta Catalogo 07")
    navigate(page, "/api/funcionarios/view")
    page.get_by_role("button", name="Novo Funcionario", exact=True).click()
    for field, value in {"nome": "Consulta Jornada 07", "cpf": "52998224725", "usuario": "consulta07", "senha": PASSWORD}.items():
        page.locator(f"#cadastro-{field}").fill(value)
    page.locator("#cadastro-role_id").select_option(str(role["id"]))
    page.locator("#cadastro-empresa_id").select_option("1")
    audit_screen(session, "create-employee")
    submit_form(page, "#form-cadastro", "/api/funcionarios/")
    expect(page.locator("#funcionario-table-body")).to_contain_text("Consulta Jornada 07")
    page.locator("#input-busca").fill("consulta07")
    row = page.locator("#funcionario-table-body tr").filter(has_text="consulta07")
    row.get_by_role("button", name="Editar funcionario", exact=True).click()
    page.locator("#edicao-nome").fill("Consulta Atualizada 07")
    with page.expect_response(lambda response: "/api/funcionarios/" in response.url and response.request.method == "PUT") as edited:
        page.locator('#form-edicao button[type="submit"]').click()
    assert edited.value.status == 200, edited.value.text()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#funcionario-table-body")).to_contain_text("Consulta Atualizada 07")
    with transaction_app.app_context():
        employee = Funcionario.query.filter_by(usuario="consulta07").one()
        assert employee.nome == "Consulta Atualizada 07" and employee.role_id == role["id"]
        assert Role.query.filter_by(codigo="consulta_catalogo_07").one().tenant_id == 1
    logout_browser(page)
    login_browser(page, username="consulta07")
    navigate(page, "/api/produtos/view")
    expect(page.get_by_role("button", name="Novo produto", exact=True)).to_have_count(0)
    expect(page.locator('#tenantSidebar a[href="/api/roles/view"]')).to_have_count(0)
    expect(page.locator('#tenantSidebar a[href="/financeiro/home"]')).to_have_count(0)
    audit_screen(session, "restricted-catalog")
    response = page.goto(ORIGIN + "/api/roles/view", wait_until="domcontentloaded")
    assert response.status == 200
    expect(page).to_have_url(ORIGIN + "/home")
    expect(page.locator("body")).to_contain_text("Voce nao tem permissao para acessar essa area.")
    expect(page.locator("#role-table-body")).to_have_count(0)
    page.wait_for_load_state("networkidle")
    assert not session.evidence["http_errors"], session.evidence["http_errors"]
    assert_audits(session)


@pytest.mark.parametrize("width", [390, 1440])
def test_public_password_and_platform_provisioning_journey(sprint07_browser, width):
    session = sprint07_browser
    page = session.page
    page.set_viewport_size({"width": width, "height": 900})
    page.locator("#userMenuBtn").click()
    page.locator('#userDropdown a[href="/senha"]').click()
    expect(page.locator("#senha_atual")).to_be_visible()
    audit_screen(session, "password-change")
    navigate(page, "/home")
    logout_browser(page)
    audit_screen(session, "login")
    page.get_by_role("link", name="Redefinir senha com codigo do administrador").click()
    expect(page.locator("#token")).to_be_visible()
    audit_screen(session, "password-reset")
    page.go_back(wait_until="networkidle")
    login_browser(page, scope="platform")
    expect(page.locator("#platformTotalTenants")).to_have_text("2")
    audit_screen(session, "platform")
    page.locator("#openTenantModalBtn").click()
    for selector, value in {
        "tenantNome": "Tenant Jornada 07", "tenantEmpresaRazaoSocial": "Jornada Browser Ltda",
        "tenantEmpresaNomeFantasia": "Loja Jornada 07", "tenantEmpresaCnpj": "11222333000181",
        "tenantAdminNome": "Admin Jornada 07", "tenantAdminUsuario": "admin07",
        "tenantAdminCpf": "52998224725", "tenantAdminSenha": PASSWORD,
    }.items():
        page.locator(f"#{selector}").fill(value)
    audit_screen(session, "provision-tenant")
    submit_form(page, "#tenantForm", "/api/platform/tenants")
    expect(page.locator("#platformTotalTenants")).to_have_text("3")
    expect(page.locator("#platformTenantGrid")).to_contain_text("Tenant Jornada 07")
    logout_browser(page)
    login_browser(page, username="admin07", tenant="Tenant Jornada 07")
    navigate(page, "/api/produtos/view")
    expect(page.locator("#produto-table-body")).to_contain_text("Nenhum registro encontrado.")
    page.get_by_role("button", name="Novo produto", exact=True).click()
    expect(page.locator("#cadastro-empresa_id")).to_contain_text("Loja Jornada 07")
    expect(page.locator("#cadastro-empresa_id")).not_to_contain_text("Empresa 1-1")
    expect(page.locator("#cadastro-empresa_id")).to_have_css("color-scheme", "dark")
    expect(page.locator("#cadastro-data_validade")).to_have_css("color-scheme", "dark")
    page.locator("#cadastro-data_validade").fill("2030-12-31")
    expect(page.locator("#cadastro-data_validade")).to_have_value("2030-12-31")
    audit_screen(session, "new-tenant-isolation")
    assert not session.evidence["http_errors"], session.evidence["http_errors"]
    assert_audits(session)
