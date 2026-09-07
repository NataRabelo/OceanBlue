import os
import subprocess
import sys

import pytest


def run_startup(overrides):
    environment = {
        name: os.environ[name]
        for name in ("PATH", "HOME", "LANG", "SYSTEMROOT")
        if name in os.environ
    }
    environment.update({
        "FLASK_ENV": "production",
        "FLASK_SKIP_DOTENV": "1",
        "DATABASE_URL": "postgresql+psycopg2://unused:unused@127.0.0.1/oceanblue",
        "SECRET_KEY": "validation-session-secret-32-characters",
        "JWT_SECRET_KEY": "validation-jwt-secret-32-characters",
        "FIELD_ENCRYPTION_KEY": "validation-field-secret-32-characters",
    })
    for name, value in overrides.items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
    return subprocess.run(
        [sys.executable, "-c", (
            "from app import create_app; app = create_app(); "
            "assert not app.debug; "
            "assert app.config['JWT_COOKIE_CSRF_PROTECT']; "
            "assert app.config['JWT_COOKIE_SECURE']; "
            "assert app.config['SESSION_COOKIE_SECURE']; "
            "print('PRODUCTION CONFIG OK')"
        )],
        env=environment, capture_output=True, text=True, timeout=20,
    )


def test_production_startup_uses_secure_configuration():
    result = run_startup({})
    assert result.returncode == 0, result.stderr
    assert "PRODUCTION CONFIG OK" in result.stdout


@pytest.mark.parametrize("variable", [
    "DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY", "FIELD_ENCRYPTION_KEY",
])
@pytest.mark.parametrize("value", [None, ""])
def test_production_startup_rejects_missing_variables(variable, value):
    result = run_startup({variable: value})
    assert result.returncode != 0
    assert "Variaveis obrigatorias ausentes" in result.stderr
    assert variable in result.stderr


@pytest.mark.parametrize("variable", ["SECRET_KEY", "JWT_SECRET_KEY", "FIELD_ENCRYPTION_KEY"])
def test_production_startup_rejects_each_weak_secret(variable):
    result = run_startup({variable: "short"})
    assert result.returncode != 0
    assert "Segredos fracos" in result.stderr
    assert variable in result.stderr


@pytest.mark.parametrize("environment", ["prod", "", "production-typo"])
def test_startup_rejects_unknown_environment(environment):
    result = run_startup({"FLASK_ENV": environment})
    assert result.returncode != 0
    assert "FLASK_ENV invalido" in result.stderr


@pytest.mark.parametrize("database_url", [
    "sqlite:///production.db",
    "mysql://unused:private-database-password@localhost/oceanblue",
    "malformed-private-database-password",
    "postgresql://unused:private-database-password@localhost:not-a-port/oceanblue",
])
def test_production_startup_rejects_invalid_database_without_leaking_url(database_url):
    result = run_startup({"DATABASE_URL": database_url})
    assert result.returncode != 0
    assert "DATABASE_URL deve ser uma URL PostgreSQL valida" in result.stderr
    assert "private-database-password" not in result.stderr
