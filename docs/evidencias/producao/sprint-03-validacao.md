# Sprint 3 — validacao destrutiva independente

Data local: 2026-09-06, America/Sao_Paulo; artefatos em 2026-09-07 UTC.

## Decisao

**GO para a Sprint 3 no escopo validado. Zero falhas criticas ou altas conhecidas abertas.** Oito defeitos corrigidos, **291 testes aprovados (74 novos)**, zero falhas/erros/skips, migrations e smoke produtivo aprovados no PostgreSQL real. Este GO nao autoriza deploy nem integracoes reais.

| Gate final | Resultado |
|---|---|
| Dependencias/inventario | `pip check` em teste e producao; 146 rotas conferidas |
| Migrations/schema | 23 revisions, upgrade individual, downgrade base, reupgrade e sentinela; 46 tabelas compativeis com os modelos |
| Suite/JUnit | 291 testes; 0 falhas, 0 erros, 0 skips; 358,741 segundos |
| Cobertura | 7.552/10.715 linhas e 1.222/2.392 ramos; combinado 8.774/13.107 = **66,94%**, gate de 50% preservado |
| Imagem | Default production, usuario nao root, quatro variaveis obrigatorias recusadas individualmente antes de conectar ao banco |
| Smoke | Entrypoint, migrations e Gunicorn; health/readiness 200; headers de proxy forjados recusados com 403 |
| Banco parado | Health 200, readiness 503 e login falha fechado, sem sessao emitida |
| Codigo testado | 232 arquivos de app/tests/scripts/migrations conferidos contra a imagem final: 230 identicos byte a byte; dois diferem somente pela remocao de uma linha vazia final no fechamento de whitespace |
| Limpeza | Containers e redes dos tres projetos removidos; containers preexistentes preservados |

Imagem final de teste: `sha256:bedc4eb7d77193d371ba833231bde1e840b2097e18ec641a4d319cb94bb4d5ae`. Producao: `sha256:3824c02474f76eaa293de249a12bbe0002ffbd8fbf45fef268adea4485732653`.

## Base e isolamento

Worktree inicialmente limpo e destacado em `352a77c`. Sincronizacao inicial por fast-forward exclusivamente com a **main local `acb85cf`**; nenhum fetch, push ou integracao de entrega. Lidos `sprint-03-execucao.md` e os GOs independentes das Sprints 1 e 2 antes das alteracoes. O GO anterior documentava 217 testes na execucao da Sprint 3 e 166 na validacao da Sprint 2; esta validacao acrescenta provas independentes.

PostgreSQL 16.12 real em tmpfs, redes Compose internas, sem portas publicadas, dados exclusivamente sinteticos. Projetos desta tarefa: `oceanblue-s03-attack`, `oceanblue-s03-nan-before` e `oceanblue-s03-validation-final`. Os containers preexistentes `blueocean_db`, `wnr_triagem_api` e `wnr_triagem_db` nao foram alterados. Nenhum deploy, merge de entrega, CI remoto ou integracao real de boleto/Nota Fiscal.

## Defeitos reproduzidos e corrigidos

