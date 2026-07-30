# Relatorio Sprint 3

## Estado inicial

- Branch Git: `main`.
- Suite inicial: `49 passed, 10 warnings`.
- Worktree inicial ja possuia alteracoes da Sprint 1/2 e documentos nao versionados; nada foi revertido.

## Implementado

- Separacao entre status interno e status externo para boleto e NFC-e.
- Migration `1a2b3c4d5e6f_add_sprint3_boleto_fiscal_external_status.py`.
- Provider bancario mockado e provider fiscal mockado.
- Registro de boleto em homologacao, arquivos de comprovante e retorno idempotente.
- Envio NFC-e em homologacao, protocolo, XML assinado/autorizado e DANFE HTML.
- Ajustes de tela para status interno/oficial e acoes operacionais.
- Testes automatizados ampliados.

## Testes

- Antes: `49 passed, 10 warnings`.
- Depois: `50 passed, 10 warnings`.

## Nao homologado em producao

- Banco real/API real.
- CNAB.
- Webhook assinado por banco.
- Integrador fiscal real.
- Assinatura digital real e comunicacao SEFAZ.
- Cancelamento, inutilizacao e contingencia oficiais.
