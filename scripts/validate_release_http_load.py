from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
import math
import ssl
import time
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener, urlopen


ORIGIN = "https://proxy:8443"


class LoginForm(HTMLParser):
    def handle_starttag(self, tag, attributes):
        fields = dict(attributes)
        if tag == "input" and fields.get("name") == "login_csrf":
            self.token = fields["value"]


def main():
    context = ssl.create_default_context(cafile="/proof-tls/fullchain.pem")
    cookies = CookieJar()
    opener = build_opener(HTTPSHandler(context=context), HTTPCookieProcessor(cookies))
    with opener.open(ORIGIN + "/login", timeout=20) as response:
        form = LoginForm()
        form.feed(response.read().decode())
    payload = urlencode({"scope": "tenant", "tenant": "Operational proof", "usuario": "proof-only",
        "senha": "Synthetic-proof!2026", "login_csrf": form.token}).encode()
    with opener.open(ORIGIN + "/login", payload, timeout=20) as response:
        assert response.url == ORIGIN + "/home", "Synthetic proof login failed"
    cookie_header = "; ".join(f"{cookie.name}={cookie.value}" for cookie in cookies)
    assert any(cookie.name == "access_token_cookie" for cookie in cookies)
    paths = (("/api/pdv/vendas?empresa_id=1", 3), ("/api/financeiro/lancamentos?empresa_id=1", 3),
             ("/api/estoque/movimentos?empresa_id=1", 3), ("/api/auditoria/", 1))

    def read(target):
        path, minimum_rows = target
        started = time.perf_counter()
        with urlopen(Request(ORIGIN + path, headers={"Cookie": cookie_header}), context=context, timeout=20) as response:
            assert response.status == 200
            assert len(response.headers["X-Request-ID"]) == 32
            result = json.load(response)
            assert isinstance(result["data"], list) and len(result["data"]) >= minimum_rows, (path, minimum_rows)
            return {"path": path.split("?")[0], "seconds": time.perf_counter() - started,
                    "rows": len(result["data"]), "request_id": response.headers["X-Request-ID"]}

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as executor:
        requests = list(executor.map(read, paths * 30))
    elapsed = time.perf_counter() - started
    times = sorted(record["seconds"] for record in requests)
    assert len({record["request_id"] for record in requests}) == len(requests)
    assert times[math.ceil(len(times) * .95) - 1] < 10, "Synthetic release latency gate exceeded"
    print(json.dumps({"requests": len(requests), "concurrency": 8, "errors": 0, "elapsed_seconds": elapsed,
        "requests_per_second": len(requests) / elapsed, "p50_seconds": times[math.ceil(len(times) * .50) - 1],
        "p95_seconds": times[math.ceil(len(times) * .95) - 1], "max_seconds": max(times),
        "transport": "TLS with verified synthetic certificate -> nginx -> Gunicorn -> PostgreSQL",
        "dataset": "3 sales, 3 ledger entries, 94 stock units; authenticated read-only business workload",
        "scope": "Synthetic single-host regression gate p95<10s, not production SLA or capacity planning. Login/audit occurs after snapshot and is not part of recovery RPO proof.",
        "samples": requests}, indent=2))


if __name__ == "__main__":
    main()
