# Documentacao Tecnica - OceanBlue PDV

## 1. Visao geral

O OceanBlue PDV e um sistema web multi-tenant orientado para pequenas lojas, com tres frentes principais:

- Estoque por empresa
- PDV com venda rapida e baixa automatica
- Financeiro com entradas, saidas e fechamento de caixa
- Clientes com carteira, historico e mensageria

O projeto preserva a separacao entre plataforma, tenant, empresas e funcionarios. Cada registro operacional relevante e amarrado ao `tenant_id`, e o acesso por empresa e controlado pelo vinculo do funcionario com as empresas permitidas.

## 2. Stack utilizada

- Backend: Flask
- ORM: Flask-SQLAlchemy / SQLAlchemy
- Migracoes: Flask-Migrate / Alembic
- Autenticacao: Flask-JWT-Extended com cookie
- Banco planejado: PostgreSQL
- Frontend: Jinja2 + Tailwind via CDN + JavaScript modular

## 3. Estrutura do projeto

Camadas principais:

- `app/controllers`: rotas HTTP e serializacao da resposta
- `app/services`: regras de negocio e orquestracao dos fluxos
- `app/repositorys`: acesso a dados e consultas ORM
- `app/models`: entidades e enums do dominio
- `app/templates`: telas Jinja2
- `app/static/js`: comportamento dos Módulos no frontend
- `app/static/css`: estilos por modulo
- `migrations`: historico de banco
- `docs`: documentacao do sistema

## 4. Modelo multi-tenant

Entidades centrais:

- `Tenant`: dominio logico do cliente
- `Empresa`: empresas do tenant, podendo ser matriz ou filial
- `Funcionario`: usuario operacional do tenant
- `FuncionarioEmpresa`: define em quais empresas o funcionario atua
- `Role`, `Permission`, `RolePermission`: controle de acesso por tenant

Regras aplicadas:

- Quase todas as tabelas operacionais possuem `tenant_id`
- O escopo de empresa e calculado em `AcessoEmpresaService`
- Endpoints operacionais usam `permission_required(...)`
- O painel de plataforma continua separado do painel do tenant

## 5. Autenticacao e autorizacao

Fluxo:

1. O login aceita dono da plataforma ou funcionario de tenant.
2. O token JWT e gravado em cookie.
3. O escopo da sessao e resolvido por `get_auth_scope()`.
4. Nos endpoints do tenant, o decorator `permission_required` valida:
   - sessao ativa
   - escopo tenant
   - permissao da role
   - acesso permitido as empresas envolvidas

Permissoes novas adicionadas:

- `visualizar_pdv`
- `registrar_venda`
- `cancelar_venda`
- `cancelar_item_venda`
- `visualizar_cliente`
- `criar_cliente`
- `editar_cliente`
- `excluir_cliente`
- `enviar_mensagem_cliente`
- `gerenciar_configuracao_cliente`
- `visualizar_financeiro`
- `criar_lancamento_financeiro`
- `fechar_caixa`
- `cancelar_movimentacao_estoque`

## 6. Bootstrap operacional do tenant

O `TenantBootstrapService` agora garante, por tenant:

- permissoes e roles padrao
- formas de pagamento base
- categorias financeiras padrao
- tipos de operacao padrao

Cadastros criados automaticamente:

- Formas: Dinheiro, Pix, Cartao de debito, Cartao de credito, Boleto, Crediario
- Categorias de entrada: Vendas PDV, Aporte de caixa, Outras entradas
- Categorias de saida: Compras de mercadorias, Despesas operacionais, Estorno de vendas, Sangria de caixa
- Tipos de operacao: venda, entrada de estoque, ajuste e transferencia

## 7. Modulo de estoque

Arquivos principais:

- `app/controllers/estoque_controller.py`
- `app/services/estoque_service.py`
- `app/repositorys/estoque_repository.py`

Capacidades:

