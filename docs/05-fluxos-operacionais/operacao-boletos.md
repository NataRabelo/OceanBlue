# Operacao de boletos

1. Configurar Asaas da empresa.
2. Criar boleto interno.
3. Registrar no provider.
4. Conferir `status_bancario`, `registro_bancario_id` e link oficial.
5. Entregar link/PDF ao cliente.
6. Aguardar webhook Asaas ou consultar status.
7. Baixa financeira so ocorre por confirmacao oficial ou baixa manual autorizada.

Duplicidades sao tratadas por idempotencia de registro e eventos de webhook.
