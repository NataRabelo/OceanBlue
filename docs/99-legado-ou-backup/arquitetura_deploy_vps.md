# OceanBlue - Documento Estrutural para Deploy em VPS

## 1. Objetivo do documento

Este documento descreve a estrutura tecnica e operacional do OceanBlue para avaliar e executar o melhor processo de deploy em uma VPS. Ele cobre a arquitetura atual, componentes do sistema, dependencias, persistencia de dados, riscos de producao, estrategia de Docker Compose, seguranca, backup, observabilidade e rotina de atualizacao.

O foco principal e deixar claro:

- quais partes do sistema devem ser atualizadas com frequencia;
- quais partes devem ser tocadas raramente;
- onde ficam os dados persistentes;
- quais comandos sao seguros no dia a dia;
- quais pontos precisam ser revisados antes de expor o sistema publicamente.

## 2. Visao geral do sistema

O OceanBlue e uma aplicacao web Flask para gestao operacional de varejo em modelo SaaS/multi-tenant. O sistema atende operacoes de PDV, estoque, financeiro, clientes, cashback, mensageria, fiscal, importacao/exportacao, permissoes e administracao da plataforma.

Stack principal:

- Linguagem: Python 3.12 no container.
- Framework web: Flask.
- Servidor WSGI: Gunicorn.
- ORM: Flask-SQLAlchemy / SQLAlchemy.
- Migracoes: Flask-Migrate / Alembic.
- Banco de dados: PostgreSQL 16 em producao.
- Autenticacao: Flask-JWT-Extended com JWT em cookies.
- Frontend: Jinja2, CSS local, JavaScript modular e Tailwind via CDN.
- Relatorios/arquivos: WeasyPrint e OpenPyXL.
- Containerizacao: Docker e Docker Compose.

## 3. Estrutura recomendada na VPS

A estrutura final recomendada separa infraestrutura persistente e aplicacao atualizavel:

```text
/opt/blueocean/
|-- infra/
|   |-- docker-compose.yml
|   |-- .env
|   `-- backup-postgres.sh
|-- app/
|   |-- docker-compose.yml
|   |-- .env
|   |-- Dockerfile
|   |-- docker-entrypoint.sh
|   |-- app/
|   |-- migrations/
|   |-- scripts/
|   `-- docs/
`-- backups/
    `-- blueocean-*.sql.gz
```

Responsabilidade de cada pasta:

- `/opt/blueocean/infra`: stack do banco e backup. Deve ser alterada raramente.
- `/opt/blueocean/app`: codigo da API Flask. Pode receber deploys frequentes.
- `/opt/blueocean/backups`: dumps compactados do PostgreSQL.

Essa separacao reduz o risco de um deploy da API apagar ou reiniciar indevidamente o banco de dados.

## 4. Arquitetura Docker

### 4.1 Stack da aplicacao

Arquivo: `docker-compose.yml`.

Servicos:

- `api`: container `blueocean_api`.

Caracteristicas:

- build local a partir do `Dockerfile`;
- porta publicada somente em `127.0.0.1:5000:5000`;
- usa `env_file: .env`;
- conecta na rede externa `blueocean_network`;
- healthcheck em `GET /api/ready`;
- nao declara banco de dados;
- nao declara volumes persistentes da aplicacao.

Consequencia operacional:

- `docker compose up -d --build` atualiza somente a API;
- `docker compose down` executado dentro de `/opt/blueocean/app` nao remove o Postgres, porque o banco nao pertence a esse compose;
- `docker compose down -v` nesse compose nao deve apagar o volume do banco, pois o volume do Postgres nao esta declarado na stack da API.

### 4.2 Stack da infraestrutura

Arquivo: `infra/docker-compose.yml`.

Servicos:

- `db`: PostgreSQL 16, container `blueocean_db`.
- `db-backup`: rotina automatica de backup com `pg_dump`.

Recursos externos:

- rede: `blueocean_network`;
- volume: `blueocean_postgres_data`.

Caracteristicas importantes:

