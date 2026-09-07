# Sprint 6 — prontidão operacional e endurecimento

Data: 2026-09-07, America/Sao_Paulo. Tarefa 11/14. Execução exclusivamente local.

## Decisão

**GO para homologação local da Sprint 6 e sua validação independente seguinte.** A regressão
integral aprovou **578 testes**, sem falhas, erros ou skips, com **73,45% de cobertura combinada**.
Zero falhas críticas/altas conhecidas abertas no escopo exercitado. As provas de banco/storage,
TLS, backup/restore, rollback e alertas passaram. O fechamento exige o único commit local e
worktree limpo, conferidos no encerramento. Não autoriza push, deploy, emissão bancária/fiscal
nem transporte externo; os limites abaixo fazem parte desta decisão.

## Base e isolamento

O worktree recebido estava limpo, em HEAD destacado `352a77c`. Antes de editar, foi aplicado
fast-forward para a main local validada `ed7112154a3e94186b17fbfc0717fb59684432bc`. Foram consultadas
as decisões e provas das Sprints 1–5, incluindo o **GO** em `sprint-05-validacao.md`.
As evidências históricas não foram substituídas.

PostgreSQL 16 real, dados exclusivamente sintéticos e projetos Compose com prefixo exclusivo
`oceanblue-s06-`. Redes internas e nenhuma porta publicada nas provas. As bases de teste usam
tmpfs; a prova operacional utiliza volumes separados de arquivos, certificados e restauração.
Os serviços preexistentes `blueocean_db`, `wnr_triagem_api` e `wnr_triagem_db` foram preservados.
As fixtures continuam bloqueando sockets externos, e o Chromium recusa requisições fora do
servidor local. Downloads de imagens/dependências de ferramentas não são contatos com provedores
de negócio. Nenhuma credencial ou dado real foi utilizado.

## Entrega

| Área | Resultado implementado |
|---|---|
| Persistência | Compose oficial com volumes de banco e instance; fonte root-owned, processo UID 1000, filesystem somente leitura, tmpfs limitado e umask 077 |
| Configuração | Secrets distintos, HTTPS obrigatório, origem do proxy explícita, timeouts de banco, credencial de runtime separada da credencial de migration |
| Flags | Boleto/Fiscal/externos explicitamente false; startup produtivo recusa true ou valor inválido; rotas e links ocultos/bloqueados; lookup de pagamento Boleto recusado |
| Dependências críticas | Health de processo independente; readiness verifica PostgreSQL, revision e escrita/fsync no storage; falhas retornam 503 e storage sem escrita bloqueia métodos mutáveis |
| Logs e rastreabilidade | JSON com UTC/request ID/template da rota/status/duração; sem querystring, corpo, cookies ou texto privado de erro; request ID também em auditoria e triggers |
| Métricas/alertas | Contadores, duração, uptime e espaço livre; TLS/Bearer em listener privado; quatro regras com teste de disparo |
| Auditoria | UI e API com permissão dedicada, tenant/empresa, cursor por ID e máximo de 100 linhas; detalhes privados fora da projeção |
| UI | Assets locais, CSP sem CDN, foco visível, labels e regiões focáveis, navegação móvel com Escape e uso da largura disponível |
| Backup/restore | Script recusa escritores ativos e destinos preenchidos; pg_dump custom, restore transacional, comparação de tabelas/sequências/arquivos, ACL e ownership |
| Rollback | Aplicação anterior executada sobre cópia restaurada; migration ida/volta com vendas; downgrade recusado se perderia request IDs |
| Operação | Runbooks de instalação, deploy, incidente, backup, restore, rollback, retenção e limites de custódia |

Inventário: **165 rotas**. Migration nova `a0d1e2f3a4b5`, sobre `9c0d1e2f3a4b`, acrescenta
`audit_logs.request_id`, índice `(tenant_id, empresa_id, id)` e permissão `visualizar_auditoria`.
Não há novas tabelas de aplicação: permanecem **47**, mais `alembic_version`.
O histórico passa a **27 revisions**. Nenhuma migration histórica foi reescrita.

