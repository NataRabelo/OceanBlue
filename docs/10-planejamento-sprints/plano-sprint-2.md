# Plano Sprint 2

## Objetivo recomendado

Preparar o sistema para evoluir boleto e nota fiscal com seguranca, corrigindo riscos imediatos de ambiente, UX e diagnostico funcional antes de implementar emissao real.

## Prioridade 1 - Governanca tecnica

- Confirmar repositorio Git oficial.
- Rodar suite completa de testes.
- Corrigir problemas de encoding visiveis.
- Confirmar stack Docker oficial e variaveis de ambiente.

## Prioridade 2 - Boleto

- Definir banco/integrador.
- Definir se o fluxo sera API bancaria, CNAB ou ambos.
- Criar especificacao funcional de boleto.
- Revisar modelo de dados para retorno, webhook, remessa e arquivos.
- Criar tela operacional de boletos.
- Criar testes de criacao, baixa parcial, baixa total, juros/multa e permissao.

## Prioridade 3 - Nota fiscal

- Decidir integrador fiscal.
- Definir UF, regime tributario, modelo fiscal e certificado.
- Separar status interno de status oficial SEFAZ.
- Revisar textos da UI fiscal.
- Criar testes de prevalidacao e geracao de XML.
- Planejar assinatura, transmissao, retorno, cancelamento, inutilizacao e DANFE.

## Criterio de saida

Ao final da Sprint 2, o projeto deve ter ambiente validado, bugs criticos documentais/UX corrigidos e especificacoes tecnicas prontas para implementacao real de boleto/fiscal.
