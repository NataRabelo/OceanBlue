# Sprint 1 — validacao independente

Data: 2026-09-06, America/Sao_Paulo. Os logs usam UTC e terminam em 2026-09-07.

## Decisao: NO-GO para aceite final

Os gates locais estao aprovados: instalacoes sem cache, 20 migrations com ida/volta, schema comparado com modelos, **85 testes passando em duas execucoes completas**, cobertura combinada **53,37%** e smoke produtivo saudavel nas duas execucoes. Nenhum teste foi removido, desabilitado ou marcado como skip/xfail; o limite de cobertura continua em 50%.

O requisito de **pipeline remoto verde no commit entregue ainda nao foi comprovado**. A consulta ao GitHub Actions retornou `total_count: 0` em `2026-09-07T00:04:32.5967813Z`. A main remota ainda aponta para `352a77c7d39836e57b6d9f366d3fc7a83d0a3f3b`, anterior a Sprint 1. Esta tarefa faz commit local; nao publica branch, nao altera a main e nao efetua deploy. A execucao local dos comandos do workflow nao e apresentada como uma execucao GitHub Actions.

Para remover o bloqueio: publicar/integrar o commit desta validacao pelo fluxo do repositorio e obter a execucao verde de `Sprint 1 verification`, com logs, JUnit, cobertura e smoke vinculados ao SHA integrado. Se a integracao modificar codigo, repetir os gates nesse SHA. Evidencia: [consulta remota](sprint-01-validacao/github-actions.json), [pagina de Actions](https://github.com/NataRabelo/OceanBlue/actions).

## Base e isolamento

- Worktree inicialmente limpo, HEAD destacado em `352a77c`. Executados `git fetch origin main` e `git merge --ff-only main`; HEAD avancou para `7bff1ea6390326dd2b866105c28c73baa4d30165`.
- Confirmada a existencia de `docs/evidencias/producao/sprint-01-execucao.md` nessa base antes da validacao. O relatorio anterior serviu apenas como especificacao, nao como prova dos resultados abaixo.
- Baseline exportado com `git archive HEAD`; final exportado do indice Git para outro diretorio novo. Ambos sem `.env`, `.venv`, `instance`, arquivos locais de desenvolvimento ou banco persistido.
- Arvore Git do codigo e guia exportados para os retestes finais: `7f36bf1b197991fd7901ce33843dffaab1e4cb6d`. Este relatorio, os novos logs e o atributo Git que preserva seus bytes foram acrescentados depois; nenhum codigo executavel mudou depois dessa exportacao.
- Projetos Compose exclusivos `oceanblue-s01-independent`, `oceanblue-s01-retest` e `oceanblue-s01-final`, PostgreSQL em tmpfs, rede interna e nenhuma porta publicada. Todos removidos ao concluir; nenhum banco externo foi utilizado.

## Casos, antes/depois e retestes

| Caso | Antes, executado nesta tarefa | Correcao / resultado final |
|---|---|---|
| Checkout limpo e instalacao | Locks prod/dev instalados sem cache com hashes; baseline 63 testes passou em 38,09 s | Novas instalacoes prod/dev sem cache e `pip check` OK; locks preservados |
| Imagem sem FLASK_ENV e sem segredos | `create_app()` aceitou DATABASE_URL isolada com debug=True, CSRF=False e cookie inseguro; gate da imagem falhou | Dockerfile assume production. Gate confirma o default e recusa cada variavel obrigatoria ausente antes de conectar ao banco |
| FLASK_ENV errado ou vazio | prod, production-typo e valor vazio cairam em desenvolvimento | Inicializacao recusa valores desconhecidos com mensagem explicita; tres regressoes passam |
| Segredos obrigatorios | A validacao da app recusava segredos, mas o entrypoint tentava o banco primeiro | Validacao movida para antes da espera; oito casos ausente/vazio e tres segredos curtos passam em processos novos |
| URL de banco invalida | Validador aceitava MySQL; URLs malformadas/porta invalida geravam erros de baixo nivel | Exige URL PostgreSQL parseavel; quatro casos recusados sem expor o marcador privado da URL |
| Schema apos migrations | Comparacao Alembic identificou **21 diferencas**: nove indices, uma FK e onze tipos de coluna | Nova revision `3c4d5e6f7a8b` corrige todas; compare_metadata retorna lista vazia |
| Historico completo e banco vazio | 19 revisions faziam upgrade/downgrade/reupgrade | 20 revisions passam individualmente; tenant sentinela preservado ate head; downgrade base sem tabelas/ENUMs orfaos; reupgrade com 42 tabelas |
| Upgrade com dados existentes | Novo teste independente criado para a correcao estrutural | Seis bancos emissores com todas as combinacoes layout/ambiente preservados em downgrade, upgrade e segundo upgrade |
| Valor legado invalido | Caso adicional de falha transacional | Upgrade com layout INVALID falha; revision permanece no head anterior e tipos novos nao ficam orfaos. Restaurado o valor valido, upgrade e schema completo passam |
| Variavel de teste ausente / banco nao isolado | Casos existentes preservados e execucao negativa adicional | Sem TEST_DATABASE_URL: exit 1 antes de acesso; URLs SQLite/banco diferente continuam recusadas |
| Validador destrutivo com banco preenchido | Precondicao de banco vazio conferida independentemente | Exit 1 com mensagem de banco nao vazio; nao aplica downgrade nem elimina dados |
| Suite completa e cobertura | Baseline 63 passed; novas regressoes contra a imagem antiga: 7 failed/12 passed em startup e 1 failed em schema | 85 passed duas vezes; zero erros, falhas ou skips; cobertura combinada 53,37% nas duas |
| Producao sobre banco vazio | Verificacao refeita com imagem atual | Entrypoint aplica migrations, Gunicorn sobe quatro workers como appuser, container healthy; /api/health e /api/ready retornam 200 com JSON validado |
| Reinicio produtivo | Teste adicional com tenant sentinela inserido via SQL | Reinicio reaplica upgrade sem duplicacao/perda: exatamente um tenant sentinela permanece; container volta a healthy |
| Indisponibilidade real do banco | Banco descartavel efetivamente desligado | /api/health continua 200; /api/ready responde 503 com apenas status/database error. Segunda execucao limpa recupera banco e smoke |
| CI e coleta de provas | Workflow nao verificava o default da imagem; coleta de logs nao habilitava o perfil smoke | Acrescentados gate negativo da imagem, verificacao HTTP/usuario/configuracao e logs incluindo smoke; comandos locais passaram. GitHub Actions continua pendente |

As sete falhas de startup anteriores incluem mudancas no contrato de diagnostico (SQLite ja era recusado); nao representam sete vulnerabilidades distintas. A correcao estrutural trata apenas schema, sem implementar integracoes fiscais ou bancarias reais.

## Execucoes finais

| Medicao | Execucao 1 | Execucao 2 |
|---|---|---|
| Compose completo, exit code | 0 | 0 |
| JUnit testes / falhas / erros / skips | 85 / 0 / 0 / 0 | 85 / 0 / 0 / 0 |
| Tempo JUnit | 47,642 s | 43,236 s |
| Linhas cobertas / totais | 5.759 / 9.996 | 5.759 / 9.996 |
| Ramificacoes cobertas / totais | 699 / 2.104 | 699 / 2.104 |
| Combinado | 6.458 / 12.100 = 53,37% | 6.458 / 12.100 = 53,37% |
| Smoke produtivo, exit code | 0 | 0 |

A segunda execucao ocorreu depois de `down -v`, refazendo o historico inteiro em outro banco vazio. Entre ambas, tambem foram exercitados reinicio com dados, indisponibilidade real e recuperacao. Os 22 casos adicionados sao 19 de startup e tres de schema. Os subprocessos de startup verificam importacao/configuracao real em ambientes novos; sua cobertura nao foi artificialmente adicionada a medicao de app.

Versoes medidas: Docker Engine 29.7.2, Compose 5.5.0, Linux amd64/WSL2, Python 3.12.12, PostgreSQL 16.12, Flask 3.0.3, Flask-SQLAlchemy 3.1.1, Flask-Migrate 4.0.7, SQLAlchemy 2.0.52, Alembic 1.19.2, psycopg2-binary 2.9.9, pytest 8.3.5, pytest-cov 6.1.1, coverage 7.16.0, pip 25.0.1, pip-tools 7.4.1 e Gunicorn 21.2.0. [Saida das versoes](sprint-01-validacao/versions.txt).

Imagem final de producao: `sha256:42fc39713e3e37fb4081695750b41513e2fe29ee7670b0103190bea7d167efcb`. Imagem final de teste: `sha256:2c8aa0fe8b2979f796a040572cc70a62b4b95c3c0d850efc60b6ac0c2e79bbb2`. As imagens base e os locks continuam nos digests/hashes originais da Sprint 1.

## Reproducao

Em checkout limpo do commit entregue, sem `.env`, com Docker Linux e shell POSIX (Git Bash no Windows):

```sh
docker build --no-cache -t oceanblue-production .
sh scripts/validate_image.sh oceanblue-production
docker compose -p oceanblue-s01-validation -f compose.test.yml build --no-cache
docker compose -p oceanblue-s01-validation -f compose.test.yml up --build --abort-on-container-exit --exit-code-from test
docker compose -p oceanblue-s01-validation -f compose.test.yml cp test:/app/coverage.xml coverage.xml
docker compose -p oceanblue-s01-validation -f compose.test.yml cp test:/tmp/junit.xml junit.xml
docker compose -p oceanblue-s01-validation -f compose.test.yml --profile smoke up -d --build --wait --wait-timeout 120 smoke
docker compose -p oceanblue-s01-validation -f compose.test.yml --profile smoke exec -T smoke python -m scripts.validate_smoke
docker compose -p oceanblue-s01-validation -f compose.test.yml --profile smoke logs --no-color
docker compose -p oceanblue-s01-validation -f compose.test.yml --profile smoke down -v
```

Repita de `up --build` ate `down -v` para validar a segunda execucao. O projeto exclusivo evita colisao com os outros composes. O smoke inicia em banco vazio porque o tmpfs perde dados quando o banco e parado apos a suite.

## Evidencias novas

- Antes: [baseline 63 testes](sprint-01-validacao/suite-before.txt), [startup falhando](sprint-01-validacao/regression-before.txt), [schema falhando](sprint-01-validacao/schema-regression-before.txt), [21 diferencas](sprint-01-validacao/schema-before.txt), [imagem insegura recusada pelo novo gate](sprint-01-validacao/image-regression-before.txt).
- Instalacoes sem cache: [teste](sprint-01-validacao/install-test.txt), [producao](sprint-01-validacao/install-production.txt); [gate negativo final](sprint-01-validacao/image-negative.txt).
- Reteste 1: [pipeline](sprint-01-validacao/pipeline-1.txt), [JUnit](sprint-01-validacao/junit-1.xml), [cobertura](sprint-01-validacao/coverage-1.xml), [smoke](sprint-01-validacao/smoke-check-1.txt), [logs de servicos](sprint-01-validacao/services-1.txt).
- Reteste 2: [pipeline](sprint-01-validacao/pipeline-2.txt), [JUnit](sprint-01-validacao/junit-2.xml), [cobertura](sprint-01-validacao/coverage-2.xml), [smoke](sprint-01-validacao/smoke-check-2.txt), [logs de servicos](sprint-01-validacao/services-2.txt).
- Casos adicionais: [reinicio e sentinela](sprint-01-validacao/smoke-restart.txt), [banco desligado](sprint-01-validacao/database-outage.txt), [variavel ausente](sprint-01-validacao/missing-test-database.txt), [banco nao vazio](sprint-01-validacao/nonempty-database.txt), [limpeza final](sprint-01-validacao/cleanup-final.txt).
- Integridade dos artefatos: [SHA-256](sprint-01-validacao/sha256sums.txt).

## Limites do aceite

O gate de schema compara tabelas, colunas, tipos reconhecidos pelo Alembic, nulabilidade, indices, unicidades e FKs. Nao certifica todos os server defaults, CHECKs ou labels de ENUMs historicos. O teste com dados cobre seis registros representativos e um valor invalido; nao representa todas as bases legadas possiveis. A nova migration exige valores validos e referencias existentes, usa DDL transacional e pode bloquear tabelas durante a conversao: a janela de uma atualizacao produtiva deve ser avaliada separadamente.

Cobertura de 53,37% e o gate inicial da Sprint, nao homologacao funcional integral. Nao houve chamadas a Asaas/Focus/SEFAZ, deploy, teste de carga, backup/restore produtivo ou teste Python nativo Windows. A unica pendencia para a decisao desta validacao e obter o pipeline remoto verde no SHA integrado; nao ha falha local conhecida restante nos gates exercitados.
