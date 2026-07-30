# Checklist de producao

## Antes do deploy

- Backup completo do banco.
- Revisar branch e tag de release.
- Executar migrations em staging.
- Configurar `FIELD_ENCRYPTION_KEY` forte e persistente.
- Configurar `OCEANBLUE_STORAGE_PATH` fora do repositorio.
- Validar permissoes de escrita/leitura do storage.
- Confirmar HTTPS publico para webhooks.

## Asaas

- Token sandbox por empresa.
- Webhook sandbox com `asaas-access-token`.
- Teste de criacao de cliente.
- Teste de boleto sandbox.
- Teste de webhook `PAYMENT_RECEIVED`.
- Token producao configurado somente apos homologacao.
- Responsavel financeiro aprovou fluxo.

## Focus NFe

- Token homologacao por empresa.
- CNPJ emitente cadastrado na Focus.
- UF, regime, serie e numeracao revisados.
- Produtos com NCM/CFOP/tributacao revisados.
- Teste de NFC-e homologacao autorizada.
- Teste de NFC-e rejeitada.
- Teste de consulta.
- Teste de cancelamento dentro do prazo.
- Contador aprovou payload e DANFE.

## Go-live

- Monitoramento de logs habilitado.
- Plano de rollback documentado.
- Suporte pos-go-live definido.
- Producao ativada por empresa, nao globalmente.
