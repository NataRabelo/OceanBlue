import ipaddress
import socket
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler

from flask import current_app


def validate_host(host, port):
    if not current_app.testing:
        raise PermissionError("Provedores externos bloqueados nesta versao.")
    allowed = {value.strip().lower() for value in current_app.config.get("OUTBOUND_ALLOWED_HOSTS", "").split(",") if value.strip()}
    if not host or host.lower() not in allowed:
        raise PermissionError("Destino de comunicacao nao autorizado pelo operador da plataforma.")
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
            raise ValueError()
    except (OSError, ValueError):
        raise PermissionError("Destino de comunicacao indisponivel.") from None


def validate_webhook(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
            raise ValueError()
    except (ValueError, TypeError):
        raise PermissionError("A comunicacao exige uma URL HTTPS autorizada.") from None
    validate_host(parsed.hostname, 443)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise PermissionError("Redirecionamento de comunicacao bloqueado.")
