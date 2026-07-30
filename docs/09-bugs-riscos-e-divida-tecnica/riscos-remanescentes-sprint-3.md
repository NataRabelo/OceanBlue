# Riscos remanescentes - Sprint 3

## Boleto

- Provider atual e mockado, sem validade bancaria.
- PDF atual e artefato de homologacao, nao boleto oficial.
- CNAB ainda nao implementado.
- Webhook ainda nao valida assinatura externa.
- Permissoes ainda reaproveitam permissoes financeiras gerais.

## Nota fiscal

- Integrador fiscal atual e mockado.
- XML assinado/autorizado e DANFE sao artefatos de homologacao interna.
- Certificado real, CSC e credencial de integrador precisam confirmacao.
- Cancelamento, inutilizacao, consulta e contingencia oficiais ainda nao foram implementados.
- Regras tributarias completas dependem de contador e UF de homologacao.

## Operacao

- Storage local precisa politica de backup, criptografia, retencao e controle de acesso.
- Dados reais no banco local exigem migrations nao destrutivas e backup antes de homologacao com sistemas externos.
