# Visao geral do sistema

## Objetivo

OceanBlue PDV e uma aplicacao web para gestao operacional de varejo. O sistema atende empresas em modelo multi-tenant e organiza funcionalidades de venda, estoque, financeiro, clientes, cashback, mensageria, permissoes, fiscal e administracao SaaS.

## Escopo funcional encontrado

- Autenticacao de funcionarios e donos de plataforma.
- Gestao de tenants, empresas, planos e administradores.
- Cadastro de produtos, categorias, funcionarios, roles e permissoes.
- PDV com carrinho, venda, pagamentos, comprovante e cancelamentos.
- Estoque com saldos, movimentos, alertas, indicadores e notificacoes.
- Financeiro com dashboard, lancamentos, fechamento de caixa e relatorios.
- Clientes com carteira, cashback, historico de vendas e mensageria.
- Cupons e adiantamentos/vales de funcionario.
- Importacao/exportacao em lote por planilhas.
- Fiscal com configuracao NFC-e, prevalidacao e XML operacional interno.
- Boletos com estrutura de cadastro, parcelas, bancos emissores, juros/multa e baixa.

## Stack identificada

- Linguagem: Python.
- Framework web: Flask.
- ORM: Flask-SQLAlchemy.
- Migrations: Flask-Migrate/Alembic.
- Banco esperado: PostgreSQL.
- Autenticacao: Flask-JWT-Extended com cookies e CSRF.
- Templates: Jinja2.
- Frontend: JavaScript modular e CSS por modulo.
- Infra: Docker, Docker Compose, Gunicorn.
- Bibliotecas relevantes: `psycopg2-binary`, `python-dotenv`, `marshmallow`, `weasyprint`, `mercadopago`, `openpyxl`.

## Observacoes importantes da Sprint 1

O projeto esta em `pdv/`. A raiz acima contem tambem `infra/`, `backups/`, `.venv` e `.pytest_cache`. A varredura nao encontrou um repositorio Git ativo na raiz consultada, o que reduz rastreabilidade de mudancas.

Nao foram feitas refatoracoes nem alteracoes de regra de negocio nesta sprint.
