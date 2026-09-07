# Bugs, riscos e divida tecnica

> Diagnóstico histórico preservado. A situação do código atual e o destino de cada grupo
> de pendências constam na [reauditoria da Sprint 7](../evidencias/producao/sprint-07-execucao/auditoria-modulos.md).
> Não use as recomendações históricas de integrações como instruções de produção.

## Riscos tecnicos principais

- Raiz analisada nao esta em repositorio Git ativo; rastreabilidade e rollback precisam ser confirmados.
- Existem duas areas de infra (`infra/` na raiz e `pdv/infra/`), exigindo confirmacao de qual e oficial.
- Boleto tem status de emissao sem integracao bancaria real.
- Fiscal gera XML interno sem autorizacao SEFAZ real.
- Persistencia de XML, PDFs, certificados e dados bancarios precisa de desenho.
- Dados sensiveis bancarios e fiscais exigem politica de criptografia, mascaramento e backup.
- `mercadopago` esta em dependencias, mas nao foi confirmada integracao ativa.

## Bugs/problemas visiveis

- Alguns textos exibidos nos arquivos aparecem com problemas de encoding em comentarios/mensagens, por exemplo `ConfiguraÃ§Ã£o`. Isso pode afetar UX e documentacao.
- `app/__init__.py` silencia excecoes no context processor com `except Exception: pass`; isso pode esconder problemas de sessao/permissao.
- Seed possui senhas padrao `123456`; aceitavel para desenvolvimento, mas perigoso se usado fora dele.
- Recalculo de juros/multa de boleto precisa revisao de idempotencia para evitar soma repetida.

## Divida tecnica funcional

- Permissoes especificas de boleto ainda nao estao claras.
- Cancelamento/estorno de boleto nao foi encontrado nos endpoints atuais.
- Nota fiscal nao tem cancelamento, inutilizacao, contingencia completa ou DANFE.
- Testes fiscais especificos nao foram identificados.
- Teste de boleto encontrado cobre calculo, mas nao fluxo completo de emissao/baixa/parcelas.

## Recomendacoes

- Inicializar ou localizar o repositorio Git oficial antes de mudancas grandes.
- Rodar suite de testes e corrigir quebras antes da Sprint 2.
- Separar diagnostico fiscal/boleto de implementacao real em tarefas pequenas.
- Criar fixtures de ambiente e dados de homologacao.
