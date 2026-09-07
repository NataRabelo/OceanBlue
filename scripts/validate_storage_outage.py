import json
import os
from pathlib import Path

from scripts.validate_security_smoke import request_status


def main():
    root = Path(os.getenv("STORAGE_ROOT", "/app/instance/storage"))
    original = root.stat().st_mode & 0o777
    try:
        root.chmod(0o500)
        assert request_status("/health")[0] == 200
        status, payload = request_status("/readiness")
        assert status == 503 and json.loads(payload)["storage"] == "error"
        from app import create_app
        client = create_app().test_client()
        response = client.post("/login", base_url="https://localhost", data={"private": "must-not-leak"})
        assert response.status_code == 503 and b"must-not-leak" not in response.data
        print("STORAGE REAL PERMISSION FAILURE: health 200, readiness 503, writes 503")
    finally:
        root.chmod(original)
    assert request_status("/readiness")[0] == 200
    print("STORAGE RECOVERY VERIFIED")


if __name__ == "__main__":
    main()
