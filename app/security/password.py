from werkzeug.security import generate_password_hash, check_password_hash


def validate_password(password):
    if not isinstance(password, str) or len(password) < 12 or len(password) > 128:
        raise ValueError("A senha deve conter entre 12 e 128 caracteres.")
    if len(set(password)) < 5 or password.lower() in {"password1234", "123456789012", "oceanblue1234"}:
        raise ValueError("Escolha uma senha menos previsivel.")

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return check_password_hash(hashed, password)