## Achados e correções

| Identificador | Origem da evidência | Correção / verificação |
|---|---|---|
| S06-01: ausência de contrato operacional de storage | Inspeção da base; testes novos e falha real de permissão na entrega | Volume persistente, sonda de escrita, 503 antes de métodos mutáveis e recuperação efetivamente testada |
| S06-02: confiança global em cabeçalhos de proxy | Inspeção da base; ataques HTTP novos | Confiança pelo IP de conexão; proxy real com certificado validado aceita tráfego, conexão direta com headers forjados retorna 403 |
| S06-03: módulos não homologados expostos em produção | Inspeção de rotas/templates e testes autenticados novos | Bloqueio antes do controlador, ocultação de links e remoção do pagamento Boleto; transportes reais continuam proibidos |
| S06-04: aplicação podia modificar suas fontes | Inspeção do Dockerfile; execução nonroot/readonly | Código pertence a root, somente instance é gravável; papel de banco restrito recusa DDL, TRUNCATE e exclusão de auditoria |
| S06-05: lacunas de consulta e rastreabilidade | Inspeção e ataques de escopo/paginação/revogação | Auditoria consultável com permissão, projeção privada e request ID persistido; perda no downgrade recusada |
| S06-06: telas móveis bloqueadas e campos sem nome | Axe e Chromium reproduziram erros; screenshots revelaram também margem lateral residual | Removido bloqueio, adicionados labels/foco; largura útil e menu/Escape passaram a ser assertions |
| S06-07: erros de configuração durante o endurecimento | Falhas reais nos runners operacionais 1–3 | Strings tmpfs com vírgulas passaram a ser citadas; pool de IPs separado do IP fixo do proxy; todos os temporários nginx passaram a /tmp |
| S06-08: restore sem proteção suficiente contra uso incorreto | Ataques ao script da entrega | Aplicação ativa, dump adulterado e banco preenchido são recusados; diretórios de verificação privados e links recusados |
| S06-09: container parado mantinha volume após rollback | Conferência final de recursos, depois de a prova funcional passar | Container de rollback passa a usar --rm e label de serviço; runner exige zero containers/redes/volumes; prova operacional repetida em `ops-clean/` |

As inspeções de código não são apresentadas como testes executados contra uma imagem antiga.
Os casos marcados como reprodução em execução têm logs preservados. Nenhum teste anterior foi
removido, convertido em skip/xfail ou teve sua exigência reduzida para aprovar a entrega.

## Gates integrais e medição

As execuções finais aprovadas são **`release/`** (regressão integral) e **`ops-clean/`**
(prova operacional completa com limpeza verificada). As demais rodadas são apenas histórico
de diagnóstico e não fundamentam os gates finais.

| Gate | Resultado |
|---|---|
| Regressão completa | **578 aprovados**, 0 falhas, 0 erros, 0 skips; **1.049,931 s (17m29s)** |
| Preservação da base | Os mesmos **547 identificadores anteriores** permanecem; 31 casos acrescentados |
| Cobertura de linhas | 8.938 / 11.649 = **76,73%** |
| Cobertura de ramos | 1.556 / 2.638 = **58,98%** |
| Cobertura combinada | 10.494 / 14.287 = **73,45%**, gate original de 50% preservado |
| Migrations / schema | 27 revisions; upgrade individual, downgrade base e reupgrade; 47 tabelas de aplicação, metadata compatível |
| Chromium | 12 casos de navegador; cinco telas com Axe e viewport móvel, mais venda móvel com replay/cancelamento/reimpressão |
| Imagem de produção | Default production, nonroot, pip check, quatro segredos obrigatórios recusados antes de conectar ao banco |
| Smoke | Entrypoint, migrations, Gunicorn, health/readiness e headers aprovados |
| Banco desligado | Health 200, readiness 503, login falha fechado sem cookie de autenticação |
| Storage sem escrita | Health 200, readiness 503, métodos mutáveis 503; recuperação efetivamente verificada |
| Auditoria / benchmark | 10.000 eventos, 50 retornados, **14 consultas** (limite 30), **0,1102 s** (limite 2 s) |
| Plano SQL | Index Scan em `audit_logs_pkey`, execução SQL de **0,029 ms**; índice composto existe e schema foi comparado, sem forçar escolha do planner |
| Alertas | Promtool: SUCCESS nas quatro regras com dados temporais sintéticos |
| Limpeza final | Zero containers, redes e volumes da Sprint 6; os três serviços preexistentes permanecem |