| ID | Severidade | Antes | Depois |
|---|---|---|---|
| VAL03-01 | Alta | Venda de 10,00 aceita cashback 9,99 sem cliente, com pagamento de 0,01 e baixa de estoque. | API recusa com 400; venda, pagamentos, financeiro, idempotencia e estoque permanecem intactos. |
| VAL03-02 | Alta | Devolucoes unitarias arredondadas isoladamente retornam 30,00 para uma venda de 29,99, 29,97 para 29,98 ou zero para uma venda de 0,01. | Rateio acumulado conserva cada centavo e o total cancelado, com uma linha de tres unidades ou tres linhas separadas. |
| VAL03-03 | Alta | Tres pagamentos de 0,01 concentram estornos no mesmo pagamento original, excedendo seu valor e deixando outros sem devolucao. | Rateio limitado ao saldo restante por origem; cada pagamento termina com estorno exato. |
| VAL03-04 | Alta | Cancelar todas as unidades pode deixar cashback gerado disponivel por arredondamento individual. | Recalculo do credito restante; cancelamento por itens zera o credito e a carteira correspondente. |
| VAL03-05 | Alta | Restituicoes de tres creditos de 0,01 tentam devolver 0,02 ao mesmo credito; CHECK do PostgreSQL impede concluir a devolucao. | Cada credito e restituido dentro de seu saldo consumido; carteira e creditos fecham exatamente em 0,03. |
| VAL03-06 | Media | Excluir funcionario autor de produto permite ao ORM anular a autoria historica e remover o cadastro. | Referencias historicas impedem exclusao/retirada de vinculo; snapshot de todas as tabelas permanece identico. |
| VAL03-07 | Media | Atualizacao sem campo de barcode troca o codigo cadastrado por outro gerado. | Omissao preserva o codigo; conflito concorrente tem uma vencedora e preserva o codigo da perdedora. |
| VAL03-08 | Alta | SQL direto persiste NaN em custos, salarios, vendas, pagamentos, itens, financeiro e movimentos. CHECKs de nao-negatividade nao bastam no PostgreSQL. | Nova migration protege 47 colunas NUMERIC em 19 tabelas; legado invalido recusa upgrade sem alterar valores nem revision anterior. |

## Matriz de provas

| Area | Execucao e invariantes verificadas |
|---|---|
| Falhas injetadas | Falha apos INSERT real de venda, item, pagamento, estoque, financeiro, idempotencia, credito e movimento de carteira; falhas em cancelamento integral/parcial, pais e vinculos; falha no commit final sem emitir notificacao. Snapshots completos e retry comprovam rollback sem efeitos residuais. |
| Concorrencia e repeticao | Sessoes independentes com barreira de partida: duas vendas da ultima unidade com chaves distintas; mesma chave com payload diferente; replay de criacao/cancelamento; cancelamento integral contra parcial; retornos manuais repetidos; bloqueios por tenant e saldo. |
| Barcode | Geracao EAN-13 simultanea, criacao com mesmo barcode, atualizacao concorrente e preservacao por omissao. |
| Multiempresa/historico | Vinculos, estoque e atividade por empresa; mudanca de empresa recusada; empresas de outro tenant em lote; replay revalida acesso; exclusoes protegidas e autoria preservada. |
| Importacoes | Todos os seis layouts XLSX: preview, confirmacao, exportacao/reimportacao; erro na ultima e na linha intermediaria; alteracao previa revertida; falha apos INSERT real; lotes duplicados concorrentes; formulas, NCM, atacado, estoque divergente e quantidades invalidas. |
| Cotas | Ultima vaga disputada por lotes, cadastro contra lote e suite anterior de cotas de produtos, funcionarios, empresas e vendas. Sem excedentes nem categorias/pais orfaos. |
| Dinheiro | Descontos de 0,01/0,02 e quase total; pagamento repartido; cashback consumido/gerado; NaN/sNaN/infinitos/limites; somas persistidas de pagamentos, devolucoes, carteira e creditos conferidas. |
| Integridade SQL | Auditoria de todas as FKs do metadata apos importacao, venda, cancelamento e replay; nenhum filho sem pai; saldo de estoque igual a soma dos movimentos e financeiro liquido zero. |
| Legado | Baixa de venda duplicada, enum legado invalido e NaN em produto/venda recusam migrations atomicamente; dados sinteticos preservados, corrigidos somente pelo teste e upgrade repetido com sucesso. |

Os ataques concorrentes usam PostgreSQL real, threads e sessoes distintas; mocks sao usados para injetar falhas ou impedir transporte externo, nao para simular o banco. Sequencias podem avancar apos rollback: ausencia de orfaos nao exige IDs consecutivos.

## Execucoes e artefatos

