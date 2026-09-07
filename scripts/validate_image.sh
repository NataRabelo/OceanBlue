#!/bin/sh
set -eu

image=${1:?Informe a imagem de producao}

docker run --rm --network none --entrypoint python "$image" -m pip check

docker run --rm --network none --entrypoint python "$image" -c '
from app.config import get_config, ProductionConfig
assert get_config() is ProductionConfig
print("IMAGE DEFAULT PRODUCTION OK")
'

for variable in DATABASE_URL SECRET_KEY JWT_SECRET_KEY FIELD_ENCRYPTION_KEY; do
    if output=$(docker run --rm --network none \
        -e DATABASE_URL=postgresql+psycopg2://unused:unused@127.0.0.1/oceanblue \
        -e SECRET_KEY=validation-session-secret-32-characters \
        -e JWT_SECRET_KEY=validation-jwt-secret-32-characters \
        -e FIELD_ENCRYPTION_KEY=validation-field-secret-32-characters \
        -e DB_WAIT_TIMEOUT_SECONDS=1 \
        -e "$variable=" "$image" true 2>&1); then
        printf '%s\n' "ERROR: imagem iniciou sem $variable"
        exit 1
    fi
    case "$output" in
        *"Variaveis obrigatorias ausentes em producao: $variable"*)
            printf '%s\n' "IMAGE REJECTS MISSING $variable BEFORE DATABASE OK" ;;
        *) printf '%s\n' "$output"; exit 1 ;;
    esac
done
