# Diagnostico de nota fiscal

## Estado atual

O sistema possui modulo fiscal parcial para NFC-e. Ele prepara configuracao por empresa, pre-valida vendas e gera XML operacional interno. Ainda nao ha emissao fiscal oficial autorizada pela SEFAZ.

## O que existe

- `ConfiguracaoFiscalEmpresa`: ambiente, regime tributario, serie, proximo numero, dados de endereco, certificado, CSC e contingencia.
- `NotaFiscalVenda`: vinculo entre venda e nota, status, serie, numero, chave, recibo, protocolo, XML e datas.
- `FiscalService`: configuracao, prevalidacao, geracao de chave, geracao de XML interno e download.
- `FiscalRepository`: consultas fiscais.
- `fiscal_controller.py`: endpoints sob `/api/fiscal`.
- `app/templates/modulos/fiscal/fiscal.html` e `app/static/js/modulos/fiscal.js`: tela fiscal.
- Integracao no PDV para chamar emissao fiscal apos venda.

## Endpoints encontrados

- `GET /api/fiscal/view`
- `GET /api/fiscal/auxiliares`
- `GET /api/fiscal/configuracao`
- `PUT /api/fiscal/configuracao/<empresa_id>`
- `GET /api/fiscal/notas`
- `POST /api/fiscal/notas/prevalidar`
- `POST /api/fiscal/notas/emitir`
- `GET /api/fiscal/notas/<nota_id>/xml`

## Lacunas

- Nao ha assinatura digital do XML.
- Nao ha transmissao para autorizador SEFAZ.
- Nao ha retorno/protocolo oficial.
- Nao ha cancelamento fiscal oficial.
- Nao ha inutilizacao de numeracao.
- Nao ha consulta de status real.
- Nao ha DANFE NFC-e.
- Tributacao dos itens parece simplificada e fixa, com CFOP e CSOSN/CST basicos.

## Riscos

- A mensagem de sucesso pode induzir operador a acreditar que a nota foi emitida oficialmente, quando o XML e interno.
- O armazenamento de certificado e XML precisa de decisao de seguranca e persistencia.
- O fluxo fiscal depende de NCM nos produtos, mas outros campos fiscais obrigatorios podem faltar conforme UF/regime.
- Biblioteca `mercadopago` existe em dependencias, mas nao foi identificada como fiscal; nao substitui integrador SEFAZ.

## Recomendacao para Sprint 2

Decidir se a emissao fiscal sera via biblioteca Python fiscal, API de terceiro ou integrador local. Em seguida, separar status interno de status SEFAZ, ajustar textos da UI, definir armazenamento seguro e montar checklist fiscal por UF/regime.
