# Manual de Uso - OceanBlue PDV

## 1. Objetivo

Este manual foi escrito para o usuario operacional do sistema. Ele explica como usar os Módulos principais no dia a dia:

- Estoque
- PDV
- Financeiro
- Clientes

## 2. Acesso ao sistema

### Login

1. Abra a tela de login.
2. Informe usuario e senha.
3. Clique em `Entrar no Sistema`.

Se o banco estiver com os dados padrao do seed, os acessos iniciais sao:

- Plataforma: usuario `platform`
- Tenant padrao: usuario `admin`

## 3. Home operacional

Depois do login do tenant, a home mostra tres areas:

- PDV Comercial
- Estoque
- Financeiro

Pelo menu superior tambem e possivel navegar entre:

- Home Operacional
- PDV
- Estoque
- Financeiro
- Clientes
- Funcionarios

Existe tambem um manual especifico para a operacao de clientes, cashback e mensageria em [manual_clientes_cashback_mensageria.md](./manual_clientes_cashback_mensageria.md).

## 4. Modulo de estoque

### O que pode ser feito

- consultar saldo por produto e empresa
- ver itens abaixo do estoque minimo
- registrar entradas manuais
- registrar saidas manuais
- acompanhar historico de movimentacoes

### Como registrar movimentacao manual

1. Entre em `Estoque`.
2. Clique em `Nova movimentacao`.
3. Escolha:
   - tipo
   - motivo
   - empresa
   - produto
4. Informe quantidade.
5. Se necessario, informe valor unitario.
6. Preencha a observacao.
7. Clique em `Registrar movimentacao`.

### Quando usar o estoque manual

Use para casos como:

- compra de mercadoria
- ajuste de inventario
- perda
- devolucao

Nao use movimentacao manual para vendas do caixa. A venda do PDV ja faz a baixa automaticamente.

## 5. Modulo de PDV

### O que pode ser feito

- escolher a empresa do atendimento
- buscar produtos
- montar carrinho
- aplicar desconto manual
- informar cupom
- dividir pagamento em mais de uma forma
- finalizar venda
- consultar vendas recentes
- cancelar vendas finalizadas

### Fluxo de venda

1. Entre em `PDV`.
2. Escolha a empresa no topo da tela.
3. Localize o produto pela busca ou pela grade.
4. Clique em `Adicionar`.
5. Ajuste a quantidade no carrinho.
6. Se necessario:
   - informe cupom
   - informe desconto manual
7. Defina a forma de pagamento.
8. Se quiser dividir, clique em `Adicionar` na area de pagamentos.
9. Preencha observacao, se precisar.
10. Clique em `Finalizar venda`.

### O que acontece ao finalizar

Automaticamente o sistema:

- grava a venda
- baixa o estoque
- registra as entradas no financeiro

### Como cancelar uma venda

1. Na tabela `Ultimas vendas`, clique no icone da venda.
2. Confira os detalhes.
3. Se a venda estiver finalizada, o botao `Cancelar venda` aparecera.
4. Informe o motivo no campo de cancelamento.
5. Clique em `Cancelar venda`.

O cancelamento:

- altera o status da venda
- devolve os itens ao estoque
- registra o estorno no financeiro

## 6. Modulo financeiro

### O que pode ser feito

- ver entradas, saidas e saldo
- acompanhar faturamento do periodo
- consultar ticket medio
- ver resumo por forma de pagamento
- acompanhar categorias mais relevantes
- registrar lancamentos manuais
- registrar fechamento de caixa

### Como registrar um lancamento manual

1. Entre em `Financeiro`.
2. Clique em `Novo lancamento`.
3. Escolha:
   - tipo
   - empresa
   - categoria
   - forma de pagamento
4. Informe descricao e valor.
5. Se quiser, preencha data de competencia e observacao.
6. Clique em `Registrar`.

### Como registrar fechamento de caixa

1. No painel financeiro, clique em `Fechar caixa`.
2. Escolha a empresa.
3. Confirme a data do fechamento.
4. Informe:
   - valor inicial
   - valor final contado
5. Se desejar, informe uma observacao.
6. Clique em `Registrar fechamento`.

### Como ler o fechamento

O card mostra:

- valor inicial
- valor final contado
- valor do sistema
- diferenca entre o caixa contado e o esperado

## 7. Modulo de clientes

### O que pode ser feito

- cadastrar clientes
- vincular vendas ao cliente
- consultar carteira de cashback
- ver historico de compras
- enviar email, SMS e WhatsApp
- configurar cashback e janelas de cancelamento por empresa
- usar o modulo de alertas para configurar o email operacional compartilhado

### Onde encontrar o detalhamento completo

Use o guia dedicado em [manual_clientes_cashback_mensageria.md](./manual_clientes_cashback_mensageria.md) para:

- configuracao de SMTP em `Estoque > Alertas > Email operacional`
- configuracao de webhook para WhatsApp e SMS
- regras de uso do cashback
- cancelamento parcial de itens
- cancelamento de movimentacoes operacionais

## 8. Filtros e acompanhamento

### No PDV

Voce pode filtrar:

- empresa
- busca de produto
- status da venda

### No financeiro

Voce pode filtrar:

- empresa
- periodo em dias
- tipo de lancamento

## 9. Boas praticas operacionais

- Sempre selecione a empresa correta antes de vender.
- Revise o carrinho antes de finalizar.
- Use observacao em casos fora do padrao.
- Evite lancamentos manuais sem categoria adequada.
- Registre o fechamento de caixa ao fim do turno.
- Use o cancelamento de venda apenas quando realmente necessario.
- Vincule o cliente quando houver historico, relacionamento ou uso de cashback.

## 10. Dicas para conferencias

- Se um item sumiu do estoque, confira primeiro as vendas e depois as movimentacoes manuais.
- Se o saldo financeiro nao bater, verifique:
  - lancamentos manuais
  - estornos de venda
  - fechamento de caixa
- Se um operador nao enxergar uma empresa, confirme o vinculo dele com essa empresa.
- Se o cashback nao aparecer no PDV, confira a configuracao da empresa e o saldo da carteira do cliente.

## 11. Resumo rapido por modulo

### Estoque

- controla saldo e movimentacao

### PDV

- registra a venda e baixa o estoque

### Financeiro

- registra entradas, saidas e fechamento

### Clientes

- concentra cadastro, historico, carteira e comunicacao

## 11. Quando chamar suporte tecnico

Procure suporte se acontecer:

- erro ao logar
- venda nao finaliza mesmo com estoque
- lancamentos nao aparecem no financeiro
- fechamento de caixa nao salva
- usuario sem acesso a empresa correta
