# Manual Completo - Clientes, Cashback e Mensageria

## 1. Objetivo

Este manual cobre a configuracao e o uso do novo modulo de clientes, incluindo:

- cadastro e manutencao de clientes
- carteira de cashback
- vinculo da venda com o cliente no PDV
- cancelamento parcial de itens e reversoes operacionais
- configuracao de email, WhatsApp e SMS por empresa

## 2. Permissoes novas

As permissoes abaixo passam a existir no tenant:

- `visualizar_cliente`
- `criar_cliente`
- `editar_cliente`
- `excluir_cliente`
- `enviar_mensagem_cliente`
- `gerenciar_configuracao_cliente`
- `cancelar_item_venda`
- `cancelar_movimentacao_estoque`

Por padrao, a role `administrador` recebe essas permissoes automaticamente. Outras roles podem receber as mesmas permissoes manualmente na tela de roles.

## 3. Como usar o modulo de clientes

### Cadastro

1. Abra `Clientes`.
2. Clique em `Novo Cliente`.
3. Preencha nome, documento, email, telefone, WhatsApp e observacoes.
4. Marque quais canais o cliente autorizou:
   - email
   - SMS
   - WhatsApp
5. Salve o cadastro.

### Edicao e inativacao

- Use o icone de edicao para atualizar os dados do cliente.
- Use o icone de inativacao para retirar o cliente da operacao diaria.
- A inativacao preserva historico, vendas, mensagens e carteira.

### Carteira e historico

Na listagem, o botao de carteira abre:

- saldo atual de cashback
- creditos disponiveis com data de expiracao
- historico da carteira
- historico de vendas vinculadas
- mensagens enviadas para o cliente

## 4. Configuracao por empresa

Entre em `Clientes > Configuracoes`.

Cada empresa tem sua propria configuracao operacional para:

- percentual de cashback
- validade do cashback em dias
- valor minimo para uso do cashback
- limite de horas para cancelamento de venda completa
- limite de horas para cancelamento de item da venda
- limite de horas para cancelamento de movimentacao de estoque
- envio por WhatsApp
- envio por SMS
- timeout das integracoes externas

### Campos de cashback

- `Habilitar cashback`: libera geracao e uso da carteira para a empresa
- `Percentual`: percentual aplicado sobre o total final da venda
- `Validade em dias`: prazo para o credito expirar
- `Minimo de resgate`: valor minimo que o operador pode usar da carteira em uma venda

### Campos de cancelamento

- `Venda completa`: janela maxima para cancelar a venda inteira
- `Itens da venda`: janela maxima para devolucao/cancelamento parcial
- `Movimentacoes`: janela maxima para reverter movimentacoes manuais

Se o valor for `0`, o sistema interpreta como sem limite de horas.

## 5. Fluxo de cashback no PDV

### Venda com cliente

1. Abra o `PDV`.
2. Escolha a empresa.
3. Monte o carrinho normalmente.
4. Selecione o cliente no bloco `Cliente`.
5. O painel mostra:
   - saldo disponivel
   - regra de cashback da empresa
   - valor minimo de uso

### Usar cashback

1. Com cliente selecionado e empresa configurada, preencha o campo `Cashback usado`.
2. O sistema limita automaticamente o valor:
   - ao saldo do cliente
   - ao total liquido da venda
   - ao minimo configurado para resgate
3. O total da venda e recalculado antes da confirmacao do pagamento.

### Gerar cashback

Ao finalizar uma venda com cliente vinculado:

- o cashback e calculado sobre o total final da venda
- o credito e gravado na carteira do cliente
- a data de expiracao segue a configuracao da empresa

### Regras importantes

- cashback e somente para consumo na loja
- cashback nao substitui o historico da venda, ele complementa o relacionamento com o cliente
- se o cashback gerado por uma venda ja tiver sido usado, a venda nao pode ser cancelada integralmente

## 6. Cancelamento parcial de itens

Nos detalhes da venda do PDV agora existe o botao `Cancelar item`.

Quando um item e cancelado:

- o estoque retorna apenas daquela parte cancelada
- o financeiro gera estorno proporcional
- o cashback usado na venda pode ser restituido proporcionalmente
- o cashback gerado pela venda e reduzido proporcionalmente
- o motivo fica registrado no item da venda

Use esse fluxo para:

- devolucao de parte da compra
- erro de registro de item
- troca interna com retorno ao estoque

## 7. Cancelamento de movimentacoes de estoque

Na tela `Estoque operacional`, as movimentacoes manuais reversiveis mostram o botao de cancelamento.

Quando a movimentacao e cancelada:

- o sistema cria a contramovimentacao automaticamente
- a movimentacao original fica marcada como revertida/cancelada
- o motivo operacional fica gravado
- a janela de horas respeita a configuracao da empresa

Esse fluxo vale para:

- entrada manual indevida
- ajuste incorreto
- retorno de transferencia manual
- devolucao operacional registrada manualmente por engano

## 8. Configuracao de email SMTP

As credenciais de email deixaram de ficar no modal de configuracoes de `Clientes`.

Agora o caminho recomendado e:

`Estoque > Alertas > Email operacional`

Preencha os campos da empresa com os dados do servidor de email:

- `Habilitar email`
- `Nome do remetente`
- `Email remetente`
- `SMTP host`
- `SMTP port`
- `Usuario SMTP`
- `Senha SMTP`
- `Usar TLS`
- `Usar SSL`

Esse cadastro e compartilhado por:

- alerta de estoque por email
- comprovante automatico da venda
- comunicacao por email com clientes

### Regras

