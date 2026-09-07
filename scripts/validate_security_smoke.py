import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request_status(path, headers=None):
    try:
        with urlopen(Request("http://127.0.0.1:5000" + path, headers=headers or {}), timeout=15) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-down", action="store_true")
    arguments = parser.parse_args()
    health, health_body = request_status("/api/health")
    ready, ready_body = request_status("/api/ready")
    assert health == 200 and json.loads(health_body)["status"] == "ok"
    assert ready == (503 if arguments.database_down else 200)
    assert json.loads(ready_body)["database"] == ("error" if arguments.database_down else "ok")
    for header, value in {"X-Forwarded-Proto": "https", "X-Forwarded-Protocol": "ssl", "X-Forwarded-Ssl": "on"}.items():
        status, body = request_status("/login", {header: value, "X-Forwarded-For": "127.0.0.1"})
        assert status == 403, (header, status)
    if arguments.database_down:
        from app import create_app
        client = create_app().test_client()
        assert client.get("/login", base_url="https://localhost").status_code == 200
        with client.session_transaction(base_url="https://localhost") as browser_session:
            csrf = browser_session["login_csrf"]
        response = client.post("/login", base_url="https://localhost", data={"login_csrf": csrf,
                               "scope": "platform", "usuario": "unavailable", "senha": "invalid"})
        assert response.status_code == 500
        assert response.json == {"success": False, "message": "Nao foi possivel concluir a operacao."}
        assert not any("access_token_cookie=" in value for value in response.headers.getlist("Set-Cookie"))
    print(json.dumps({"database_down": arguments.database_down, "health": health, "ready": ready,
                      "forged_proxy_login": 403, "login_fails_closed": arguments.database_down}))


if __name__ == "__main__":
    main()
