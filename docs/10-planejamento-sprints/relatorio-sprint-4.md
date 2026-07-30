# Relatorio Sprint 4

## Estado inicial

- Branch: `main`.
- Worktree ja continha alteracoes da Sprint 3 e documentacao nao versionada.
- Testes iniciais: `50 passed, 10 warnings`.
- Migrations existentes verificadas; Sprint 4 criada sobre `1a2b3c4d5e6f`.

## Implementado

- Configuracao Asaas por empresa/tenant com segredos criptografados.
- Provider real Asaas, mantendo mock.
- Criacao de cliente Asaas, cobranca boleto, consulta e webhook idempotente.
- Configuracao Focus NFe por empresa/tenant com tokens criptografados.
- Provider real Focus NFe, mantendo mock.
- Emissao NFC-e, consulta e cancelamento via provider.
- Tela fiscal com campos Focus NFe mascarados.
- Telas operacionais com provider, links, consulta e cancelamento.
- Testes HTTP mockados para Asaas e Focus.

## Testes finais

`python -m pytest` -> `52 passed, 12 warnings`.

## Go/no-go

Go tecnico para homologacao assistida em sandbox/homologacao.

No-go para producao imediata ate preencher checklist de producao, validar credenciais reais, executar testes com Asaas sandbox e Focus homologacao, e obter aprovacao fiscal/financeira.
