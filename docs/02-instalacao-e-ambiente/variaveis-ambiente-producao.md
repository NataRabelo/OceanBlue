# Variaveis de ambiente - producao

## Obrigatorias

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `FIELD_ENCRYPTION_KEY`
- `OCEANBLUE_STORAGE_PATH`

## Recomendadas

- `ASAAS_TIMEOUT_SECONDS`
- `FOCUS_NFE_TIMEOUT_SECONDS`
- `FLASK_ENV=production`

## Observacoes

Tokens Asaas e Focus NFe sao configurados por empresa/tenant e salvos criptografados. A chave `FIELD_ENCRYPTION_KEY` nao pode ser perdida ou alterada sem plano de rotacao, pois ela protege esses segredos.
