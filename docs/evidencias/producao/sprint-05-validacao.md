# Sprint 5 — validacao destrutiva independente

Data: 2026-09-07, America/Sao_Paulo. Tarefa 10/14. Execucao exclusivamente local.

## Decisao

**GO para homologacao local da Sprint 5 corrigida.** Cinco defeitos reproduzidos e corrigidos
(quatro altos e um medio), zero falhas criticas/altas conhecidas abertas no escopo exercitado.
As duas regressoes integrais independentes aprovaram **547 testes cada**, sem falhas, erros ou skips,
com **72,64% de cobertura combinada**. Migrations, schema, navegador, imagem produtiva, smoke,
indisponibilidade real do banco, correspondencia de fontes e limpeza passaram nas duas rodadas.
O GO considera a reconstrucao offline sobre dependencias congeladas, detalhada abaixo; nao autoriza
push, deploy ou integracoes externas.

## Base, metodo e isolamento

Worktree recebido limpo em `352a77c7d39836e57b6d9f366d3fc7a83d0a3f3b`; fast-forward local,
antes de editar qualquer arquivo, para `df6eed4c8f863cbc398c5887011389e4a062da11`.
Lidos integralmente `sprint-05-execucao.md`, a matriz `ciclos-financeiros-relacionamento.md`,
`validate_sprint05.ps1` e seu runner efetivo `validate_sprint04.ps1`.

Os primeiros ataques executaram na imagem congelada da execucao,
`sha256:911e78aca5b6e2fe786fe5afa31c75323e3295aa74c0cdeccfe5f2de684ce2b6`, com somente o novo
arquivo de testes copiado para o container. Nenhum arquivo da aplicacao foi alterado nesse container
ate preservar as provas `before`, `expanded-before` e `access-before`.
O manifesto original preserva hashes dos **273 arquivos**; a comparacao com os blobs de `df6eed4`
confirmou igualdade de conteudo apos normalizar exclusivamente CRLF/LF. A imagem anterior continha
finais de linha mistos do checkout Windows. Essa verificacao da base nao e apresentada como igualdade
bruta de bytes com os blobs Git. As imagens finais sao comparadas byte a byte com o checkout testado.

PostgreSQL 16.12 real, dados sinteticos, bancos `oceanblue_test` em tmpfs, redes Compose internas,
sem portas publicadas. Projetos exclusivos `oceanblue-s05-audit`, `...-round1`, `...-round2`,
`...-accept1` e `...-accept2`. Os tres servicos preexistentes foram preservados.
O bloqueio de sockets dos testes e o bloqueio de requisicoes externas do Chromium permanecem ativos.
Adaptadores de clientes recusam transporte externo; os cenarios de entrega usam apenas simuladores.
Nao houve push, deploy, SMTP/WhatsApp externo, emissao bancaria/fiscal ou acesso a dados reais.

O build canonico com `--network none` recusou a instalacao de dependencias sem cache acessivel;
o log foi preservado em `offline-build-test.txt`. Nao se habilitou rede para contornar o bloqueio.
`Dockerfile.validation` reconstruiu as fontes sobre as imagens locais congeladas de teste e producao,
com `--network none --pull=false`; os IDs das bases, os dois locks e os Dockerfiles canonicos sao
conferidos antes de cada build. A base produtiva e
`sha256:b2d581913deed102e29c0843665662e6d3ce1fe92319b89b70212360baf4c52f`.
O runner usa `--pull never` e bancos novos. Dependencias sao herdadas e verificadas por `pip check`,
sem nova instalacao online. Essa limitacao de reproducao offline esta explicitamente preservada.

## Defeitos reproduzidos e corrigidos