- o volume `blueocean_postgres_data` e declarado como `external: true`;
- a rede `blueocean_network` e declarada como `external: true`;
- o banco usa aliases `db`, `postgres` e `blueocean_db`;
- a API acessa o banco via host `db` dentro da rede Docker;
- backups sao gravados em `/opt/blueocean/backups`.

Consequencia operacional:

- o Compose da infra nao cria nem possui o volume do banco;
- mesmo se alguem usar `docker compose down -v` na infra, o Compose nao deve remover um volume externo;
- a manutencao do banco fica separada dos deploys diarios da API.

## 5. Fluxo de rede recomendado

Fluxo externo:

```text
Internet
  |
  v
Nginx/Caddy na VPS :443
  |
  v
127.0.0.1:5000
  |
  v
container blueocean_api
  |
  v
rede Docker blueocean_network
  |
  v
container blueocean_db:5432
```

Regras importantes:

- o container da API nao deve publicar `0.0.0.0:5000`;
- a porta 5432 do Postgres nao deve ser publicada para a internet;
- o proxy reverso deve terminar TLS;
- o proxy deve enviar `X-Forwarded-Proto`, `X-Forwarded-For` e `Host`;
- a aplicacao deve manter `TRUST_PROXY_HEADERS=true` somente quando estiver atras de proxy confiavel.

## 6. Componentes internos da aplicacao

Estrutura principal:

- `app/controllers`: rotas HTTP, validacao superficial e serializacao.
- `app/services`: regras de negocio e orquestracao.
- `app/repositorys`: consultas e persistencia via ORM.
- `app/models`: entidades, enums, constraints e indices.
- `app/security`: JWT, permissoes, validadores, headers, rate limit e criptografia de campo.
- `app/templates`: telas Jinja2.
- `app/static/js`: comportamento dos modulos no frontend.
- `app/static/css`: estilos por modulo.
- `migrations`: historico Alembic.
- `tests`: testes automatizados.
- `docs`: documentacao.

Padrao de execucao:

1. Gunicorn inicia `wsgi:app`.
2. `wsgi.py` chama `create_app()`.
3. `create_app()` carrega configuracao, extensoes, headers, blueprints, contexto de templates e comandos CLI.
4. O entrypoint espera o banco responder.
5. O entrypoint executa `flask db upgrade`.
6. A API comeca a receber trafego.

## 7. Modulos funcionais

### 7.1 Plataforma

Rotas principais:

- `/platform/home`
- `/api/platform/tenants`
- `/api/platform/planos`
- `/api/platform/tenants/<tenant_id>/empresas`
- `/api/platform/tenants/<tenant_id>/admins`
- `/api/platform/tenants/<tenant_id>/assinatura`

Responsabilidades:

- administracao global dos tenants;
- criacao de empresas;
- criacao de administradores;
- controle de plano, assinatura, trial e limites comerciais.

### 7.2 Autenticacao

Rotas principais:

- `/login`
- `/logout`

Caracteristicas:

- autentica dono da plataforma ou funcionario de tenant;
- usa JWT armazenado em cookie;
- em producao os cookies devem ser seguros (`Secure`) e trafegar somente via HTTPS;
- o escopo da sessao diferencia `platform` e `tenant`.

### 7.3 Multi-tenant e permissoes

Entidades centrais:

- `Tenant`
- `Empresa`
- `Funcionario`
- `FuncionarioEmpresa`
- `Role`
- `Permission`
- `RolePermission`

Regras:

- registros operacionais usam `tenant_id`;
- acesso por empresa e controlado por vinculo ativo do funcionario;
- endpoints usam decorators de permissao;
- a navegacao e montada com base nas permissoes do usuario logado.

### 7.4 PDV

Rotas principais:

- `/api/pdv/view`
- `/api/pdv/auxiliares`
- `/api/pdv/produtos`
- `/api/pdv/produtos/codigo-barras`
- `/api/pdv/vendas`
- `/api/pdv/vendas/<venda_id>/cancelar`
- `/api/pdv/vendas/<venda_id>/itens/<item_id>/cancelar`
- `/api/pdv/vendas/<venda_id>/comprovante`

