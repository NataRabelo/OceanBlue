# Integracao Asaas - boletos

## Base tecnica

O provider real `AsaasProvider` usa a API Asaas v3. Conforme a documentacao oficial, cobrancas sao criadas em `/v3/payments` com `customer`, `billingType`, `value`, `dueDate` e `externalReference`; para boleto, `billingType` deve ser `BOLETO`. Clientes sao criados em `/v3/customers` e o ID retornado deve ser reutilizado. Webhooks enviam JSON com `id`, `event` e objeto `payment`, e podem usar `asaas-access-token`.

Fontes oficiais:

- https://docs.asaas.com/reference/create-new-payment
- https://docs.asaas.com/reference/create-new-customer
- https://docs.asaas.com/docs/create-new-webhook-via-api
- https://docs.asaas.com/docs/receive-asaas-events-at-your-webhook-endpoint

## Configuracao por empresa

Endpoint:

- `GET /api/financeiro/boletos/configuracao-asaas?empresa_id={id}`
- `PUT /api/financeiro/boletos/configuracao-asaas/{empresa_id}`

Campos principais:

- `ambiente`: `sandbox` ou `producao`
- `api_key`: salvo criptografado com `FieldCrypto`
- `webhook_auth_token`: salvo criptografado
- `webhook_url`
- `webhook_ativo`
- `dias_apos_vencimento_cancelamento`
- `notificacoes_desabilitadas`

## Operacao

1. Configurar Asaas por empresa/tenant.
2. Criar boleto interno.
3. Registrar boleto. O provider cria cliente Asaas, cria cobranca `BOLETO`, persiste `pay_*`, status externo e link `bankSlipUrl`/`invoiceUrl`.
4. Consultar status quando necessario.
5. Receber webhook em `/api/financeiro/boletos/webhook/asaas/{tenant_id}/{empresa_id}`.
6. Confirmacao de pagamento aciona baixa financeira idempotente.

## Seguranca

- Tokens nao sao retornados pela API apos salvar.
- Webhook valida `asaas-access-token` quando configurado.
- Eventos duplicados sao ignorados por constraint de idempotencia.
- Producao depende de credenciais reais e URL publica HTTPS.
