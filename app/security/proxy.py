import ipaddress

from werkzeug.middleware.proxy_fix import ProxyFix


class TrustedProxy:
    def __init__(self, application, networks):
        self.application = application
        self.networks = [ipaddress.ip_network(value.strip()) for value in networks.split(",") if value.strip()]
        self.forwarded = ProxyFix(application, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)

    def __call__(self, environ, start_response):
        try:
            peer = ipaddress.ip_address(environ.get("REMOTE_ADDR", ""))
            trusted = any(peer in network for network in self.networks)
        except ValueError:
            trusted = False
        if trusted:
            return self.forwarded(environ, start_response)
        return self.application(environ, start_response)
