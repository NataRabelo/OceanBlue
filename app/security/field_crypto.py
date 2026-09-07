import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from app.security.secrets import load_field_keys


class FieldCrypto:
    PREFIX = "enc:v2:"
    LEGACY_PREFIX = "enc:v1:"

    @classmethod
    def encrypt(cls, value):
        if value in (None, ""):
            return None
        text = str(value)
        if text.startswith("enc:"):
            text = cls.decrypt(text)
        keys, active = cls._keys()
        payload = cls._fernet(keys[active]).encrypt(text.encode()).decode()
        return f"{cls.PREFIX}{active}:{payload}"

    @classmethod
    def decrypt(cls, value):
        if value in (None, ""):
            return None
        text = str(value)
        try:
            if text.startswith(cls.PREFIX):
                identifier, token = text[len(cls.PREFIX):].split(":", 1)
                keys, active = cls._keys()
                return cls._fernet(keys[identifier]).decrypt(token.encode()).decode()
            if text.startswith(cls.LEGACY_PREFIX):
                raw = base64.b64decode(text[len(cls.LEGACY_PREFIX):], altchars=b"-_", validate=True)
                if len(raw) < 48:
                    raise ValueError()
                nonce, mac, ciphertext = raw[:16], raw[16:48], raw[48:]
                key = hashlib.sha256(current_app.config["FIELD_ENCRYPTION_KEY"].encode()).digest()
                if not hmac.compare_digest(mac, hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()):
                    raise ValueError()
                stream = bytearray()
                counter = 0
                while len(stream) < len(ciphertext):
                    stream.extend(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
                    counter += 1
                return bytes(left ^ right for left, right in zip(ciphertext, stream)).decode()
            if text.startswith("enc:"):
                raise ValueError()
            return text
        except (InvalidToken, ValueError, KeyError, UnicodeError):
            raise ValueError("Campo sensivel invalido ou chave indisponivel.") from None

    @classmethod
    def is_encrypted(cls, value):
        return isinstance(value, str) and value.startswith("enc:")

    @staticmethod
    def _fernet(secret):
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))

    @staticmethod
    def _keys():
        config = current_app.config
        if config.get("FIELD_ENCRYPTION_KEYS") or not current_app.debug and not current_app.testing:
            return load_field_keys(config)
        return {"primary": config["FIELD_ENCRYPTION_KEY"]}, "primary"
