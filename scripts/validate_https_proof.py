import json
import ssl
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    context = ssl.create_default_context(cafile="/proof-tls/fullchain.pem")
    with urlopen("https://proxy:8443/login", context=context, timeout=10) as response:
        assert response.status == 200
        assert response.headers["Strict-Transport-Security"].startswith("max-age=")
        assert len(response.headers["X-Request-ID"]) == 32
        assert "cdn" not in response.headers["Content-Security-Policy"]
    with urlopen("https://proxy:8443/readiness", context=context, timeout=10) as response:
        assert json.load(response)["storage"] == "ok"
    with urlopen(Request("https://proxy:9443/metrics", headers={"Authorization": "Bearer synthetic-metrics-token-32-characters-long"}), context=context, timeout=10) as response:
        assert b"oceanblue_requests_total" in response.read()
    try:
        urlopen("https://proxy:9443/metrics", context=context, timeout=10)
        raise AssertionError("Metrics accepted without token")
    except HTTPError as response:
        assert response.code == 404
    for path in ("/api/fiscal/view", "/api/financeiro/boletos/view", "/metrics"):
        try:
            urlopen("https://proxy:8443" + path, context=context, timeout=10)
            raise AssertionError("Blocked route accepted")
        except HTTPError as response:
            assert response.code == 404
    try:
        urlopen(Request("http://app:5000/login", headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "127.0.0.1"}), timeout=10)
        raise AssertionError("Forged proxy accepted")
    except HTTPError as response:
        assert response.code == 403
    print("TLS VERIFIED with certificate validation; trusted proxy 200; direct forged headers 403; fiscal/boleto/metrics 404; HSTS and request ID present.")


if __name__ == "__main__":
    main()