- consulta de saldo por produto e empresa
- historico de movimentacoes
- entradas e saidas manuais
- baixa automatica por venda no PDV
- retorno automatico por cancelamento da venda

Fluxos automaticos novos:

- `registrar_saida_por_venda(..., persistir=False)` para integrar com o PDV
- `registrar_entrada_por_cancelamento_venda(..., persistir=False)` para estorno operacional

## 8. Modulo de PDV

Arquivos principais:

- `app/controllers/pdv_controller.py`
- `app/services/pdv_service.py`
- `app/repositorys/pdv_repository.py`
- `app/templates/modulos/pdv/pdv.html`
- `app/static/js/modulos/pdv.js`
- `app/static/css/modulos/pdv.css`

Endpoints:

- `GET /api/pdv/view`
- `GET /api/pdv/auxiliares`
- `GET /api/pdv/produtos`
- `GET /api/pdv/vendas`
- `POST /api/pdv/vendas`
- `POST /api/pdv/vendas/<id>/cancelar`
- `POST /api/pdv/vendas/<id>/itens/<item_id>/cancelar`

Regras da venda:

- exige empresa dentro do escopo do operador
- exige pelo menos um item
- exige pagamento total igual ao total da venda
- aceita desconto manual
- aceita cupom por codigo, se estiver valido
- aceita vinculo com cliente
- aceita uso de cashback configurado por empresa
- usa o preco de venda do produto por empresa
- gera numero unico de venda
- grava venda, itens e pagamentos
- baixa estoque automaticamente
- gera lancamentos financeiros automaticamente
- gera credito de cashback na carteira do cliente quando habilitado

Cancelamento:

- permitido apenas para vendas finalizadas
- altera status da venda para `CANCELADA`
- gera entrada de estoque por devolucao
- gera saida financeira de estorno
- preserva rastreabilidade completa

Cancelamento parcial:

- atua por item da venda
- devolve apenas a quantidade cancelada
- gera estorno proporcional no financeiro
- ajusta cashback usado e cashback gerado da venda

## 9. Modulo de clientes

Arquivos principais:

- `app/controllers/cliente_controller.py`
- `app/services/cliente_service.py`
- `app/services/comunicacao_service.py`
- `app/repositorys/cliente_repository.py`
- `app/templates/modulos/cliente/cliente.html`
- `app/static/js/modulos/cliente.js`
- `app/static/css/modulos/cliente.css`

Entidades novas:

- `Cliente`
- `CarteiraCliente`
- `CreditoCashbackCliente`
- `MovimentoCarteiraCliente`
- `ConfiguracaoClienteEmpresa`
- `MensagemCliente`

Capacidades:

- cadastro de clientes e opt-in por canal
- carteira com saldo, creditos e expiracao
- historico de vendas vinculadas
- configuracao por empresa para cashback e janelas de cancelamento
- envio de email via SMTP
- envio de WhatsApp e SMS via webhook HTTP

Endpoints:

- `GET /api/clientes/view`
- `GET /api/clientes/auxiliares`
- `GET /api/clientes/`
- `POST /api/clientes/`
- `PUT /api/clientes/<id>`
- `DELETE /api/clientes/<id>`
- `GET /api/clientes/<id>/carteira`
- `GET /api/clientes/<id>/historico-vendas`
- `GET /api/clientes/<id>/mensagens`
- `POST /api/clientes/<id>/mensagens`
- `GET /api/clientes/configuracoes`
- `GET /api/clientes/configuracoes/<empresa_id>`
- `PUT /api/clientes/configuracoes/<empresa_id>`
- `POST /api/clientes/configuracoes/<empresa_id>/testar`

## 10. Modulo financeiro

Arquivos principais:

- `app/controllers/financeiro_controller.py`
- `app/services/financeiro_service.py`
- `app/repositorys/financeiro_repository.py`
- `app/templates/modulos/financeiro/financeiro.html`
- `app/static/js/modulos/financeiro.js`
- `app/static/css/modulos/financeiro.css`