| ID | Severidade | Antes, na imagem congelada | Correcao e prova |
|---|---|---|---|
| S05V-01 | Alta | Descadastro ou anonimizacao confirmados depois do claim ainda permitiam chamar o transporte | Worker readquire o bloqueio do tenant, recarrega cliente/contato e cancela antes do transporte; `test_privacy_committed_after_claim_prevents_transport`, dois casos |
| S05V-02 | Alta | Permissao de envio revogada depois do claim nao impedia transporte com escopo antigo | Releitura do operador, permissoes e acesso a empresa apos claim; interrupcao sem transporte e INCERTO persistido; `test_send_revalidates_permission_after_claim` |
| S05V-03 | Alta | SQL direto podia marcar origem como revertida sem contrapartida ou apagar o marcador depois do estorno | Migration `9c0d1e2f3a4b`, trigger diferido ate commit exige contrapartida integral e impede desfazer marcador; `test_ledger_reversal_marker_cannot_be_forged`, dois casos |
| S05V-04 | Alta | Solicitacao de vale ainda era autorizada apos remover vinculo do beneficiario com a empresa | Revalidacao do vinculo e atividade na autorizacao; `test_advance_approval_rechecks_employee_company_link` |
| S05V-05 | Media | `9999999999.999` passava na validacao e arredondava para fora de Numeric(12,2) | Limite rechecado depois do HALF_UP; `test_rounded_money_cannot_overflow_storage` e ataque HTTP de overflow |

As correcoes de aplicacao limitam-se a tres servicos e uma migration nova. Nao se alteraram migrations
historicas, contratos de provedores ou gates de cobertura. Nenhum teste anterior foi removido,
desativado, convertido em skip/xfail ou flexibilizado para aprovar uma falha.

O transporte mantem o bloqueio ate confirmar seu resultado. Uma alteracao de consentimento que
ocorra depois do inicio efetivo da tentativa aguarda sua conclusao; uma alteracao ja confirmada
antes dessa fronteira e relida e respeitada. O claim permanece duravel em INCERTO se houver crash
ou confirmacao perdida. Nao ha promessa de exactly-once fora do banco.

## Matriz de ataques e reconciliacao

Prefixo dos novos casos abaixo: `tests/test_sprint05_adversarial.py`. As suites anteriores inteiras
tambem executam nas duas rodadas. O inventario de 160 rotas foi regenerado para incluir os novos testes.

| Area / ataque | Prova e resultado esperado |
|---|---|
| Ledger direto | Oito alteracoes de identidade, valor, empresa, tenant, tipo e data recusadas; exclusao permanece coberta por `test_sprint05_cycles`; marcador forjado ou desfeito tambem recusado |
| Estorno formal | Falhas em INSERT financeiro, auditoria, idempotencia e commit preservam uma unica origem nao revertida; reteste cria exatamente uma contrapartida; replay nao duplica |
| Caixa concorrente | Tres sessoes tentam reabrir a mesma revisao: uma vence; ajuste posterior retorna revisao 3 e diferenca de R$ 0,01; replay divergente recusado |
| Caixa e falhas | Falhas no fechamento, auditoria, cache e commit preservam FECHADO/revisao 1; retentativa confirma revisao 2 |
| Conciliacao integral | 1.001 vendas no dia local somam R$ 20,00 em PDV e financeiro; venda um segundo antes da meia-noite fica no dia anterior; nenhuma truncagem de 1.000 registros |
| Divergencia real | Entrada extra de R$ 0,01 e detectada e impede criar fechamento; zero fechamento persistido |
| Vales completos | Dinheiro e produto: PENDENTE → AUTORIZADO → BAIXADO → AUTORIZADO → ESTORNADO; estoque integralmente reposto, duas contrapartidas iguais, saldo de folha zero; testes de execucao preservados |
| Transicoes invalidas | Todas as 20 combinacoes proibidas entre cinco estados e cinco acoes recusadas sem alterar saldo ou estado |
| Falhas de vale | Autorizacao e estorno de produto em cinco fronteiras cada: movimento, financeiro, estado, auditoria, idempotencia; rollback de quantidades e valores e replay unico |
| Concorrencia de vale | Tres autorizacoes com a mesma chave produzem uma saida; vinculo removido antes da autorizacao bloqueia efeitos |
| Valores e IDs | NaN, infinitos, expoente extremo, limite arredondado, fracionados, booleanos e centavos exercitados em servico e API; nove novos casos HTTP sem efeitos |
| Cashback | Corrida em tres sessoes entre consumir credito vencido, expirar e cancelar origem; consumo recusado, carteira/credito zero e conciliacao consistente; replay divergente e cancelamentos parciais/integral preservados nas suites anteriores |
| Enfileiramento | Falhas em mensagem, auditoria e commit deixam zero mensagem; venda/fila/cashback transacionais exercitados tambem nas suites 4 e 5 |
| Transporte parcial | Lote ENVIADO / INCERTO / ENVIADO; nenhuma tentativa automatica adicional; erros de transporte nao vazam resposta privada |
| Crash de worker | Antes do commit do claim: PENDENTE; antes/depois do transporte ou no ack: INCERTO duravel; controle transacional nunca duplica a tentativa aceita |
| Backoff e limites | Limite de 1.000 mensagens em 24 horas disputado por tres sessoes com uma unica vaga; duas recusadas; backoff testado exatamente em 60 segundos; cinco tentativas/ESGOTADO cobertos na suite de ciclos |
| Consentimento concorrente | Descadastro e anonimizacao confirmados na janela claim/transporte bloqueiam envio; permissao revogada nessa janela tambem bloqueia |
| Exportacao/anonimizacao | Cinco fronteiras de falha restauram cadastro, mensagem, resposta idempotente e auditoria; reteste remove nome/documento/email de exportacao e caches, preservando uma venda e seu financeiro |
| Tenant / empresa | Sessao de outro tenant nao exporta nem estorna; historico HTTP de mensagens omite empresa fora do escopo; novas permissoes relidas em sessao existente |
| CSRF | Oito endpoints novos recusam escrita sem token; ataques validos usam token e seguem as validacoes de negocio |
| Navegador real | Novo E2E perde a resposta apos gravar um vale de R$ 0,01, repete o mesmo payload/chave e autoriza um unico vale com um lancamento; cinco E2Es anteriores preservados |