O benchmark mede uma requisição e essa distribuição sintética. Não é p95, throughput, carga
concorrente ou prova de uso do índice composto em toda distribuição de tenants.

Artefatos: [JUnit](sprint-06-execucao/release/junit.xml),
[cobertura](sprint-06-execucao/release/coverage.xml),
[pipeline](sprint-06-execucao/release/pipeline.txt),
[resumo conferido](sprint-06-execucao/acceptance-summary.json),
[benchmark/EXPLAIN](sprint-06-execucao/release/benchmark.json),
[venda móvel](sprint-06-execucao/release/e2e/test_mobile_sale_retry_and_reversal/screen.png) e
[limpeza completa](sprint-06-execucao/cleanup-final.txt).

Python 3.12.12, PostgreSQL 16.12, Flask 3.0.3, SQLAlchemy 2.0.52, Alembic 1.19.2,
psycopg2-binary 2.9.9 e Gunicorn 21.2.0. Versões registradas em `versions.json` e
`postgresql-version.txt`, dentro da pasta de evidências.

## Provas operacionais executadas

O runner `validate_operational_proof.ps1`, projeto `oceanblue-s06-ops-clean`, criou uma base
sintética com **três vendas, três lançamentos, total de R$ 60,00 e estoque restante 94**, mais
um arquivo de recibo no volume persistente. A aplicação foi parada antes do snapshot.

O snapshot comparou **48 tabelas incluindo alembic_version e 44 sequências**. A restauração
ocorreu em outro PostgreSQL inicialmente vazio e outro volume. Contagens e hashes de conteúdo
de todas as tabelas/sequências coincidiram; dump e arquivo foram conferidos por SHA-256.
Os fingerprints de tabelas usam MD5 de representações JSON ordenadas como teste de igualdade;
a integridade do artefato completo usa SHA-256 e depende da custódia do manifesto.

- Dump: `98c3ff7b979091e3ffe431ab259a6a98b8ca696acb2f7d65f8d5c86fd66420a1`.
- Arquivo: `5d3d8ada1aec31e045f7f403923f87cf862009f1642a212f904ad1d99dee9b0b`.
- Manifesto do snapshot: `dd99ae68cce2919a5f7727222d3d317c33d6899f523eabc9f9768b65303d1a57`.

O smoke da aplicação restaurada passou e o arquivo continuou conferido. A prova retirou
permissão de escrita de fato, observou health 200/readiness 503/escrita 503 e restaurou o
funcionamento. O script recusou backup com aplicação ativa, restore de dump adulterado e
restore sobre banco preenchido antes de qualquer sobrescrita desses destinos.

O digest anterior `sha256:896e64670d1cf36bd15ae5b97784fed1ff564de6b98cbeaadaca9d8fa74529b1`
foi iniciado com Gunicorn diretamente, sem executar migrations antigas, sobre a cópia restaurada.
Health/readiness e contagens das três vendas/lançamentos passaram. A prova demonstra
compatibilidade de processo e dados para esse par de versões; não autoriza reabrir produção
com uma imagem que não tenha os novos controles de endurecimento. O runbook exige conferir
todos os gates antes de liberar tráfego e prioriza correção para frente quando necessário.

Em seguida, a migration nova foi revertida e reaplicada, mantendo contagem e soma das vendas.
Esse cenário não tinha request IDs gravados. O teste de integração separado grava um request ID,
tenta downgrade, exige recusa e confere que a revision permaneceu no head. Portanto, não se
alega rollback destrutivo de dados de auditoria nem recuperação de escritas posteriores ao backup.

