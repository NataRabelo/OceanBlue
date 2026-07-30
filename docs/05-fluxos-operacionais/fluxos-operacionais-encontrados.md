# Fluxos operacionais encontrados

## Login e navegacao

Usuario acessa login, recebe JWT em cookie e passa a ver navegacao conforme permissoes e escopo de empresa. A navegacao tenant e montada em `app/__init__.py`.

## Venda PDV

O operador consulta produtos, monta carrinho, aplica descontos/cashback quando permitido, registra pagamentos e finaliza venda. O fluxo integra estoque, lancamento financeiro, cashback e comprovante.

## Cancelamentos

Ha cancelamento de venda e item de venda, com controles de limite e reversoes relacionadas a estoque, financeiro e cashback.

## Estoque

Produtos possuem dados por empresa. Movimentos de estoque podem ser gerados por venda ou manualmente. Alertas verificam estoque baixo, falta de estoque e validade.

## Financeiro

Lancamentos podem ser criados manualmente ou automaticamente por venda/baixa. Ha dashboard, fechamento de caixa e relatorios de impressao.

## Clientes e mensageria

Clientes possuem historico, carteira de cashback e configuracoes de comunicacao por empresa. Mensagens podem ser enviadas por email, SMS ou WhatsApp conforme configuracao.

## Fiscal

Venda finalizada pode ser prevalidada. Se configuracao fiscal e produtos estiverem completos, o sistema gera nota fiscal interna e XML operacional. Ainda nao ha autorizacao externa.

## Boleto

Fluxo parcial: cadastrar banco emissor, configurar parcelamento/juros, criar boleto, criar parcelas, recalcular encargos e baixar boleto. Ainda falta tela dedicada e emissao bancaria real.
