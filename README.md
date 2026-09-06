# OceanBlue PDV

OceanBlue PDV e um sistema web Flask para operacao de varejo em modelo SaaS multi-tenant. O projeto combina PDV, estoque, financeiro, clientes, cashback, mensageria, permissoes, administracao de tenants, fiscal e base inicial para boletos.

## Stack principal

- Python 3.12
- Flask 3
- Flask-SQLAlchemy
- Flask-Migrate/Alembic
- PostgreSQL via `DATABASE_URL`
- JWT em cookies com CSRF
- Templates Jinja2, CSS e JavaScript modular
- Docker, Docker Compose e Gunicorn

## Como rodar

Para validar um checkout limpo sem `.env`:

```sh
docker compose -f compose.test.yml up --build --abort-on-container-exit --exit-code-from test
```

Veja [instalacao, testes e homologacao](docs/02-instalacao-e-ambiente/como-rodar-o-projeto.md) e [evidencias da Sprint 1 de producao](docs/evidencias/producao/sprint-01-execucao.md).

1. Crie o arquivo `.env` a partir de `.env.example`.
2. Configure `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY` e `FIELD_ENCRYPTION_KEY`.
3. Instale dependencias com `pip install --require-hashes -r requirements.txt` ou use Docker.
4. Execute as migrations com `flask db upgrade`.
5. Use `flask seed` apenas em demonstracao isolada: ele cria senhas fixas e nao e apropriado para producao.
6. Inicie a aplicacao com `flask run` em desenvolvimento ou `docker compose up -d --build` em ambiente Docker.

## Documentacao

A nova base documental da Sprint 1 esta em `docs/`. O relatorio executivo esta em `relatorio-sprint-1/resumo-executivo.md`.

Documentos legados foram preservados em `docs/99-legado-ou-backup/` antes da reorganizacao.

## Situacao atual de boleto e nota fiscal

- Boleto: existe base de modelos, migration, repository, service e endpoints para cadastro, parcelas, regras de juros/multa e baixa. Nao ha evidencia de integracao bancaria real, remessa CNAB efetiva, registro em API bancaria ou geracao real de PDF.
- Nota fiscal: existe modulo fiscal com configuracao por empresa, prevalidacao, criacao de nota e geracao de XML interno de NFC-e. Nao ha autorizacao real na SEFAZ, assinatura digital, transmissao, consulta de protocolo real ou cancelamento fiscal.

## Proximos passos recomendados

Use `docs/10-planejamento-sprints/plano-sprint-2.md` como guia para priorizar correcao de bugs visiveis, validacao de ambiente, decisao de integradores externos e desenho funcional de boleto/fiscal antes de implementar emissao real.
