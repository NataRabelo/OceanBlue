# Revisao de telas e templates

## Estrutura visual

O frontend usa templates Jinja2 em `app/templates`, CSS em `app/static/css` e JavaScript por modulo em `app/static/js/modulos`.

## Bases e componentes

- `bases/base.html`
- `bases/base_public.html`
- `componentes/header_home.html`
- `componentes/header_subpages.html`
- `componentes/tenant_sidebar.html`
- `componentes/footer.html`
- `componentes/flash_mensagem.html`

## Telas principais

- `pages/login.html`
- `pages/home.html`
- `pages/home_pdv.html`
- `pages/home_estoque.html`
- `pages/home_financeiro.html`
- `pages/home_configuracoes.html`
- `pages/platform_home.html`

## Telas por modulo

- Produtos, categorias, clientes, funcionarios, cupons, adiantamentos.
- PDV.
- Estoque, alertas e indicadores.
- Financeiro, lancamentos e relatorios.
- Fiscal.
- Importacao/exportacao.
- Roles e permissions.

## Relatorios e emails

- Relatorios: comprovante, fluxo de caixa, adiantamentos e produtos mais vendidos.
- Emails: venda para cliente, mensagem cliente e alerta de estoque.

## Achados

- Nao foi encontrada tela especifica de boleto; boleto parece exposto apenas por endpoints.
- A tela fiscal informa emissao interna de NFC-e, ponto importante para evitar confusao operacional.
- A navegacao por permissoes e montada em `app/__init__.py`.
- Ha estilos por modulo, o que favorece melhoria incremental de templates sem refatoracao ampla.

## Recomendacoes

- Criar inventario visual com screenshots na Sprint 2.
- Revisar responsividade das telas mais usadas: PDV, financeiro, estoque e fiscal.
- Criar tela/aba operacional de boletos antes da emissao real.
- Revisar textos de fiscal para diferenciar "XML interno" de "autorizado pela SEFAZ".
