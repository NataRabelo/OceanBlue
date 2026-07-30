# Arquitetura atual

## Padrao geral

A aplicacao segue uma arquitetura Flask em camadas:

- `app/controllers`: blueprints HTTP, renderizacao de templates e endpoints JSON.
- `app/services`: regras de aplicacao, validacoes, transacoes e orquestracao.
- `app/repositorys`: acesso a dados e consultas SQLAlchemy.
- `app/models/db.py`: modelos ORM, enums, constraints, indices e relacionamentos.
- `app/templates`: telas Jinja2, componentes, emails e relatorios.
- `app/static/js`: scripts por modulo e utilitarios de frontend.
- `app/static/css`: estilos core, forms e modulos.
- `migrations`: historico Alembic.
- `tests`: testes unitarios/integracao de servicos, seguranca e fluxos.

## Inicializacao

`wsgi.py` instancia a aplicacao. `app/__init__.py` cria o app, carrega configuracao, registra extensoes, headers de seguranca, blueprints, context processors e comandos CLI.

## Blueprints registrados

- `/api`: healthcheck.
- auth sem prefixo: login/logout.
- main sem prefixo: home, homes por area, favicon.
- `/api/produtos`
- `/api/clientes`
- `/api/cupons`
- `/api/adiantamentos`
- `/api/estoque`
- `/api/pdv`
- `/api/financeiro`
- `/api/financeiro/boletos`
- `/api/fiscal`
- `/api/importacao-exportacao`
- `/api/categorias`
- `/api/funcionarios`
- `/api/roles`
- `/api/permissions`
- plataforma em rotas `/platform/home` e `/api/platform/...`.

## Seguranca

O sistema usa JWT em cookies, CSRF, decorators de permissao, headers de seguranca, rate limit de login e validacao de escopo por tenant/empresa. Ha camada dedicada em `app/security`.

## Multi-tenant

A maior parte das entidades usa `tenant_id`. Acesso por empresa e permissao e centralizado em `AcessoEmpresaService`. O bootstrap de tenant cria dados padrao como permissoes, roles, categorias financeiras, formas de pagamento e tipos de operacao.

## Configuracoes importantes

- `app/config.py`: ambiente, segredos, banco, JWT, cookies, limites e HTTPS.
- `.env` e `.env.example`: variaveis locais.
- `Dockerfile`: imagem Python 3.12 slim e Gunicorn.
- `docker-compose.yml`: servico `api` em `127.0.0.1:5000`.
- `infra/docker-compose.yml`: stack de banco/infra.
- `docker-entrypoint.sh`: aguarda banco e executa `flask db upgrade`.
