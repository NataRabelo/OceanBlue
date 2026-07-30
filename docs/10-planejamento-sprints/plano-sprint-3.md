# Plano Sprint 3

## Objetivo

Implementar primeira versao homologada de boleto e nota fiscal, mantendo separacao clara entre estado interno e autorizacao/registro externo.

## Boleto

1. Definir banco/integrador e estrategia API, CNAB ou hibrida.
2. Criar migration para status bancario, protocolo, arquivos, webhooks/retornos e origem de baixa.
3. Criar interface de provider bancario.
4. Implementar provider homologacao.
5. Registrar boleto sem marcar como pago/emitido oficialmente antes do retorno.
6. Gerar ou obter PDF com rastreabilidade.
7. Processar retorno/webhook de forma idempotente.
8. Conciliar baixa bancaria com lancamento financeiro.
9. Ampliar tela de boletos com detalhe, baixa, recalcule e historico.

## Nota fiscal

1. Definir modelo fiscal, UF, regime e integrador/biblioteca.
2. Criar migration separando `status_interno` e `status_sefaz`.
3. Montar XML conforme schema oficial.
4. Assinar XML com certificado A1.
5. Transmitir em homologacao e persistir retornos.
6. Gerar DANFE NFC-e/NF-e conforme modelo escolhido.
7. Implementar cancelamento e consulta.
8. Planejar inutilizacao e contingencia.
9. Criar testes com mocks de autorizacao, rejeicao, duplicidade e cancelamento.

## Criterios de aceite

- Nenhum fluxo chama SEFAZ ou banco sem ambiente/credencial explicitos.
- UI diferencia claramente preparo interno, registro bancario e autorizacao fiscal.
- Retornos externos sao idempotentes.
- XML/PDF/arquivos sao persistidos fora do repositorio.
- Testes cobrem sucesso, rejeicao, duplicidade e falha de comunicacao.

## Prompt recomendado para iniciar

Atue como Codex arquiteto e engenheiro senior no projeto OceanBlue PDV. Use `docs/`, `relatorio-sprint-1/resumo-executivo.md`, `docs/10-planejamento-sprints/relatorio-sprint-2.md`, `docs/06-financeiro-boletos/especificacao-tecnica-boletos.md` e `docs/07-nota-fiscal/especificacao-tecnica-nota-fiscal.md`. Na Sprint 3, implemente uma primeira integracao homologada de boleto e nota fiscal sem confundir status interno com registro/autorizacao oficial. Antes de codar, confirme as decisoes de banco/integrador, API ou CNAB, modelo fiscal, UF, regime tributario e armazenamento de arquivos. Depois implemente em passos pequenos, com migrations, testes e documentacao.
