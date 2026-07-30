# Especificacao tecnica de nota fiscal

## Estado atual

O modulo fiscal prepara configuracao por empresa, pre-valida vendas, gera chave de acesso e XML NFC-e interno. Nao ha assinatura digital, transmissao, autorizacao SEFAZ, protocolo oficial, DANFE, cancelamento, inutilizacao ou contingencia real.

## Componentes analisados

- `ConfiguracaoFiscalEmpresa`: ambiente, regime, serie, numero, dados fiscais, certificado, CSC e contingencia.
- `NotaFiscalVenda`: vinculo com venda, status, serie, numero, chave, recibo, protocolo, XML e datas.
- `FiscalService`: configuracao, prevalidacao, chave, XML interno e download.
- `FiscalRepository`: consultas fiscais.
- `fiscal_controller.py`: endpoints sob `/api/fiscal`.
- `app/templates/modulos/fiscal/fiscal.html` e `app/static/js/modulos/fiscal.js`: tela fiscal.

## Fluxo atual

1. Usuario configura dados fiscais da empresa.
2. Sistema valida presenca de campos obrigatorios, certificado A1 em disco, variavel de senha e NCM dos produtos.
3. Prevalidacao cria ou atualiza `NotaFiscalVenda`.
4. Quando nao ha pendencias, o status vira `PRONTA_PARA_EMISSAO`.
5. A acao atual gera numero, serie, chave, recibo/protocolo internos e XML local.
6. O XML pode ser baixado pelo endpoint.

## Problemas atuais

- Status `EMITIDA` ainda representa XML interno, nao autorizacao fiscal oficial.
- `recibo` e `protocolo` sao hashes internos, nao retornos SEFAZ.
- O XML inclui protocolo interno e tributacao simplificada.
- Nao ha assinatura digital.
- Nao ha transmissao para webservices SEFAZ.
- Nao ha DANFE NFC-e.
- Nao ha cancelamento, inutilizacao ou contingencia real.
- Nao ha armazenamento definitivo/backup para XMLs autorizados e eventos.

## Correcoes aplicadas na Sprint 2

- Textos da tela e API foram ajustados para falar em XML fiscal interno e deixar claro que nao ha autorizacao SEFAZ.
- Mensagem interna do XML deixou de sugerir autorizacao interna.

## NFC-e, NF-e e emissao interna

- NFC-e: modelo 65, venda presencial ao consumidor final, normalmente com QR Code CSC e DANFE NFC-e simplificado.
- NF-e: modelo 55, venda/operacao com maior abrangencia fiscal/logistica, DANFE NF-e e regras de transporte/destinatario mais completas.
- Emissao interna atual: geracao operacional de dados e XML local para preparar integracao futura. Nao tem validade fiscal oficial sem assinatura, transmissao e autorizacao.

## Dados fiscais necessarios

- CNPJ, razao social, nome fantasia e endereco completo da empresa.
- IE, IM quando aplicavel, CNAE, regime tributario, CRT.
- UF, codigo IBGE do municipio, ambiente homologacao/producao.
- Serie, numero, modelo, tipo de emissao e controle de numeracao.
- Produtos com NCM, CFOP, CSOSN/CST, origem, unidade, CEST quando aplicavel, aliquotas e beneficios fiscais.
- Dados de pagamento com mapeamento oficial `tPag`.
- CSC/ID CSC para NFC-e.
- Certificado A1 `.pfx/.p12` e senha por variavel segura.

## Certificados, XMLs, PDFs e armazenamento

Recomendacao:

- Certificado fora do repositorio, com caminho configurado por ambiente e senha em secret manager ou variavel segura.
- XMLs autorizados imutaveis, versionados por tenant/empresa/ano/mes/modelo/serie/numero.
- Guardar XML assinado, XML autorizado, eventos de cancelamento/inutilizacao e retornos brutos.
- DANFE/PDF pode ser gerado sob demanda, mas deve ser reproduzivel a partir do XML autorizado.

## Assinatura digital

A Sprint 3 deve escolher entre:

- biblioteca Python fiscal mantida e compatvel com NF-e/NFC-e 4.00;
- integrador fiscal terceiro;
- servico proprio separado para assinatura/transmissao.

Assinatura deve ocorrer antes da transmissao e precisa validar schema, cadeia do certificado, validade e senha.

## Transmissao e autorizacao

Fluxo desejado:

1. Prevalidar venda e configuracao.
2. Montar XML fiscal conforme schema oficial.
3. Assinar XML.
4. Transmitir para SEFAZ ou integrador.
5. Persistir recibo/retorno.
6. Consultar autorizacao quando assincrono.
7. Persistir protocolo oficial.
8. Atualizar status fiscal.
9. Gerar/permitir DANFE.

## Cancelamento, inutilizacao e contingencia

- Cancelamento: enviar evento oficial dentro do prazo legal, persistir XML do evento e protocolo.
- Inutilizacao: inutilizar faixa de numeracao nao usada quando houver quebra.
- Contingencia: definir modelo suportado por UF/integrador, justificativa, data/hora e transmissao posterior.
- Consulta: permitir sincronizar nota local com status oficial.

## Tarefas recomendadas para Sprint 3

1. Definir NFC-e, NF-e ou ambas; priorizar UF e regime tributario.
2. Escolher integrador fiscal ou biblioteca.
3. Separar status interno de status oficial SEFAZ em modelo/migration.
4. Implementar assinatura/transmissao em homologacao.
5. Validar XML contra schema oficial.
6. Criar armazenamento definitivo para XML autorizado e eventos.
7. Implementar DANFE NFC-e.
8. Implementar cancelamento, inutilizacao e consulta.
9. Criar testes com mocks de autorizacao, rejeicao, duplicidade, cancelamento e contingencia.
