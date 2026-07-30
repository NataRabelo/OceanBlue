# Validacao de ambiente - Sprint 2

## Escopo

Validacao realizada em 30/07/2026 no projeto `pdv`, dentro de `C:\Users\Rabel\OneDrive\Documentos\07.Sistemas\14. OceanBlue`.

## Git

- A raiz informada `14. OceanBlue` nao e um repositorio Git.
- O repositorio valido esta em `14. OceanBlue/pdv`.
- Branch atual: `main`.
- Estado inicial observado: `README.md` modificado e base documental da Sprint 1 ainda nao rastreada pelo Git.
- Estado apos Sprint 2: alem dos arquivos anteriores, ha alteracoes em boleto, fiscal, template financeiro, teste de boleto, nova tela de boletos e novos documentos da Sprint 2.

## Execucao local

Fluxo documentado e coerente com o projeto:

```bash
cd pdv
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
$env:FLASK_APP = "wsgi.py"
flask db upgrade
flask seed
flask run
```

O arquivo `wsgi.py` cria a aplicacao via `create_app()`. Em desenvolvimento, `FLASK_ENV` padrao e `development`; em producao, `app/config.py` exige `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY` e `FIELD_ENCRYPTION_KEY`.

## Docker e Gunicorn

- `Dockerfile` usa `python:3.12-slim`, instala `requirements.txt`, prepara `docker-entrypoint.sh`, configura `FLASK_APP=wsgi.py` e executa Gunicorn em `0.0.0.0:5000`.
- `docker-entrypoint.sh` aguarda `DATABASE_URL`, testa a conexao SQLAlchemy, roda `flask db upgrade` e inicia o comando final.
- `docker-compose.yml` da aplicacao publica `127.0.0.1:5000:5000`, usa `.env` e depende da rede externa `blueocean_network`.
- `infra/docker-compose.yml` define Postgres 16 e backup, tambem usando rede/volume externos.

## Variaveis de ambiente

`.env.example` existe e cobre:

- `FLASK_ENV`, `FLASK_DEBUG`
- `DATABASE_URL`
- `SECRET_KEY`, `JWT_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`
- limites e seguranca HTTP/CSRF/proxy
- credenciais iniciais de platform owner
- variaveis de senha de certificado fiscal por empresa

Ponto de atencao: em producao, `DATABASE_URL` nao pode apontar para SQLite e os segredos precisam ter pelo menos 32 caracteres.

## Dependencias

`requirements.txt` contem Flask 3, SQLAlchemy, Flask-Migrate, JWT, Postgres, dotenv, marshmallow, Gunicorn, WeasyPrint, MercadoPago e OpenPyXL. Para emissao fiscal real, ainda nao ha dependencia identificada para assinatura/transmissao SEFAZ.

## Testes

Comando executado:

```bash
.venv/Scripts/python.exe -m pytest -q
```

Resultado inicial da Sprint 2:

- 48 testes passaram.
- 10 warnings SQLAlchemy relacionados a identity map em testes de fluxo PDV/financeiro.

Resultado apos correcoes:

- `tests/test_boleto_service.py`: 2 testes passaram, incluindo cobertura contra reaplicacao cumulativa de juros/multa.

## Divergencias e recomendacoes

- Documentar explicitamente que o repositorio oficial e `pdv`, nao a pasta pai.
- Confirmar se a stack `infra/` da pasta pai e `pdv/infra/` continuam ambas oficiais.
- Criar checklist de bootstrap Docker: rede `blueocean_network`, volume `blueocean_postgres_data`, `.env` e usuario/senha Postgres.
- Definir armazenamento persistente para XML fiscal, PDF/HTML de boleto, remessa/retorno CNAB e certificados.