Endpoints:

- `GET /api/financeiro/view`
- `GET /api/financeiro/auxiliares`
- `GET /api/financeiro/dashboard`
- `GET /api/financeiro/lancamentos`
- `POST /api/financeiro/lancamentos`
- `GET /api/financeiro/fechamentos`
- `POST /api/financeiro/fechamentos`

Capacidades:

- dashboard com entradas, saidas, saldo, faturamento e ticket medio
- serie diaria do periodo filtrado
- resumo por forma de pagamento
- top categorias financeiras
- lancamentos manuais de entrada e saida
- lancamentos automaticos vindos do PDV
- fechamento de caixa com comparacao entre valor informado e saldo esperado

## 11. Fluxos criticos do negocio

### 10.1 Venda no PDV

1. Operador escolhe a empresa.
2. Adiciona itens ao carrinho.
3. Define pagamentos.
4. Finaliza a venda.
5. O sistema:
   - grava a venda
   - grava itens e pagamentos
   - baixa o estoque
   - cria entradas financeiras

### 10.2 Cancelamento de venda

1. Operador abre os detalhes da venda.
2. Informa o motivo do cancelamento.
3. O sistema:
   - cancela a venda
   - devolve o estoque
   - registra estorno financeiro

### 10.3 Cancelamento parcial de item

1. Operador abre os detalhes da venda.
2. Escolhe o item a cancelar.
3. Informa o motivo.
4. O sistema:
   - estorna apenas o item
   - recompõe o estoque proporcional
   - ajusta o financeiro proporcional
   - ajusta o cashback do cliente proporcional

### 10.4 Lancamento manual

1. Operador escolhe empresa, tipo, categoria e forma.
2. Informa descricao e valor.
3. O sistema grava o lancamento e o incorpora ao dashboard.

### 10.5 Fechamento de caixa

1. Operador informa empresa, data, valor inicial e valor final contado.
2. O sistema calcula o saldo esperado em dinheiro.
3. O fechamento grava o valor contado e exibe a diferenca.

### 10.6 Cancelamento de movimentacao manual

1. Operador abre a tela de estoque operacional.
2. Localiza a movimentacao manual reversivel.
3. Informa o motivo do cancelamento.
4. O sistema:
   - marca a movimentacao original
   - cria a contramovimentacao
   - recompõe o saldo do estoque

## 12. Migracoes novas

Foi adicionada a migracao:

- `8f6e4c2a1b9d_add_pdv_financeiro_permissions_and_defaults.py`

Ela atualiza tenants existentes com:

- novas permissoes
- vinculos de permissoes nas roles padrao
- formas de pagamento base
- categorias financeiras base
- tipos de operacao base

## 12. Seeds

O seed agora:

- garante owner da plataforma
- garante tenant base
- garante roles e permissoes
- garante cadastros operacionais de PDV e financeiro
- garante empresas e admin inicial

## 13. Validacao executada

Validacoes realizadas nesta entrega:

- `python -m compileall app migrations`
- importacao da app com `create_app()`
- renderizacao das novas telas Jinja2
- testes automatizados do fluxo critico com SQLite:
  - venda baixa estoque e gera financeiro
  - cancelamento reverte estoque e financeiro
  - lancamento manual e fechamento de caixa

Arquivo de testes:

- `tests/test_fluxo_pdv_financeiro.py`

## 14. Observacoes tecnicas finais

- O projeto continua desenhado para PostgreSQL.
- Os testes automatizados foram executados em SQLite para validacao rapida da regra de negocio.
- O ambiente local usado para validacao nao possuia `psycopg2-binary` pronto para Python 3.13, por isso a validacao completa do banco PostgreSQL depende do ambiente Docker ou de um Python com wheel compativel.
- O frontend novo foi mantido dentro da linguagem visual do projeto, mas com navegacao revisada e rotas validas no cabecalho.
