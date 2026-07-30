# Integracao Focus NFe - NFC-e

## Base tecnica

O provider real `FocusNFeProvider` usa a API Focus NFe v2. Conforme a documentacao oficial, NFC-e e emitida em `/v2/nfce?ref=...`; o envio e sincrono e retorna autorizacao ou rejeicao na mesma requisicao. A autenticacao e HTTP Basic usando o token como usuario e senha vazia. A consulta ocorre em `/v2/nfce/{referencia}`.

Fontes oficiais:

- https://doc.focusnfe.com.br/reference/introducao
- https://doc.focusnfe.com.br/reference/ambiente
- https://doc.focusnfe.com.br/reference/emitir_nfce
- https://doc.focusnfe.com.br/reference/consultar_nfce
- https://doc.focusnfe.com.br/reference/inutilizar_numeracao_nfce

## Configuracao por empresa

A configuracao fiscal existente foi ampliada:

- `integrador_provider`: `mock_nfce` ou `focus_nfe`
- `focus_token_homologacao`: criptografado
- `focus_token_producao`: criptografado
- `focus_cnpj_emitente`
- `focus_status_configuracao`

Os campos estao disponiveis na tela fiscal e no endpoint `PUT /api/fiscal/configuracao/{empresa_id}`. Tokens sao enviados apenas para alterar, nunca exibidos completos.

## Operacao

1. Configurar empresa fiscal em homologacao.
2. Selecionar `Focus NFe`.
3. Informar token de homologacao, CNPJ emitente, UF, regime, serie e dados fiscais.
4. Prevalidar venda finalizada.
5. Emitir NFC-e. O sistema usa `ref` idempotente por nota/venda.
6. Persistir status, protocolo, chave, URLs e arquivos XML/DANFE quando retornados.
7. Consultar status por `POST /api/fiscal/notas/{nota_id}/consultar`.
8. Cancelar NFC-e autorizada por `POST /api/fiscal/notas/{nota_id}/cancelar`, com justificativa minima.

## Limites

- Payload fiscal usa campos operacionais essenciais; validacao com contador e Focus NFe e obrigatoria antes de producao.
- Inutilizacao ficou documentada e preparada como etapa futura.
- Producao so deve ser ativada apos homologacao assistida.
