# Mapa de funcionalidades

## Plataforma/SaaS

Status: funcional com base implementada.

- Login de dono da plataforma.
- Listagem/criacao de tenants.
- Planos SaaS.
- Cadastro de empresas e admins.
- Atualizacao de assinatura e modo visual.

## Autenticacao, permissoes e usuarios

Status: funcional com testes de seguranca.

- Login/logout com JWT.
- Roles e permissoes por tenant.
- Funcionarios vinculados a empresas.
- Decorators de permissao e escopo.

## Cadastros

Status: funcional.

- Produtos.
- Categorias.
- Cupons.
- Funcionarios.
- Roles.
- Permissions.
- Importacao/exportacao por planilha.

## PDV e vendas

Status: funcional com fluxo testado.

- Tela de PDV.
- Busca de produtos.
- Carrinho.
- Criacao de venda.
- Pagamentos.
- Cancelamento de venda.
- Cancelamento de item.
- Comprovante.
- Integracao com estoque, financeiro e cashback.

## Estoque

Status: funcional.

- Saldos por produto/empresa.
- Movimentos manuais.
- Cancelamento de movimento.
- Alertas de estoque/validade.
- Indicadores e produtos mais vendidos.
- Notificacoes por configuracao.

## Financeiro

Status: funcional para lancamentos, dashboard, fechamento e relatorios.

- Dashboard.
- Lancamentos de entrada/saida.
- Categorias financeiras.
- Formas de pagamento.
- Fechamento de caixa.
- Relatorios de fluxo de caixa, adiantamentos e produtos mais vendidos.

## Clientes, cashback e mensageria

Status: funcional com pontos externos dependentes de configuracao.

- Cadastro de cliente.
- Historico de vendas.
- Carteira e cashback.
- Mensagens individuais e disparo coletivo.
- Configuracao de email, SMS e WhatsApp.

## Boletos

Status: parcial.

- Encontrado: modelos, migration, repository, service, endpoints, bancos emissores, regras de parcelamento, juros/multa, criacao de boleto e baixa.
- Nao encontrado: tela propria evidente, emissao bancaria real, registro em banco/API, CNAB efetivo, PDF real, linha digitavel calculada automaticamente, webhook/retorno bancario.

## Fiscal/nota fiscal

Status: parcial/operacional interno.

- Encontrado: tela fiscal, configuracao por empresa, prevalidacao, criacao de nota vinculada a venda, XML interno de NFC-e e download.
- Nao encontrado: assinatura digital real, transmissao para SEFAZ, autorizacao oficial, consulta de protocolo real, cancelamento, inutilizacao, contingencia completa.

## Telas encontradas

- Login.
- Home operacional.
- Homes de PDV, estoque, financeiro e configuracoes.
- Plataforma.
- Produtos, categorias, clientes, funcionarios, cupons, adiantamentos, roles, permissions.
- PDV.
- Estoque, alertas e indicadores.
- Financeiro, lancamentos e relatorios.
- Fiscal.
- Importacao/exportacao.
- Relatorios/impressao.
