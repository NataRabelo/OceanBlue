# Como rodar o projeto

## Pre-requisitos

- Python 3.12.
- PostgreSQL acessivel por `DATABASE_URL`.
- Docker e Docker Compose, caso use ambiente containerizado.

## Variaveis de ambiente

O projeto possui `.env.example` e `.env`. Variaveis criticas:

- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `FIELD_ENCRYPTION_KEY`
- `FLASK_ENV`
- `FORCE_HTTPS`
- `TRUST_PROXY_HEADERS`
- `MAX_CONTENT_LENGTH`
- variaveis relacionadas a certificado fiscal, quando fiscal real for ativado.

Em producao, `app/config.py` exige segredos com pelo menos 32 caracteres e bloqueia SQLite.

## Rodando localmente

```bash
cd pdv
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
set FLASK_APP=wsgi.py
flask db upgrade
flask seed
flask run
```

No PowerShell, prefira `$env:FLASK_APP='wsgi.py'` em vez de `set`.

## Rodando com Docker

```bash
cd pdv
docker compose up -d --build
```

O compose da aplicacao espera a rede externa `blueocean_network`. A documentacao legada indica o uso de scripts em `scripts/` para preparar infra e deploy.

## Pontos de atencao

- Confirmar se a stack de banco em `infra/` e a stack em `pdv/infra/` estao ambas em uso ou se uma delas e sobra historica.
- Validar conteudo real do `.env.example` antes de onboarding de novos ambientes.
- Confirmar procedimento oficial de seed em ambiente produtivo.
- Confirmar onde serao persistidos XML fiscal, PDFs/HTML de boleto e certificados.
