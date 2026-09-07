from flask import g, request


def register_security_headers(app):
    @app.before_request
    def enforce_https():
        g.pop("tenant_scope", None)
        g.pop("auth_user", None)
        if not app.config.get("FORCE_HTTPS"):
            return None

        # Docker healthcheck interno usa HTTP puro via loopback, sem liberar bypass para trafego externo.
        if request.remote_addr in {"127.0.0.1", "::1"} and request.path in {"/api/health", "/api/ready"}:
            return None

        if request.is_secure:
            return None

        return ("HTTPS obrigatorio em producao.", 403)

    @app.after_request
    def add_security_headers(response):
        if request.path in {"/login", "/senha", "/redefinir-senha"} or request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

        if app.config.get("JWT_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response