Nginx real recebeu certificado sintético, validado pelo cliente TLS. Proxy confiável retornou 200;
HTTP direto com headers forjados retornou 403. O listener público recusou métricas e módulos
bloqueados; o listener interno exigiu Bearer token. A imagem executou com fonte não gravável,
UID 1000 e filesystem somente leitura. Promtool disparou as quatro regras de alerta esperadas.

Artefatos: [resumo](sprint-06-execucao/ops-clean/summary.json),
[backup](sprint-06-execucao/ops-clean/backup.txt),
[restore](sprint-06-execucao/ops-clean/restore.txt),
[rollback de aplicação](sprint-06-execucao/ops-clean/rollback-smoke.txt),
[migration com dados](sprint-06-execucao/ops-clean/migration-downgrade.txt),
[TLS](sprint-06-execucao/ops-clean/https.txt),
[limpeza operacional](sprint-06-execucao/ops-clean/cleanup-check.txt) e
[alertas](sprint-06-execucao/alerts-test.txt).

## Iterações preservadas

- `iteration/operations.*`: 20 aprovados e uma expectativa de teste incorreta; Flask-Migrate
  converte RuntimeError em SystemExit. A assertion foi ajustada para exigir exit 1 e schema intacto.
- `iteration/e2e.txt`: 23 aprovados e erro Axe no nome do seletor de empresa do PDV.
- `iteration/mobile.*`: quatro aprovados e duas falhas de acessibilidade em financeiro/estoque.
- `iteration/preflight.*`: 29 aprovados. Screenshots permitiram identificar a margem móvel residual.
- `iteration/mobile-final.*`: **31 aprovados**, após a correção visual e os testes de schema/UI.
- `operational/`, `operational2/`, `operational3/`: falhas de configuração reproduzidas e corrigidas.
- `operational4/`: primeira prova integral efetiva de backup/restore/rollback e TLS com dados.
- `ops-accept/`: prova acrescentando recusa de aplicação ativa, corrupção e destino preenchido.
- `final/` e `accept/`: regressões interrompidas intencionalmente para incorporar correções
  encontradas nas provas paralelas e inspeção visual. Não são contabilizadas como regressões aprovadas.
- `ops-release/`: prova funcional aprovada, mas a conferência posterior encontrou o resíduo
  parado de rollback; substituída por `ops-clean/` para o aceite operacional final.
- `release/`: regressão integral aprovada usada no aceite final.
- `ops-clean/`: repetição integral da prova operacional após corrigir a remoção do container
  de rollback; `cleanup-check.txt` confirma ausência de containers, redes e volumes dos dois projetos.

## Fechamento de imagens e CI

A regressão integral usou imagens de teste
`sha256:4dc1d11e76e2766ff1c94c6b9b43ae4f17515730047c96e635bb17456d1b0da9`
e produção `sha256:b603f392544a1e3c8b9942e0c81ffd408e94b1fb18da4da90b3a6ecb65fcb8a5`.
Os **303 arquivos** dos manifestos foram conferidos byte a byte com as fontes dessa rodada.

Depois da regressão, houve somente ajustes em ferramentas de host: limpeza do runner operacional,
gate estático do workflow no runner integral, novo validador YAML e configuração do CI. A limpeza
foi reexecutada integralmente e o YAML foi validado. **Aplicação, testes Python/Chromium, migrations
e assets não mudaram**, o que foi conferido por hashes antes de reconstruir a entrega.

Imagens finais de entrega: teste
`sha256:0e93bf35b7a44c0525d1ae30c9d0b2cf137e0739efe7ad1ddbf36ebccc480429`;
produção `sha256:a65e4e58799e86743147c539cedf935aecb3aecbb2552e212a6af37bf08a31d7`.
Os **304 arquivos** atuais coincidem com essas imagens. Os únicos deltas de fontes em relação à
regressão estão enumerados nos manifestos: `validate_operational_proof.ps1`, `validate_sprint06.ps1`
e `validate_workflow.cjs`. A alteração de workflow tem SHA próprio na prova estática.
Não se apresenta a imagem final reconstruída como o mesmo digest da imagem usada no pytest.
Provas: [teste](sprint-06-execucao/complete-test-check.json),
[produção](sprint-06-execucao/complete-smoke-check.json) e
[imagens finais](sprint-06-execucao/complete-images.txt).

