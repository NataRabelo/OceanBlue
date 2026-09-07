#!/bin/sh
set -e

python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text

from app.config import get_config

get_config().validate_runtime()

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    sys.exit("DATABASE_URL obrigatoria")

engine = create_engine(database_url, pool_pre_ping=True)
deadline = time.time() + int(os.environ.get("DB_WAIT_TIMEOUT_SECONDS", "60"))
last_error = None

while time.time() < deadline:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        break
    except Exception as exc:
        last_error = type(exc).__name__
        print(f"Aguardando banco de dados: {last_error}", flush=True)
        time.sleep(2)
else:
    raise SystemExit(f"Banco indisponivel apos aguardar: {last_error}")
PY

flask db upgrade

exec "$@"