Fluxos criticos:

- venda finalizada baixa estoque;
- venda cria lancamentos financeiros;
- venda pode usar cupom;
- venda pode gerar ou consumir cashback;
- cancelamento recompoe estoque e registra estorno;
- cancelamento parcial atua por item.

Risco operacional:

- indisponibilidade do banco interrompe venda;
- deploy durante horario de caixa pode derrubar sessoes ou atrapalhar finalizacoes;
- migracoes devem ser avaliadas antes de deploy em horario comercial.

### 7.5 Estoque

Rotas principais:

- `/api/estoque/view`
- `/api/estoque/alertas/view`
- `/api/estoque/indicadores/view`
- `/api/estoque/`
- `/api/estoque/movimentos`
- `/api/estoque/movimentos/manual`
- `/api/estoque/movimentos/<movimento_id>/cancelar`
- `/api/estoque/notificacoes`
- `/api/estoque/notificacoes/configuracao`
- `/api/estoque/indicadores/produtos-mais-vendidos`

Responsabilidades:

- saldo por produto e empresa;
- entradas e saidas;
- alertas de baixo estoque, sem estoque e validade;
- indicadores;
- reversao de movimentacao manual.

### 7.6 Financeiro

Rotas principais:

- `/api/financeiro/view`
- `/api/financeiro/lancamentos/view`
- `/api/financeiro/relatorios/view`
- `/api/financeiro/dashboard`
- `/api/financeiro/lancamentos`
- `/api/financeiro/fechamentos`
- `/api/financeiro/relatorios/fluxo-caixa/impressao`
- `/api/financeiro/relatorios/adiantamentos/impressao`
- `/api/financeiro/relatorios/produtos-mais-vendidos/impressao`

Responsabilidades:

- entradas e saidas;
- fechamento de caixa;
- relatorios;
- lancamentos automaticos vindos do PDV;
- estornos.

### 7.7 Clientes, cashback e mensageria

Rotas principais:

- `/api/clientes/view`
- `/api/clientes/`
- `/api/clientes/<cliente_id>/carteira`
- `/api/clientes/<cliente_id>/historico-vendas`
- `/api/clientes/<cliente_id>/mensagens`
- `/api/clientes/mensagens/disparo-coletivo`
- `/api/clientes/configuracoes`
- `/api/clientes/configuracoes/<empresa_id>`
- `/api/clientes/configuracoes/<empresa_id>/testar`

Responsabilidades:

- cadastro de clientes;
- opt-in por canal;
- carteira de cashback;
- credito, debito, estorno e expiracao;
- envio de email SMTP;
- envio por WhatsApp/SMS via webhook.

Ponto de producao:

- mensageria HTTP/SMTP acontece no processo web. Para volume alto, recomenda-se separar em worker assincrono no futuro.

### 7.8 Fiscal

Rotas principais:

- `/api/fiscal/view`
- `/api/fiscal/auxiliares`
- `/api/fiscal/configuracao`
- `/api/fiscal/configuracao/<empresa_id>`
- `/api/fiscal/notas`
- `/api/fiscal/notas/prevalidar`
- `/api/fiscal/notas/emitir`
- `/api/fiscal/notas/<nota_id>/xml`

Responsabilidades:

- configuracao fiscal por empresa;
- ambiente fiscal;
- numeracao;
- certificado;
- CSC;
- notas fiscais vinculadas a vendas.

Pontos de producao:

- certificados e senhas devem ser tratados como segredo;
- arquivos XML e certificados podem exigir volume persistente dedicado caso sejam salvos fora do banco;
- confirmar onde `xml_path` e `certificado_caminho` apontarao na VPS antes de ativar uso fiscal real.

### 7.9 Importacao e exportacao

Rotas principais:

- `/api/importacao-exportacao/view`
- `/api/importacao-exportacao/contexto`
- `/api/importacao-exportacao/template`
- `/api/importacao-exportacao/exportar`
- `/api/importacao-exportacao/importar`

