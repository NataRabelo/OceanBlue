# Sprint 3 — integridade transacional, cadastros, estoque e lotes

Data local: 2026-09-06, America/Sao_Paulo. Artefatos finais: 2026-09-07 UTC.

## Resultado

**Execucao local aprovada: 217 testes, zero falhas, erros ou skips; migrations, imagem e smoke aprovados.** Sao 51 casos novos sobre os 166 da Sprint 2. Cobertura combinada de linhas e ramos: **65,83%**, preservando o gate de 50% e todos os modulos de `app`.

Worktree inicialmente limpo e destacado em `352a77c`; sincronizado por fast-forward exclusivamente com a **main local `2b75727619d5f9f718b38c034aa759b44b2e743e`**. As evidencias das Sprints 1 e 2 foram consultadas e o **GO em `sprint-02-validacao.md`** foi confirmado antes de alterar codigo. O CI remoto da Sprint 2, run `34073219979`, foi informado pela coordenacao; esta tarefa nao consultou nem alterou remotos.

## Gates finais

| Gate | Evidencia e resultado |
|---|---|
| Dependencias | Imagens Python 3.12.12 com locks/hashes existentes; `pip check` aprovado em teste e producao |
| Inventario | 146 rotas; vinculos estaticos com novos testes atualizados e `--check` aprovado |
| Migrations | 22 revisions; upgrade individual, downgrade ate base, reupgrade e tenant sentinela preservado |
| Schema | 46 tabelas; colunas, tipos, indices e FKs conferidos com os modelos |
| Pytest/JUnit | 217 testes; 0 falhas, 0 erros, 0 skips; 223,915 segundos |
| Cobertura | 7.439/10.688 linhas e 1.166/2.384 ramos; combinado 8.605/13.072 = 65,83% |
| Imagem | Default production, usuario nao root e recusa individual das quatro variaveis obrigatorias ausentes antes de conectar ao banco |
| Smoke produtivo | Entrypoint/migrations/Gunicorn; health e readiness HTTP 200; headers de esquema forjados recusados com 403 |
| Banco parado | Health 200; readiness 503; login falha fechado, sem emitir sessao |
| Interface | Sintaxe dos quatro arquivos JavaScript alterados aprovada; fluxos HTTP de cadastro multiempresa, pre-validacao e venda/cancelamento cobertos |
| Git | Verificacao de whitespace aprovada; commit somente depois do aceite de todos os gates |
| Isolamento | PostgreSQL 16.12 em tmpfs, rede interna, nenhuma porta publicada; projetos `oceanblue-s03-dev` e `oceanblue-s03-final` removidos |

Imagens finais: teste `sha256:9018e204ab07c0bb7218d2844ffc519d3016e903662baccaf61182d9d6c348fd`; producao `sha256:bcd432b1634d61e1224062d6666c21e94fedd898d1fb9d7c3dc11e04e29cb8b9`.

## Entrega e provas

| Area | Implementacao | Provas reproduziveis |
|---|---|---|
| Atomicidade | Fronteira transacional nos servicos; commits internos tornam-se flush; rollback unico; notificacoes posteriores ao commit | Falha depois de inserir filho de produto, funcionario e perfil; falha ao excluir pai; troca de permissoes interrompida; falha financeira apos baixa; falha no estorno e no commit final |
| Orfaos | Exclusao de ultimo vinculo e pai na mesma transacao; categorias em uso e produtos com saldo/historico protegidos | Pais e vinculos mantem contagens anteriores nas falhas injetadas; produto sem historico removido junto ao ultimo vinculo |
| Multiempresa | Novo vinculo de produto sem outra vaga de produto; preco/saldo/atividade por empresa; conjunto de empresas do funcionario substituido atomicamente | Duas empresas no mesmo tenant; vinculacao/exclusao; falha com empresa estrangeira preserva nome e conjunto antigo; troca da empresa principal; desativacao local |
| Validacoes | Categoria ativa e nomes validos; valores finitos; quantidades inteiras; atacado e NCM; codigo de barras normalizado e unico | Casos parametrizados invalidos sem pais residuais; conflito entre nome e barcode; NCM/fracao/formula recusados no lote |
| Concorrencia | Bloqueio transacional por tenant compatível com cotas e bloqueio de linha do saldo | Quatro geracoes EAN-13 distintas; duas tentativas do mesmo barcode com uma vencedora; quatro saidas da ultima unidade com uma vencedora; tres reversoes manuais com um unico retorno |
| Venda/idempotencia | Chave obrigatoria nas APIs de venda e cancelamento parcial; resposta persistida com os efeitos; indice unico de baixa por item | Tres criacoes concorrentes com mesma chave resultam em uma venda/baixa; tres cancelamentos parciais repetidos devolvem uma unidade; cancelamento integral e callbacks repetidos nao duplicam saldo; HTTP retorna mesma resposta e recusa chave ausente/payload diferente |
| Importacao | Pre-validacao sem gravacao e confirmacao integral; savepoints por linha; relatorio; cotas sob bloqueio | Seis layouts com preview/importacao/exportacao/reimportacao; erro na ultima linha reverte todo lote; ultima vaga disputada por dois lotes com uma vencedora e sem categoria orfa |
| Atacado e estoque importado | Tres colunas de atacado/varejo preservadas; saldo inicial gera movimento; saldo existente nao e sobrescrito | Roundtrip preserva varejo 10, atacado 8, minimo 5 e saldo 3; reimportacao nao duplica movimento; saldo divergente de produto existente recusa lote |
| Migration com legado invalido | Novo indice recusa baixas duplicadas sem apagar historico | Downgrade controlado no banco de teste, duplicidade sintetica, upgrade recusado e revision anterior preservada; correcao apenas do dado sintetico e reupgrade aprovado |
| Auditoria HTTP | Identificacao do ator usa identidade ORM sem provocar nova consulta na abertura de conexao | Cadastro multiempresa e venda/cancelamento HTTP funcionam depois do commit, mantendo isolamento e auditoria da Sprint 2 |