- Primeira rodada: [9 falhas e 35 aprovados](sprint-03-validacao/before.txt). A selecao de itens pelo indice da resposta foi posteriormente corrigida para usar IDs estaveis; a ordem SQL pode mudar apos UPDATE.
- Ataques adicionais: [primeira iteracao](sprint-03-validacao/extra-before.txt) continha erros de fixture (configuracao transitoria nao adicionada e permissao global ainda presente); [rodada corrigida](sprint-03-validacao/extra-before-corrected.txt) reproduz tres defeitos reais e aprova seis casos.
- Banco antes: [sete gravacoes NaN indevidamente aceitas](sprint-03-validacao/nan-before.txt).
- Retestes: [101 aprovados e tres erros de selecao de item do teste](sprint-03-validacao/retest.txt); apos corrigir os IDs, [142 aprovados, zero falhas](sprint-03-validacao/retest2.txt).
- Comparacao consolidada: [testes finais contra a imagem congelada da base](sprint-03-validacao/baseline-final.txt): **19 falhas reais e 41 aprovados**, reproduzindo os oito defeitos sem os erros de fixture das iteracoes. Os tres testes exclusivos da nova migration foram deliberadamente deselecionados apenas nessa comparacao anterior; todos passam no aceite final.
- Aceite completo: [build](sprint-03-validacao/build.txt), [pipeline](sprint-03-validacao/pipeline.txt), [JUnit](sprint-03-validacao/junit.xml), [cobertura](sprint-03-validacao/coverage.xml), [smoke](sprint-03-validacao/smoke.txt), [banco indisponivel](sprint-03-validacao/database-outage.txt) e [SHA-256](sprint-03-validacao/sha256sums.txt).
- Rastreabilidade: [hashes dos arquivos da imagem](sprint-03-validacao/source-image.json), [conferencia do checkout](sprint-03-validacao/source-check.txt), [imagens da base](sprint-03-validacao/baseline-images.txt), [limpeza final](sprint-03-validacao/cleanup.txt) e [ausencia de recursos residuais](sprint-03-validacao/cleanup-check.txt).

Depois do pipeline, o gate do indice Git detectou uma linha vazia extra no fim dos dois arquivos novos `6f7a8b9c0d1e_finite_money.py` e `validate_sprint03_adversarial.ps1`. Somente essas linhas finais foram removidas; a comparacao contra a imagem comprova igualdade integral dos demais bytes. Nenhuma logica mudou apos os testes.

## Reproducao e limites

Docker Linux e PowerShell 7, na raiz do checkout:

```powershell
pwsh -NoProfile -File scripts/validate_sprint03_adversarial.ps1 -Project oceanblue-s03-validation-repro
```

O projeto deve ser novo. O runner constroi teste e producao, verifica dependencias, usuario nao root, configuracao production e ausencia de cada segredo obrigatorio, inventario, migrations individuais/ida-volta, suite completa e cobertura minima de 50%. Em seguida inicia Gunicorn, confere HTTP/headers, para somente seu PostgreSQL para testar falha fechada e remove seus containers/rede em `finally`.

A comparacao anterior usou a imagem imutavel da base `acb85cf`, `sha256:9a829c3d3618896a6423b38f5756d9c6e0bb77b164eef888696e2fc6808747ce`, com os testes finais montados somente para leitura e outro PostgreSQL descartavel. Para reproduzir essa comparacao, construa a imagem de `acb85cf` em checkout isolado, monte a pasta `tests` desta entrega e execute `python -m pytest tests/test_sprint03_adversarial.py tests/test_sprint03_database.py --no-cov -k 'not finite_migration and not all_numeric'`. O resultado esperado na base e falha; nao e gate de aceite. Nunca direcione esses testes a um banco preenchido ou externo.

As suites novas sao `tests/test_sprint03_adversarial.py`, `tests/test_sprint03_database.py` e `tests/test_sprint03_faults.py`. Os testes e gates existentes permanecem habilitados; nao foram usados skips, xfails ou reducao de cobertura. Os seis formatos sao layouts de entidades, nao seis extensoes de arquivo.

O aceite e local no escopo exercitado, sem homologacao visual integral, carga produtiva, proxy externo ou providers reais. Notificacoes posteriores ao commit continuam sem fila duravel. A idempotencia de novas vendas depende de preservar a chave; chamadas internas legadas sem chave nao prometem deduplicacao. A migration nao reconcilia automaticamente valores historicos invalidos e requer investigacao antes da implantacao futura. Os erros SQL nos logs sao negativos intencionais com dados sinteticos.