Responsabilidades:

- templates;
- importacao de planilhas;
- exportacao de dados.

Ponto de producao:

- imports grandes no processo web podem estourar timeout ou memoria. Se o uso crescer, mover para fila/worker.

### 7.10 Cadastros e configuracoes

Modulos:

- produtos;
- categorias;
- cupons;
- funcionarios;
- roles;
- permissions;
- adiantamentos.

Esses modulos seguem o mesmo padrao controller/service/repository e compartilham as regras de tenant, empresa e permissao.

## 8. Modelo de dados

O modelo e relacional e centrado no tenant.

Blocos principais:

- Plataforma: `PlatformOwner`, `Tenant`.
- Organizacao: `Empresa`, `Funcionario`, `FuncionarioEmpresa`.
- Autorizacao: `Role`, `Permission`, `RolePermission`.
- Catalogo: `CategoriaProduto`, `Produto`, `ProdutoEmpresa`.
- Estoque: `MovimentoEstoque`, configuracoes de notificacao.
- Venda: `Venda`, `ItemVenda`, `PagamentoVenda`, `Cupom`.
- Financeiro: `LancamentoFinanceiro`, `FechamentoCaixa`, categorias e formas.
- Clientes: `Cliente`, `CarteiraCliente`, `CreditoCashbackCliente`, `MovimentoCarteiraCliente`.
- Mensageria: `MensagemCliente`, configuracao por empresa.
- Fiscal: `ConfiguracaoFiscalEmpresa`, `NotaFiscalVenda`.
- Auditoria: `AuditLog`.

Caracteristicas relevantes:

- uso extensivo de `UniqueConstraint` por tenant;
- indices para consultas por tenant/empresa/data;
- checks de valores nao negativos;
- checks de quantidades validas;
- rastreabilidade de cancelamentos e reversoes.

## 9. Migracoes

As migracoes ficam em `migrations/versions`.

O container da API executa automaticamente:

```bash
flask db upgrade
```

durante o `docker-entrypoint.sh`, apos validar que o banco responde.

Vantagens:

- deploy novo aplica schema automaticamente;
- reduz passos manuais.

Riscos:

- migracao destrutiva ou lenta pode impactar a API no boot;
- dois containers da API subindo ao mesmo tempo poderiam tentar migrar em paralelo, caso a arquitetura evolua para replicas;
- rollback de codigo nao necessariamente faz downgrade do banco.

Recomendacao:

- para VPS single-instance, manter migracao no entrypoint e simples;
- antes de deploys grandes, testar migracao em copia do banco;
- criar backup imediatamente antes de migracoes relevantes;
- se o sistema crescer para multiplas replicas, mover migracao para job unico de deploy.

## 10. Variaveis de ambiente

### 10.1 API

Arquivo: `/opt/blueocean/app/.env`.

Variaveis essenciais:

- `FLASK_ENV=production`
- `FLASK_DEBUG=0`
- `DATABASE_URL=postgresql+psycopg2://usuario:senha@db:5432/banco`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `FIELD_ENCRYPTION_KEY`
- `FORCE_HTTPS=true`
- `JWT_COOKIE_CSRF_PROTECT=true`
- `TRUST_PROXY_HEADERS=true`
- `PROXY_FIX_X_FOR=1`
- `PROXY_FIX_X_PROTO=1`
- `PROXY_FIX_X_HOST=1`

Variaveis operacionais:

- `MAX_CONTENT_LENGTH`
- `LOGIN_RATE_LIMIT_ATTEMPTS`
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `DB_WAIT_TIMEOUT_SECONDS`
- `SQLALCHEMY_POOL_RECYCLE`
- `PLATFORM_OWNER_NAME`
- `PLATFORM_OWNER_USER`
- `PLATFORM_OWNER_PASSWORD`

Cuidados:

- segredos devem ter pelo menos 32 caracteres;
- `DATABASE_URL` em producao nao pode apontar para SQLite;
- nao versionar `.env`;
- nao usar senha de exemplo em VPS;
- se houver certificados fiscais, documentar nomes de variaveis de senha por empresa.