- marque apenas um modo de seguranca: `TLS` ou `SSL`
- use `TLS` normalmente com porta `587`
- use `SSL` normalmente com porta `465`
- se o provedor exigir autenticacao, informe usuario e senha
- o remetente precisa ser valido para o provedor configurado
- no Gmail, use `senha de app` com verificacao em duas etapas
- se a senha do Gmail vier no formato `xxxx xxxx xxxx xxxx`, o sistema remove os espacos automaticamente no envio

### Exemplo comum

- Host: `smtp.office365.com`
- Porta: `587`
- TLS: ligado
- SSL: desligado

ou

- Host: `smtp.gmail.com`
- Porta: `587`
- TLS: ligado
- SSL: desligado

Se o Gmail responder com erro `535 5.7.8 Username and Password not accepted`, normalmente a causa e uma destas:

- senha da conta comum foi usada no lugar da senha de app
- verificacao em duas etapas nao esta ativa
- a senha de app foi colada com espacos e o valor nao corresponde ao gerado no Google

## 9. Configuracao de WhatsApp e SMS

Para WhatsApp e SMS o sistema usa integracao HTTP do tipo webhook `POST`.

Campos disponiveis:

- `Habilitar WhatsApp`
- `WhatsApp API URL`
- `Token Bearer`
- `Remetente / instancia`
- `Habilitar SMS`
- `SMS API URL`
- `Token Bearer`
- `Alias do remetente`
- `Timeout`

### Requisicao enviada pelo sistema

O payload JSON enviado para WhatsApp e SMS segue este formato:

```json
{
  "channel": "whatsapp",
  "to": "+5511999999999",
  "subject": "Assunto opcional",
  "message": "Conteudo da mensagem",
  "sender": "nome-da-instancia-ou-alias",
  "customer": {
    "nome": "Maria Oliveira",
    "documento": "12345678901",
    "email": "cliente@exemplo.com",
    "telefone": "+5511999999999",
    "whatsapp": "+5511999999999"
  }
}
```

### Headers enviados

- `Content-Type: application/json`
- `Authorization: Bearer <token>` quando o token estiver preenchido

### Requisitos do seu gateway

O seu servidor de WhatsApp/SMS deve:

- aceitar `POST`
- responder dentro do timeout configurado
- retornar HTTP `2xx` em caso de sucesso
- devolver corpo textual ou JSON, que sera armazenado como resposta da integracao

Se o endpoint responder com HTTP diferente de `2xx`, o erro volta para a tela e fica gravado no historico da mensagem.

## 10. Como testar a comunicacao

Na tela `Clientes > Configuracoes` existe a caixa `Teste de comunicacao`.

Passos:

1. Selecione a empresa.
2. Escolha o canal.
3. Informe o destinatario de teste.
4. Informe assunto e conteudo.
5. Clique em `Executar teste`.

Use esse teste antes de liberar campanhas ou comunicacao operacional.

## 11. Email automatico na venda

Quando uma venda for finalizada com cliente vinculado:

- se a empresa tiver email habilitado
- se o cliente tiver email cadastrado
- se o cliente tiver autorizado email

o sistema envia automaticamente um email com:

- numero da venda
- data da compra
- total pago
- desconto aplicado
- cashback utilizado
- cashback gerado na compra
- validade do cashback gerado, quando houver
- saldo atual da carteira
- layout visual padrao do OceanBlue

Se o email falhar, a venda continua finalizada normalmente e a falha fica registrada no historico de mensagens do cliente.

## 12. Como enviar mensagem para um cliente

1. Abra `Clientes`.
2. Clique em `Enviar mensagem` no registro do cliente.
3. Escolha a empresa.
4. Escolha o canal.
5. Informe assunto e conteudo.
6. Envie.

### Disparo coletivo

Para enviar uma mensagem para toda a base apta ao canal:

1. Abra `Clientes`.
2. Clique em `Disparo coletivo`.
3. Escolha a empresa.
4. Escolha o canal.
5. Informe assunto e conteudo.
6. Clique em `Disparar para todos`.

O sistema envia apenas para clientes ativos que:

- autorizaram o canal selecionado
- possuem contato valido para o canal
- podem ser atendidos pela configuracao da empresa naquele canal
- recebem o email em layout visual padrao do OceanBlue quando o canal for `email`

O sistema valida automaticamente:

- se o cliente autorizou o canal
- se a empresa tem o canal habilitado
- se os dados obrigatorios de integracao foram configurados
- se o cliente possui contato valido para aquele canal

## 13. Boas praticas operacionais

- Vincule o cliente sempre que a venda tiver potencial de recompra.
- Use cashback apenas quando o cliente estiver confirmado no caixa.
- Revise a configuracao de cada empresa antes de liberar uso em lojas diferentes.
- Defina janelas de cancelamento realistas para evitar estornos fora da operacao.
- Teste email, WhatsApp e SMS antes de uso em producao.
- Mantenha opt-in atualizado para evitar contato sem autorizacao do cliente.

## 14. Checklist de implantacao

- Executar a migracao do banco
- Revisar permissoes das roles
- Configurar ao menos uma empresa para cashback, se aplicavel
- Configurar SMTP, WhatsApp e SMS por empresa
- Executar o teste de comunicacao de cada canal
- Validar venda com cliente e geracao de cashback
- Validar venda com uso de cashback
- Validar cancelamento parcial de item
- Validar cancelamento de movimentacao manual


## Exemplo de preenchimento 

Habilitar email: ✔

Nome do remetente:
OceanBlue

Email remetente:
natarabelo0@gmail.com

SMTP host:
smtp.gmail.com

SMTP port:
587

Usuario SMTP:
natarabelo0@gmail.com

Senha SMTP:
(senha de app Google)

Usar TLS:
✔

Usar SSL:
✖