O workflow foi renomeado de `Sprint 1 verification` para **`OceanBlue verification`**, e o timeout
subiu de **15 para 30 minutos**. Os 17m29s medidos excediam o limite antigo; a nova margem acomoda
build, migrations e coleta, sem remover testes nem reduzir cobertura. A prova estática usa parser
YAML e exige timeout mínimo, suíte integral, migrations, cobertura de ramos/gate de 50%, coleta e
limpeza com `always()`. Roda no próprio workflow e no runner local. O artefato remoto passou a
`oceanblue-verification-evidence`. **Nenhuma execução remota foi disparada**, conforme a proibição
de push/deploy. Prova local: [workflow.json](sprint-06-execucao/workflow.json).
O [controle negativo](sprint-06-execucao/workflow-rejects-15.txt) substituiu o timeout apenas na
leitura do processo de teste e confirmou recusa de 15 minutos, sem alterar o arquivo real.

## Reproduzir

```powershell
npm ci --ignore-scripts
node scripts/validate_workflow.cjs
pwsh -NoProfile -File scripts/validate_sprint06.ps1 -Project oceanblue-s06-release -EvidenceDirectory docs/evidencias/producao/sprint-06-execucao/release
pwsh -NoProfile -File scripts/validate_operational_proof.ps1 -Project oceanblue-s06-ops-clean -ImagePrefix oceanblue-s06-release -EvidenceDirectory docs/evidencias/producao/sprint-06-execucao/ops-clean
docker run --rm --network none --mount "type=bind,source=${PWD}/infra/production,target=/rules,readonly" -w /rules --entrypoint promtool prom/prometheus@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996 test rules alerts.test.yml
```

Use nomes de projeto e diretórios novos em uma reprodução; os runners recusam sobrescrever
evidências. O build canônico de teste/produção foi usado, com camadas de dependências disponíveis
no cache Docker. Não se apresenta essa execução como instalação fria de todas as dependências.
Os locks Python e as bases Python/PostgreSQL da main foram preservados. Axe 4.10.3 foi acrescentado
como ferramenta de desenvolvimento, com lock e cópia local; npm audit não encontrou vulnerabilidades
nesse conjunto durante a instalação. Isso não constitui varredura completa de CVEs das imagens.

## Limites operacionais

O aceite é para homologação local e para a próxima validação independente. Não é deploy,
certificação fiscal/bancária, teste de carga produtiva, garantia de durabilidade física ou SLA.
Não houve chamada a Asaas/Focus/SEFAZ, SMTP, WhatsApp ou outro provedor de negócio.

O benchmark de auditoria tem amostra e limites explícitos; não generaliza throughput dos demais
módulos. Axe e Chromium cobrem cinco telas em 390×844 e um fluxo completo móvel; não certificam
todos os leitores de tela, navegadores ou estados de todos os modais. A CSP ainda contém
unsafe-inline por scripts legados, sem dependência crítica de CDN.

Métricas são locais ao único worker com quatro threads; múltiplos workers exigem agregação.
Regras de alerta foram avaliadas, mas coletor e canal de notificação produtivos não foram instalados.
Agendamento, criptografia/imutabilidade externa de backups, custódia de chaves, renovação de TLS,
retenção jurídica e expurgo de históricos dependem da instalação operacional descrita no runbook.
Backups e pastas de verificação de produção não devem ficar no Git. Os artefatos deste relatório
são sintéticos. Nenhum procedimento promete reconstruir escritas posteriores ao backup sem replay
previamente preparado e testado. O caos independente final da Sprint 6 fica para a tarefa seguinte.

Hashes dos artefatos: [sha256sums.txt](sprint-06-execucao/sha256sums.txt).
O SHA do único commit local é informado ao concluir, evitando autorreferência circular.
