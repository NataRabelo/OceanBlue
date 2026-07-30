# Implementacao nota fiscal - Sprint 3

## Decisoes aplicadas

- NFC-e como primeiro modelo.
- Integrador fiscal terceiro como estrategia recomendada.
- Provider fiscal mockado para homologacao sem credenciais reais.
- Storage privado configuravel por `OCEANBLUE_STORAGE_PATH`.
- Certificado e credenciais sempre fora do codigo, por caminho/env vars.

## Implementado

- `StatusOficialNotaFiscal` separado do `StatusNotaFiscal` interno.
- Campos na nota para modelo, provider, idempotencia, protocolo oficial, XML assinado, XML autorizado, DANFE, codigo de retorno e data de autorizacao.
- Campos na configuracao fiscal para provider e env de credencial do integrador.
- Tabela `eventos_fiscais_nota`.
- `FiscalProvider` e `MockIntegradorFiscalProvider`.
- Emissao NFC-e homologada com XML interno, XML assinado mock, XML autorizado mock e DANFE HTML.
- Endpoint de download de DANFE em `GET /api/fiscal/notas/<id>/danfe`.
- Tela fiscal exibindo status interno e status oficial.

## Como operar em homologacao

1. Configurar empresa fiscalmente em ambiente `HOMOLOGACAO`.
2. Prevalidar venda finalizada.
3. Enviar NFC-e em homologacao.
4. Conferir `status=EMITIDA`, `status_oficial=AUTORIZADA`, protocolo oficial/homologacao e arquivos.
5. Baixar XML e DANFE.

## Limites

- Autorizacao atual e mockada; nao comunica SEFAZ.
- XML assinado/autorizado e DANFE sao homologaveis para fluxo interno, nao documentos fiscais oficiais de producao.
- Cancelamento, inutilizacao e contingencia real ficaram preparados em modelo/status, mas nao foram integrados a SEFAZ.