## Iteracoes preservadas

- `before.txt/xml`: seis falhas intencionais, quatro defeitos iniciais reproduzidos.
- `expanded-before.txt/xml`: 41 aprovados e sete falhas; seis sao os defeitos iniciais. A setima
  e uma montagem de fixture com data fora do mes corrente, corretamente recusada pelo trigger de quota.
  O teste passou a usar o mes real do PostgreSQL, preservando a fronteira de meia-noite.
- `access-before.txt/xml`: dois aprovados (isolamento de empresa e 1.001 vendas) e uma falha
  real adicional de revogacao de permissao apos claim.
- `retest.txt/xml`: 101 aprovados, combinando os primeiros ataques e toda a suite de ciclos.
- `expanded-retest.txt/xml`: 82 aprovados, incluindo todos os novos ataques e o novo E2E.
- `iteration-e2e/`: screenshot, HTML, trace e diagnostico; screenshot inspecionado, campos e acoes legiveis.
- `round1/`, `round2/`: primeiras inicializacoes integrais pararam no inventario desatualizado,
  antes de executar testes; recursos removidos. Logs mantidos, sem contabiliza-las como regressao aprovada.
- `accept1/`, `accept2/`: duas regressoes integrais efetivas, PostgreSQL inicialmente vazio,
  builds e pipelines independentes. Resultados finais abaixo.

## Gates finais

| Gate | accept1 | accept2 |
|---|---|---|
| Runner independente | Exit 0 | Exit 0 |
| PostgreSQL inicial | Vazio, tmpfs, exclusivo | Vazio, tmpfs, exclusivo |
| Inventario / dependencias | 160 rotas; pip check teste/producao OK | Mesmo resultado |
| Migrations | 26 revisions, head `9c0d1e2f3a4b`; upgrade individual, downgrade base, reupgrade, sentinela preservada | Mesmo resultado |
| Schema | 47 tabelas; colunas, tipos, indices e FKs compativeis | Mesmo resultado |
| Suite integral | **547 aprovados**, 0 falhas/erros/skips; 1.251,375 s | **547 aprovados**, 0 falhas/erros/skips; 1.246,519 s |
| Conjunto de casos | Os mesmos 547 identificadores nas duas rodadas | Conferido por comparacao ordenada |
| Linhas | 8.709 / 11.476 = **75,89%** | Identico |
| Ramos | 1.510 / 2.592 = **58,26%** | Identico |
| Cobertura combinada | 10.219 / 14.068 = **72,64%**; gate de 50% preservado | Identico |
| Navegador | 6 casos Chromium 140.0.7339.16; zero erros JS e requisicoes externas | Mesmo resultado |
| Imagem produtiva | UID 1000; default production; quatro variaveis obrigatorias recusadas antes de banco | Mesmo resultado |
| Smoke HTTP | Entrypoint, migrations, Gunicorn, health/readiness 200, proxy forjado 403 | Mesmo resultado |
| PostgreSQL desligado | Health 200, readiness 503, login falha fechado | Mesmo resultado |
| Fontes byte a byte | 278 arquivos contra imagem de teste **e** produtiva | 278 arquivos contra ambas |
| Rede | Internal=true, sem portas publicadas, adaptadores bloqueados | Mesmo resultado |
| Limpeza | Zero containers e redes do projeto | Zero containers e redes do projeto |

