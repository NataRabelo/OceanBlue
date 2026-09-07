import json
import os
from urllib.request import urlopen

from app import create_app


def main():
    app = create_app()
    assert app.config["ENV"] == "production"
    assert not app.debug
    assert app.config["JWT_COOKIE_SECURE"]
    assert app.config["JWT_COOKIE_CSRF_PROTECT"]
    assert os.geteuid() != 0
    for endpoint in ("health", "ready"):
        with urlopen(f"http://127.0.0.1:5000/api/{endpoint}", timeout=4) as response:
            payload = json.load(response)
            assert response.status == 200
            assert payload["status"] == "ok"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            if endpoint == "ready":
                assert payload["database"] == "ok"
            print(json.dumps({"endpoint": endpoint, "response": payload}), flush=True)
    print("PRODUCTION NONROOT SECURE CONFIG HTTP SMOKE OK", flush=True)


if __name__ == "__main__":
    main()