### 10.2 Infra

Arquivo: `/opt/blueocean/infra/.env`.

Variaveis:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `BACKUP_INTERVAL_SECONDS`
- `BACKUP_RETENTION_DAYS`

Cuidados:

- `POSTGRES_PASSWORD` deve bater com a senha dentro de `DATABASE_URL`;
- esse arquivo deve ter permissao restrita no servidor;
- alteracao de `POSTGRES_DB`, `POSTGRES_USER` ou `POSTGRES_PASSWORD` depois do volume criado exige manutencao cuidadosa.

## 11. Seguranca de producao

Controles ja previstos:

- cookies JWT seguros em producao;
- CSRF em cookies JWT;
- headers de seguranca;
- forca HTTPS quando `FORCE_HTTPS=true`;
- validacao de segredos obrigatorios;
- `ProxyFix` opcional atras de proxy reverso;
- rate limit de login por configuracao;
- criptografia de campos sensiveis via `FIELD_ENCRYPTION_KEY`;
- usuario nao-root no container da API.

Checklist para VPS:

- liberar firewall apenas para `22`, `80` e `443`;
- bloquear acesso externo a `5000` e `5432`;
- usar Nginx/Caddy com TLS;
- renovar certificados automaticamente;
- aplicar atualizacoes de seguranca do sistema;
- restringir permissao de `.env`;
- desabilitar login SSH por senha se possivel;
- usar usuario nao-root para deploy;
- manter Docker atualizado;
- configurar logs e rotacao.

Ponto sensivel:

- Tailwind via CDN e scripts externos em `unpkg.com` aparecem na politica CSP atual. Para producao mais controlada, considerar empacotar assets localmente e reduzir dependencias externas.

## 12. Backups e recuperacao

### 12.1 Backup atual

O servico `db-backup` executa `pg_dump`, compacta com gzip e grava:

```text
/opt/blueocean/backups/blueocean-YYYYMMDDTHHMMSSZ.sql.gz
```

Retencao:

- controlada por `BACKUP_RETENTION_DAYS`;
- padrao sugerido: 14 dias.

### 12.2 Recomendacoes adicionais

Para producao real, manter pelo menos duas camadas:

- backup local na VPS para restauracao rapida;
- copia externa em outro local, como S3, Backblaze, Google Cloud Storage ou outro servidor.

Frequencias recomendadas:

- pequeno varejo: 1 backup diario;
- PDV com alto movimento: backup a cada 6 ou 12 horas;
- antes de deploy com migracao: backup manual imediato.

Validacoes periodicas:

- testar restore mensalmente;
- conferir tamanho dos dumps;
- alertar se backup deixar de ser criado;
- monitorar espaco em disco.

### 12.3 Restauracao manual

Exemplo:

```bash
gzip -dc /opt/blueocean/backups/blueocean-YYYYMMDDTHHMMSSZ.sql.gz | docker exec -i blueocean_db psql -U blueocean -d blueocean
```

Antes de restaurar:

- parar a API;
- confirmar banco alvo;
- fazer backup do estado atual;
- registrar data e motivo;
- validar login e fluxos criticos apos restore.

## 13. Processo de deploy recomendado

### 13.1 Primeiro deploy

1. Preparar VPS com Docker, Compose e proxy reverso.
2. Criar estrutura `/opt/blueocean`.
3. Clonar codigo em `/opt/blueocean/app`.
4. Criar `.env` da API a partir de `.env.example`.
5. Rodar `./scripts/init-infra.sh`.
6. Editar `/opt/blueocean/infra/.env`.
7. Rodar `./scripts/init-infra.sh` novamente.
8. Subir API com `docker compose up -d --build`.
9. Configurar Nginx/Caddy para apontar para `127.0.0.1:5000`.
10. Acessar `/api/health` e `/api/ready`.
11. Criar ou validar usuario inicial da plataforma.
12. Testar login, PDV, estoque e financeiro.

