# Riscos remanescentes para producao

> Registro histórico anterior ao fechamento. A referência vigente é o
> [checklist do candidato](../10-planejamento-sprints/checklist-producao.md) e o
> [relatório da Sprint 7](../evidencias/producao/sprint-07-execucao.md).
> Asaas/Focus/Boleto/Fiscal não podem ser habilitados neste candidato. Configuração
> de provedores citada abaixo não é uma etapa autorizada da instalação atual.

- Payload fiscal Focus NFe precisa homologacao real com contador.
- Regras tributarias completas por produto ainda exigem saneamento cadastral.
- Inutilizacao NFC-e ainda nao foi implementada operacionalmente.
- Webhook Asaas depende de URL HTTPS publica e token forte configurado.
- Storage local precisa backup, criptografia em repouso e politica de retencao.
- Permissoes especificas para configurar integracoes ainda reaproveitam permissoes financeiras/fiscais.
- Go-live deve ser por empresa/tenant para reduzir impacto.
