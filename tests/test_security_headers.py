import unittest

from flask import Flask

from app.security.headers import register_security_headers


class SecurityHeadersHttpsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["FORCE_HTTPS"] = True
        register_security_headers(self.app)

        @self.app.route("/api/health")
        def healthcheck():
            return "ok"

        self.client = self.app.test_client()

    def test_loopback_http_request_bypasses_https_enforcement_for_internal_healthcheck(self):
        response = self.client.get(
            "/api/health",
            environ_overrides={"REMOTE_ADDR": "127.0.0.1", "wsgi.url_scheme": "http"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "ok")

    def test_external_http_request_still_requires_https(self):
        response = self.client.get(
            "/api/health",
            environ_overrides={"REMOTE_ADDR": "10.0.0.50", "wsgi.url_scheme": "http"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("HTTPS obrigatorio em producao", response.get_data(as_text=True))

    def test_forwarded_for_loopback_does_not_bypass_https_enforcement(self):
        response = self.client.get(
            "/api/health",
            headers={"X-Forwarded-For": "127.0.0.1"},
            environ_overrides={"REMOTE_ADDR": "10.0.0.50", "wsgi.url_scheme": "http"},
        )

        self.assertEqual(response.status_code, 403)

    def test_forwarded_proto_is_not_trusted_without_proxyfix(self):
        response = self.client.get("/api/health", headers={"X-Forwarded-Proto": "https"},
                                   environ_overrides={"REMOTE_ADDR": "10.0.0.50"})
        self.assertEqual(response.status_code, 403)

    def test_loopback_cannot_bypass_https_on_login(self):
        response = self.client.get("/login", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
