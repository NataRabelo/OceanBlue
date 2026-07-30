# Implementacao boletos - Sprint 3

## Decisoes aplicadas

- Provider/adaptador generico, sem banco especifico acoplado ao service.
- Fluxo principal por API bancaria em homologacao/mock.
- PDF/HTML de boleto armazenados em storage privado configuravel por `OCEANBLUE_STORAGE_PATH`.
- Retorno/webhook preparado com idempotencia por `tenant_id`, provider e `event_id`.
- CNAB ficou previsto para sprint futura.

## Implementado

- `StatusBancarioBoleto` separado do `StatusBoleto` interno.
- Campos externos no boleto: provider, ambiente, idempotency key, registro externo, protocolo, mensagem de retorno, data de registro e origem da baixa.
- Tabelas `arquivos_boleto` e `retornos_bancarios_boleto`.
- `BoletoProvider` e `MockApiBancariaProvider`.
- Endpoint `POST /api/financeiro/boletos/<id>/registrar`.
- Endpoint `POST /api/financeiro/boletos/<id>/retorno`.
- Baixa bancaria idempotente via retorno homologado.
- Tela exibindo status interno e status bancario separadamente.

## Como operar em homologacao

1. Criar boleto normalmente.
2. Acionar registro pela tela de boletos ou pelo endpoint de registro.
3. Conferir `status_bancario`, protocolo e mensagem do provider.
4. Processar retorno bancario com `event_id` unico para simular baixa automatica.

## Limites

- O provider atual e mockado.
- PDF gerado e artefato de homologacao, nao boleto bancario oficial.
- CNAB, assinatura de webhook e banco real dependem de credenciais/contrato.