As rodadas correram em paralelo, com processos, bancos e redes distintos. Nao compartilharam fixtures,
conexoes ou arquivos de resultado. Os 465 casos anteriores permanecem, acrescidos de 81 ataques e
um E2E. Nenhuma fonte executavel foi alterada depois dos builds de aceite.

Imagens de accept1: teste `sha256:ccab7b4eaebd49afa5a70ce9dd29ebec76d3a3c711704149d641c0acf37fb477`;
producao `sha256:896e64670d1cf36bd15ae5b97784fed1ff564de6b98cbeaadaca9d8fa74529b1`.
Imagens de accept2: teste `sha256:f1cd3cbdbcb4a110f1ecb391e3017c516ae17f0f2835a951d7d7c14de1e4c8ef`;
producao `sha256:fec7f968f6fd76de90c35c3f4892459840f14282324d3d17e79daf34166faaad`.

Evidencias: [resumo conferido](sprint-05-validacao/accept-summary.json),
[JUnit 1](sprint-05-validacao/accept1/junit.xml), [JUnit 2](sprint-05-validacao/accept2/junit.xml),
[cobertura 1](sprint-05-validacao/accept1/coverage.xml), [cobertura 2](sprint-05-validacao/accept2/coverage.xml),
[pipeline 1](sprint-05-validacao/accept1/pipeline.txt), [pipeline 2](sprint-05-validacao/accept2/pipeline.txt),
[limpeza final](sprint-05-validacao/cleanup-final.txt) e [hashes](sprint-05-validacao/sha256sums.txt).
Os screenshots finais de ciclos e replay foram inspecionados. Os traces e diagnosticos dos seis
cenarios de cada rodada estao nos respectivos diretorios `e2e/`.

## Reproducao e limites

```powershell
pwsh -NoProfile -File scripts/validate_sprint05_adversarial.ps1 -Project oceanblue-s05-audit-repro1 -EvidenceDirectory docs/evidencias/producao/sprint-05-repro1
pwsh -NoProfile -File scripts/validate_sprint05_adversarial.ps1 -Project oceanblue-s05-audit-repro2 -EvidenceDirectory docs/evidencias/producao/sprint-05-repro2
```

Exige Docker Linux, PowerShell 7 e as duas imagens congeladas locais com os IDs verificados pelo runner.
Nao faz download de dependencias. Cada rodada cria seu banco, aplica todas as revisions, executa
downgrade base/reupgrade, verifica schema e roda a suite integral com cobertura e Chromium/Gunicorn.
Depois verifica ambas as imagens contra as fontes, smoke, banco desligado e limpeza em finally.

O resultado e restrito a homologacao local e ao modelo de concorrencia serializado por tenant.
Nao mede throughput produtivo nem cobre outros navegadores. O bloqueio durante o adaptador pode
acrescentar latencia; provedores reais continuam proibidos. Gatilhos nao constituem protecao contra
superusuario que desabilite triggers, altere DDL ou execute TRUNCATE; a limpeza descartavel usa esse
privilegio exclusivamente no banco de testes. Crash abrupto e simulado por interrupcao BaseException
e remocao da sessao; indisponibilidade do PostgreSQL e exercitada desligando o servico de fato.

Dados operacionais anonimizados preservam IDs e obrigacoes financeiras; auditorias/textos livres,
documentos historicos, backups e exportacoes anteriores obedecem aos limites ja registrados no guia.
O aceite nao homologa boleto, Nota Fiscal, SMTP ou WhatsApp. Hashes dos artefatos estao em
`sprint-05-validacao/sha256sums.txt`; o SHA do unico commit local e informado ao concluir, sem
autoreferencia circular no relatorio.