### 13.2 Deploy rotineiro da API

Comandos:

```bash
cd /opt/blueocean/app
git pull
./scripts/deploy-api.sh
```

O script:

- faz build da API;
- sobe `api` com `--no-deps`;
- nao sobe nem derruba banco;
- nao chama `down`;
- nao usa `--volumes`.

### 13.3 Deploy com migracao importante

Fluxo recomendado:

1. Avisar usuarios e escolher janela de menor movimento.
2. Gerar backup manual.
3. Validar espaco em disco.
4. Fazer `git pull`.
5. Rodar testes, se o ambiente permitir.
6. Executar `./scripts/deploy-api.sh`.
7. Acompanhar logs:

```bash
docker logs -f blueocean_api
```

8. Validar `/api/ready`.
9. Testar login, venda simples e consulta de estoque.

## 14. Operacao diaria

Comandos uteis:

```bash
docker compose ps
docker logs -f blueocean_api
docker logs -f blueocean_db
docker logs -f blueocean_db_backup
docker exec -it blueocean_db psql -U blueocean -d blueocean
```

Verificar saude:

- `/api/health`: processo web responde.
- `/api/ready`: processo web e banco respondem.

Monitorar:

- uso de CPU;
- memoria;
- disco;
- crescimento de backups;
- logs de erro;
- tempo de resposta;
- falhas de login;
- falhas de mensageria;
- falhas fiscais.

## 15. Observabilidade e logs

Estado atual:

- logs da aplicacao saem em stdout/stderr;
- Gunicorn integra com logger Flask;
- Docker captura logs por container;
- healthcheck do container usa `/api/ready`.

Recomendacoes:

- configurar rotacao de logs do Docker;
- criar alerta para container unhealthy;
- monitorar espaco de `/var/lib/docker`;
- manter logs de Nginx/Caddy;
- registrar erros de aplicacao com contexto suficiente;
- futuramente integrar Sentry, Grafana Loki, Prometheus ou outro stack leve.

## 16. Pontos de persistencia alem do banco

Hoje, o banco e a persistencia principal. Entretanto, alguns recursos merecem decisao antes de producao:

- certificados fiscais: confirmar caminho, permissao e backup;
- XML de notas fiscais: `xml_path` indica possibilidade de arquivo persistente;
- arquivos temporarios de importacao/exportacao;
- relatorios gerados;
- favicon/assets versionados no repositorio.

Recomendacao:

- se certificados/XML forem armazenados em disco, criar volume dedicado fora do container da API;
- exemplo futuro: `/opt/blueocean/storage`;
- incluir esse diretorio no backup externo;
- restringir permissao de leitura.

## 17. Avaliacao de alternativas de deploy

### 17.1 Compose unico para API e banco

Nao recomendado.

Vantagens:

- mais simples no inicio.

Problemas:

- banco e API ficam no mesmo ciclo de vida;
- `docker compose down -v` pode remover dados;
- scripts de deploy ficam perigosos;
- CI/CD mal configurado pode atingir banco.

### 17.2 Compose separado com banco em volume externo

Recomendado para a VPS atual.

Vantagens:

- simples de operar;
- banco protegido estruturalmente;
- deploy da API fica pequeno;
- custo baixo;
- boa aderencia a uma VPS unica.

Limites:

- sem alta disponibilidade;
- backup precisa ser bem cuidado;
- escalabilidade horizontal limitada.

### 17.3 Banco gerenciado fora da VPS

Recomendado quando houver mais clientes, maior criticidade ou equipe menor para operacao.

Vantagens:

- backup e restore mais maduros;
- menor risco operacional;
- atualizacoes de banco gerenciadas;
- maior disponibilidade.

Desvantagens:

- custo maior;
- latencia depende da regiao;
- exige configuracao de rede e firewall.

### 17.4 Orquestrador completo

Kubernetes, Swarm ou similar nao e necessario agora.

So considerar quando houver:

- multiplas instancias;
- deploy blue/green;
- workers separados;
- alto volume;
- equipe com maturidade operacional.