Os testes concorrentes usam threads com barreira de partida, contextos Flask/sessoes independentes e PostgreSQL real, com limites de espera. As contagens persistidas de vendas, movimentos, saldos, vinculos e registros de idempotencia sao verificadas depois dos concorrentes terminarem. Nao se substituiu concorrencia de banco por mocks.

Suite nova: [`tests/test_sprint03_transactions.py`](../../../tests/test_sprint03_transactions.py). O teste de importacao/cotas da Sprint 2 foi adaptado do contrato de sucesso parcial para lote atomico e **ampliado**: continua comprovando criacao na ultima vaga e atualizacao de registro existente com a cota cheia. Nenhum teste foi removido, marcado skip/xfail ou excluido da cobertura.

## Iteracoes e falhas encontradas

1. Primeira verificacao funcional: 34 testes existentes aprovados. A primeira suite nova encontrou sete falhas: bloqueio `FOR UPDATE` aplicado aos lados opcionais de joins (incluindo reimportacao), uma linha de teste completamente vazia que era corretamente ignorada e a consulta recursiva do ator de auditoria apos commit. Corrigidos o alvo do bloqueio, o dado de teste e a identificacao do ator. Reteste direcionado: **82 aprovados**.
2. O primeiro pipeline completo parou no inventario, que precisava incorporar os novos testes. [Log preservado](sprint-03/iteration-inventory.txt). O inventario foi regenerado, mantendo o gate.
3. A rodada seguinte teve **215 testes aprovados e um erro de teardown**: o mock de falha no commit ainda estava ativo durante a limpeza do fixture. Seu escopo foi limitado ao trecho testado, preservando a verificacao de rollback. [Log preservado](sprint-03/iteration-teardown.txt). Essa rodada nao foi usada como aceite.
4. Uma verificacao auxiliar desativou a conversao Git de finais de linha e interpretou CRLF do checkout Windows como whitespace. [Saida integral preservada em gzip](sprint-03/iteration-line-endings.txt.gz). A verificacao final usa a normalizacao configurada pelo repositorio, sem alterar as regras de whitespace do codigo.
5. Revisao final acrescentou obrigatoriedade de chave nas APIs, replay HTTP e teste de migration com baixas legadas duplicadas; tambem preservou textos literais semelhantes a formulas na exportacao/reimportacao. **Aceite final: 217 aprovados, zero falhas/erros/skips**, em imagens reconstruidas e banco novo.

Os erros PostgreSQL presentes no log final sao ataques negativos intencionais e dados sinteticos: cotas, referencias estrangeiras e indices duplicados. Eles nao foram ocultados e suas respostas/rollbacks sao verificados pelos testes.

## Artefatos e reproducao

- [Pipeline completo, migrations e suite](sprint-03/pipeline.txt)
- [JUnit final](sprint-03/junit.xml) e [cobertura XML](sprint-03/coverage.xml)
- [Build](sprint-03/build.txt), [gate da imagem](sprint-03/image-gates.txt) e [identificadores](sprint-03/images.txt)
- [Smoke](sprint-03/smoke.txt), [headers](sprint-03/security-smoke.txt), [banco indisponivel](sprint-03/database-outage.txt) e [startup](sprint-03/smoke-startup.txt)
- [JavaScript e whitespace](sprint-03/static-checks.txt)
- [Hashes dos 220 arquivos de codigo conferidos byte a byte contra a imagem testada](sprint-03/source-sha256.txt); representam os bytes deste checkout Windows, incluindo finais de linha
- [Limpeza final](sprint-03/cleanup.txt), [limpeza de desenvolvimento](sprint-03/cleanup-dev.txt) e [SHA-256](sprint-03/sha256sums.txt)
- [Guia operacional, contratos e limites](../../02-instalacao-e-ambiente/integridade-sprint-03.md)

Em checkout desta entrega, com Docker Linux e PowerShell 7:

```powershell
pwsh -NoProfile -File scripts/validate_sprint03.ps1 -Project oceanblue-s03-repro
```

O nome do projeto deve estar livre. O runner preserva os gates existentes, coleta JUnit/cobertura, executa smoke e indisponibilidade real do seu banco e remove seus containers/rede em `finally`. Para repetir o gate adicional da imagem, em Git Bash:

```sh
sh scripts/validate_image.sh oceanblue-s03-repro-smoke
```

## Limites do aceite

Execucao local, sem push, merge de entrega, deploy, CI remoto da Sprint 3 ou integracoes reais de boleto/Nota Fiscal. A suite funcional existente de providers simulados foi preservada. Nenhum container de outro projeto nem banco externo foi alterado.

O bloqueio por tenant prioriza integridade; lotes grandes serializam outras escritas desse tenant. Notificacoes posteriores ao commit nao constituem fila duravel. Clientes HTTP devem enviar e preservar a chave de idempotencia; reiniciar uma venda como uma nova operacao gera outra chave. A validacao de interface cobre sintaxe, contratos e fluxos HTTP, sem alegacao de homologacao visual integral ou teste de carga produtiva. O aceite independente da Sprint 3 permanece separado desta evidencia de execucao.
