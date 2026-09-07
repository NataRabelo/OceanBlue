import json
import re


def validate_secret(name, value):
    lowered = str(value or "").lower()
    if len(str(value or "")) < 32 or len(set(str(value))) < 10 or any(
        marker in lowered for marker in ("change-me", "changeme", "dev-secret", "your-secret", "replace-me")
    ):
        raise RuntimeError(f"Segredos fracos em producao: {name}")


def load_field_keys(config):
    raw = config.get("FIELD_ENCRYPTION_KEYS")
    try:
        keys = json.loads(raw) if isinstance(raw, str) and raw else raw
        if keys is None:
            keys = {"primary": config["FIELD_ENCRYPTION_KEY"]}
        if not isinstance(keys, dict) or not keys or len(keys) > 10:
            raise ValueError()
        for identifier, secret in keys.items():
            if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", identifier) or not isinstance(secret, str):
                raise ValueError()
            validate_secret("FIELD_ENCRYPTION_KEYS", secret)
        active = config.get("FIELD_ENCRYPTION_ACTIVE_KEY_ID") or "primary"
        if active not in keys or len(set(keys.values())) != len(keys):
            raise ValueError()
        return keys, active
    except (ValueError, TypeError, KeyError):
        raise RuntimeError("Configuracao de chaves de campos invalida.") from None