## 18. Recomendacao final para o melhor processo na VPS

Para o estado atual do OceanBlue, o melhor processo e:

1. VPS unica com Docker Compose.
2. Stack de infra separada da stack da API.
3. Postgres em volume externo.
4. Rede Docker externa compartilhada.
5. Proxy reverso na VPS com HTTPS.
6. Porta da API presa em `127.0.0.1`.
7. Banco sem porta publicada.
8. Deploy da API por script restrito.
9. Backup automatico local e copia externa.
10. Migracoes automaticas no entrypoint enquanto houver apenas uma instancia da API.

Essa abordagem oferece o melhor equilibrio entre simplicidade, seguranca operacional e custo.

## 19. Checklist pre-producao

Infra:

- Docker instalado.
- Docker Compose funcionando.
- Rede `blueocean_network` criada.
- Volume `blueocean_postgres_data` criado.
- `/opt/blueocean/infra/.env` preenchido.
- `/opt/blueocean/app/.env` preenchido.
- `/opt/blueocean/backups` criado.

Seguranca:

- HTTPS ativo.
- Firewall configurado.
- Porta 5432 fechada externamente.
- Porta 5000 fechada externamente.
- Segredos fortes.
- `.env` fora do Git.
- `FIELD_ENCRYPTION_KEY` guardado com muito cuidado.

Aplicacao:

- `FLASK_ENV=production`.
- `FLASK_DEBUG=0`.
- `FORCE_HTTPS=true`.
- `TRUST_PROXY_HEADERS=true` atras de Nginx/Caddy.
- `/api/health` retorna 200.
- `/api/ready` retorna 200.
- `flask db upgrade` executou sem erro.

Dados:

- backup automatico ativo.
- restore testado.
- plano de restore documentado.
- espaco em disco monitorado.

Negocio:

- usuario plataforma criado.
- tenant inicial validado.
- empresa inicial validada.
- funcionario/admin validado.
- fluxo de venda testado.
- fluxo de estoque testado.
- fluxo financeiro testado.
- relatorios testados.

## 20. Pendencias recomendadas antes de escala

Curto prazo:

- configurar proxy reverso com TLS e headers corretos;
- configurar rotacao de logs Docker;
- enviar backups para armazenamento externo;
- testar restore;
- revisar armazenamento de certificado/XML fiscal;
- revisar CSP para reduzir dependencias externas.

Medio prazo:

- criar worker para mensageria, imports grandes e tarefas fiscais;
- adicionar Redis/fila se houver processamento assincrono;
- adicionar monitoramento e alertas;
- separar storage persistente da API se arquivos fiscais forem usados;
- criar script de backup manual pre-deploy;
- documentar runbook de incidentes.

Longo prazo:

- avaliar banco gerenciado;
- avaliar deploy com imagem versionada em registry;
- adicionar pipeline CI/CD com testes;
- separar migracao em job unico;
- suportar replicas da API;
- melhorar observabilidade distribuida.

## 21. Runbook resumido

Deploy normal:

```bash
cd /opt/blueocean/app
git pull
./scripts/deploy-api.sh
curl -fsS http://127.0.0.1:5000/api/ready
```

Ver logs:

```bash
docker logs -f blueocean_api
```

Checar banco:

```bash
docker exec -it blueocean_db pg_isready -U blueocean -d blueocean
```

Backup manual:

```bash
docker exec blueocean_db pg_dump -U blueocean -d blueocean --no-owner --no-privileges | gzip -9 > /opt/blueocean/backups/blueocean-manual-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
```

Parar apenas API:

```bash
cd /opt/blueocean/app
docker compose stop api
```

Subir apenas API:

```bash
cd /opt/blueocean/app
docker compose up -d api
```

Nao usar no dia a dia:

```bash
docker compose down -v
docker volume rm blueocean_postgres_data
docker system prune --volumes
```

Esses comandos podem ser destrutivos e devem exigir manutencao planejada, backup validado e plena certeza do alvo.
