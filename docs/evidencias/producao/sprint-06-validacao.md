# Sprint 6 — validação independente e destrutiva

Data: 2026-09-07, America/Sao_Paulo. Base sincronizada por fast-forward com
`main`, commit `804256ae6edafb4a2db99dcdb39ddacb987f9148`. O GO de execução foi
lido antes dos ataques. Dados, credenciais e certificados usados são sintéticos.

## Decisão

**GO para homologação local da Sprint 6 corrigida. Não autoriza deploy produtivo.**
As duas regressões integrais passaram, assim como restore, rollback, smokes e falhas
operacionais. Fontes das imagens conferidas e recursos descartáveis removidos.
Os limites de operação, segurança, carga e recuperação estão explicitados abaixo.

## Isolamento e método

Os recursos novos usam nomes `oceanblue-s06-*` exclusivos desta validação, redes
internas ou `--network none`, sem portas publicadas. PostgreSQL 16 real em todas
as provas de persistência. As duas regressões têm bancos e redes separados, com
PostgreSQL em tmpfs conforme o Compose oficial de testes. As provas de parada/retorno
e restore usam volumes persistentes descartáveis próprios. As regressões
compartilham somente o host Docker e as fontes congeladas. Há sobreposição temporal
entre elas, portanto suas medições incluem concorrência pelos recursos do host.

Os três serviços preexistentes foram preservados. Nenhuma chamada a Boleto,
Nota Fiscal, WhatsApp, SMTP ou outro provedor de negócio foi realizada. As fixtures
recusam sockets externos; o navegador permite somente o servidor local de teste.
Downloads de ferramentas/imagens durante preparação não são integrações de negócio.

Testes novos foram executados contra o código anterior antes de corrigir defeitos.
Falhas do produto e problemas dos próprios runners estão separados neste relatório.
Não foram removidos testes antigos, introduzidos skips/xfails ou reduzido o gate de
cobertura. O teste antigo do link de salto foi fortalecido para exigir foco no conteúdo
principal, em vez do contêiner que também continha o cabeçalho.

## Defeitos encontrados e corrigidos

| ID | Reprodução e impacto | Correção e prova |
| --- | --- | --- |
| V06-01 | Proxy confiável com X-Forwarded-For loopback contornava HTTPS nas quatro sondas | Exceção baseada no IP real do transporte, GET/HEAD locais sem encaminhamento; ataques e TLS real |
| V06-02 | Campos JSON permitidos aceitavam senha, CPF, cartão, token, objetos e números não finitos; método HTTP arbitrário aparecia no log | Validação de evento/ID/método/status/duração e template de rota obtido do contexto; log permanece JSON sem texto privado |
| V06-03 | Requisição encerrada por hook anterior podia ter ID divergente no log e duração negativa | Inicialização coerente no encerramento; mesmo ID na resposta e no log |
| V06-04 | Authorization não ASCII causava erro em métricas; primeiras séries zeradas faltavam; sondas e negativas de métricas eram cacheáveis | Credenciais inválidas retornam 404, contadores existem desde zero e respostas usam no-store |
| V06-05 | Ausência completa de métricas/readiness não disparava as regras existentes | Duas regras de ausência; promtool prova desaparecimento, recuperação e cenário saudável |
| V06-06 | Erro de upstream nginx registrava URI com senha, CPF e cartão | Error log HTTP nativo descartado; access log JSON mantém ID/status/duração e erros globais de startup continuam em stderr |
| V06-07 | Filtros vazios/duplicados e inteiros não canônicos tinham comportamento ambíguo; ID máximo sumia da primeira página | Parsing explícito limitado e cursor exclusivo aplicado somente quando enviado; escopo continua vinculado ao JWT/permissões |
| V06-08 | Factories retornavam simuladores Boleto/Fiscal fora do ambiente de testes | Exigem ambiente de testes e flag exatamente True; adaptadores reais continuam bloqueados antes de rede/segredos |
| V06-09 | Sonda aceitava escrita parcial ou bytes corrompidos com contagem aparentemente correta | Confere tamanho, fsync e releitura no mesmo descritor; falha fechada e limpeza |
| V06-10 | Listar 25 vendas fazia 39 consultas, contra 15 para uma venda | Configurações empresariais carregadas em lote; 15 consultas tanto para uma quanto para 25 vendas |
| V06-11 | Foco escapava da lateral móvel, sumia nos breakpoints/restauração, menu de usuário não fechava pelo teclado; lateral excedia 320 px | Ciclo Tab/Shift+Tab, Escape/retorno de foco, estado acessível sincronizado e largura limitada ao viewport |
| V06-12 | Link de salto levava novamente à navegação | Foco em main e próximo Tab no primeiro campo operacional; red/green nas duas telas |
| V06-13 | Snapshot aceitava revisão/formato incorretos, objetos preexistentes, escritor de storage e junction na raiz; ordem JSON produzia falso negativo | Manifesto v2, compatibilidade de versão, digest externo obrigatório no restore, comparação por mapas, inventário de objetos e links/ancestrais, verificação de escritores |
| V06-14 | Restore confirmava banco antes de validar/copy de arquivos; falha deixava estado parcial aceito | Transação mantida até verificar banco e arquivos; rollback e limpeza conferidos; publicação de backup somente após validação |
| V06-15 | Destino de restore interrompido/ambíguo poderia ser servido | Marcador persistente de restore incompleto bloqueia readiness e mutações; remoção somente após reconciliação; health permanece disponível |

São grupos de causas, não uma contagem de vulnerabilidades por caso parametrizado.
Ataques a tenant, empresa, assinatura de cookie, revogação de acesso e adulteração
SQL de auditoria não demonstraram fuga entre tenants. O parsing corrigido tinha
falhas de contrato; isso não é apresentado como vazamento entre tenants.

## Controles negativos e retestes focais

- Segurança: **32 falhas / 17 aprovados** no red; **49/49** após correção e
  **104/104** na regressão focal ampliada. [Detalhes](sprint-06-validacao/security/README.md).
- Dados: **19 falhas / 68 aprovados** inicialmente; expansão e correções culminaram
  em **176/176**. Marcador acrescentado depois: red/green de **8 casos**, seguido de
  **79/79** storage/security. [Detalhes](sprint-06-validacao/data/README.md).
- Carga/consultas: **1 falha / 2 aprovados**; mesmos três casos passaram após corrigir
  N+1. Mais **2/2** provas de migration sob bloqueio real. [Red](sprint-06-validacao/load/initial.txt),
  [reteste](sprint-06-validacao/load/retest.txt), [migration](sprint-06-validacao/load/migration.txt).
- UI: red inicial teve **12 falhas de produto**, uma expectativa de transição CSS
  ajustada e um erro de setup Chromium. Skip-link teve **2/2 falhando** antes e
  **2/2 passando** depois. Conjunto final: **26/26 em 358,97 s**, sem erros/skips.
  [Histórico e screenshots](sprint-06-validacao/ui/README.md).
- Alertas: quatro expectativas de ausência falharam no red; seis regras passaram
  nos arquivos original e adversarial, incluindo resolução e controles saudáveis.
  [Red](sprint-06-validacao/alerts/red.txt), [green](sprint-06-validacao/alerts/green.txt).
- Proxy: TLS real com upstream recusando conexão produziu 502 e vazou **3 marcadores**
  no red; o mesmo ataque corrigido vazou **0**, preservando access log JSON.
  [Red](sprint-06-validacao/proxy/red3/result.json), [green](sprint-06-validacao/proxy/green/result.json).
- Snapshot: **22 casos**, sendo **12 falhas / 10 aprovados**, antes da correção.
  Fonte congelada: **32/32 casos e 3/3 provas suplementares aprovados**.
  [Resultados e limites](sprint-06-validacao/snapshot/README.md).

Os números focais se sobrepõem e não são somados como testes independentes.
Logs red podem conter os próprios marcadores privados sintéticos cuja fuga foi
provocada. Eles não são logs seguros da versão corrigida nem contêm dados reais.

## Regressões integrais

As duas rodadas passaram com **758 casos cada**, sem falhas, erros ou skips;
o conjunto preserva os **578 anteriores** e acrescenta **180 casos**:
49 de segurança, 106 de dados/storage/flags, 20 de navegador e 5 de carga/migrations.
Os identificadores foram comparados com distinção de maiúsculas/minúsculas:
nenhum teste ausente ou duplicado. [Conferência](sprint-06-validacao/test-preservation.json).

| Rodada | Aprovados | Tempo pytest | Cobertura combinada | Linhas | Ramos |
| --- | ---: | ---: | ---: | ---: | ---: |
| verify1 | 758/758 | 1.755,395 s | 73,94% | 77,07% | 60,22% |
| verify2 | 758/758 | 1.756,676 s | 73,94% | 77,07% | 60,22% |

Cada rodada cobriu 9.017/11.700 linhas e 1.609/2.672 ramos: cobertura combinada
de 10.626/14.372 pontos. Ambos os runners terminaram com código zero, incluindo
os gates posteriores ao pytest. Os manifestos das imagens de teste e smoke
conferiram **313 arquivos em cada imagem**, sem divergências.

Cada pipeline exige dependências íntegras, inventário atualizado, migrations do
zero revision por revision com sentinela de upgrade, downgrade base/reupgrade,
comparação de schema/metadata, pytest completo e cobertura de linhas/ramos.
Depois confere hashes das fontes das imagens, usuário, smoke, headers, storage,
indisponibilidade do banco e limpeza. Parada/retorno com preservação dos dados é
comprovada no runner operacional separado. O gate de cobertura original de 50% permanece.
As porcentagens medem o pacote Python `app`, com ramos habilitados. Não são cobertura
de PowerShell, nginx, SQL de migrations ou JavaScript; essas áreas têm provas próprias.

Evidências finais: [rodada 1](sprint-06-validacao/verify1/),
[rodada 2](sprint-06-validacao/verify2/),
[contagens e cobertura extraídas dos XMLs](sprint-06-validacao/regression-summary.json).

## Restore, rollback e falhas reais

A prova final `ops-final/` criou três vendas e três lançamentos, R$ 60,00 de total,
estoque 94 e recibo persistente. A aplicação ficou parada durante a captura.
O restore ocorreu em outro banco e volume vazios, com SHA-256 esperado do manifesto
preservado separadamente no momento da captura. Conferiu tabelas, sequências e
arquivos antes do commit e passou no smoke da aplicação restaurada.
São **48 tabelas incluindo alembic_version, 44 sequências e dois arquivos no
manifesto (dump e recibo)**. [Resumo conferido](sprint-06-validacao/ops-final/snapshot-summary.json).

**Backup: 23,190 s. Restore até smoke: 50,589 s. RPO observado: zero registros
capturados perdidos.** O tempo de restore começa imediatamente antes de chamar o
script e termina após startup/smoke; não inclui detectar incidente, provisionar o
destino ou reconciliar escritas posteriores. Não ocorreram escritas de negócio após
o snapshot. Esses valores não são SLA, RPO temporal contínuo ou prova de PITR/WAL.
[Medição](sprint-06-validacao/ops-final/recovery-measurements.json).

A prova independente do script, em base sintética menor e rede desabilitada,
mediu backup em **23,677 s**, restore em **24,929 s** e rollback após encerramento
forçado em **1,603 s**, mantendo o marcador de estado incompleto. Esses tempos
não incluem startup/readiness e não são comparáveis diretamente ao RTO operacional.

A imagem anterior da Sprint 5, digest
`sha256:896e64670d1cf36bd15ae5b97784fed1ff564de6b98cbeaadaca9d8fa74529b1`,
executou sobre a cópia restaurada sem rodar migrations antigas, preservando as três
vendas/lançamentos. Banco parado produziu health 200/readiness 503 e autenticação
falhando fechada; depois do retorno, o smoke passou. Migration da Sprint 6 foi
revertida e reaplicada com os totais preservados. Testes separados recusam downgrade
com request IDs e provam rollback transacional de upgrade/downgrade sob lock timeout.
Isso comprova somente esse par de versões e conjunto de dados.
O teste de compatibilidade não autoriza liberar tráfego com uma imagem anterior
sem os controles novos; o runbook exige repetir os gates e priorizar correção para
frente quando um downgrade perderia rastreabilidade.

- SIGKILL real do worker Gunicorn: processo substituído e readiness recuperado em
  **2,145 s**; não havia transação de negócio em voo nessa prova HTTP.
- Worker de entrega: regressões existentes encerram processo de verdade e conferem
  locks/estados duráveis sem duplicar transporte simulado; nenhum envio externo.
- ENOSPC real em tmpfs limitado a **1 MiB**: health 200, readiness e escrita 503;
  após remover o arquivo de preenchimento, readiness retornou em **0,0068 s**.
- Permissão de storage removida e restaurada, filesystem montado somente leitura,
  marcador de restore incompleto, corrupção de sentinela, links e traversal exercitados.
- Proxy parado ficou inacessível na borda, mantendo sondas internas; TLS voltou após
  reinício. Certificado sintético foi validado pelo cliente, não ignorado.
- Processo produtivo UID 1000, fonte não gravável, root filesystem somente leitura,
  capabilities removidas, no-new-privileges e diretórios temporários limitados.
- Quatro segredos obrigatórios ausentes foram recusados antes de conectar ao banco.

[Prova operacional](sprint-06-validacao/ops-final/),
[gates de imagem](sprint-06-validacao/image-gates.txt),
[estado nonroot/read-only/capabilities](sprint-06-validacao/container-hardening.json).
Os logs finais de aplicação/proxy e o ataque corrigido a upstream passaram na
[busca de marcadores secretos](sprint-06-validacao/final-log-scan.json), com zero ocorrências.

Os 313 arquivos do manifesto da imagem operacional foram comparados ao checkout:
aplicação, testes, migrations, assets, configuração do proxy, snapshot e probes são
idênticos. O único delta é `scripts/validate_sprint06.ps1`, ajustado depois para usar
o tmpfs oficial nas regressões. Essa ferramenta do host não executa dentro da prova
operacional. [Comparação explícita](sprint-06-validacao/ops-final/image-source-comparison.json).

## Carga e consultas críticas

O teste de auditoria faz 120 requisições WSGI autenticadas, oito leitores concorrentes,
20.000 eventos em dois tenants e páginas de 50, sem repetição de IDs entre páginas
de cada leitor. Não é carga HTTP através do proxy. Os arquivos `load.json` das
regressões registram p50/p95/máximo e throughput de cada rodada.

| Rodada | p50 | p95 | Máximo | Requisições/s | Erros |
| --- | ---: | ---: | ---: | ---: | ---: |
| verify1 | 1,398 s | 2,238 s | 2,398 s | 5,706 | 0 |
| verify2 | 1,411 s | 2,878 s | 3,289 s | 5,424 | 0 |

As 120 leituras levaram 21,029 s e 22,125 s, respectivamente, com as duas suítes
concorrendo no mesmo host de 12 CPUs e aproximadamente 3,67 GiB disponíveis ao
Docker. Não constituem SLA ou dimensionamento de produção.

Contenção de estoque usa 16 escritores contra 12 unidades: 12 vendas aprovadas,
quatro recusas por falta de estoque, saldo zero e ledger R$ 120,00. Os caminhos de
listagem foram comparados com uma e 25 linhas: vendas 15/15 consultas; financeiro
14/14; movimentos de estoque 14/14. Isso não prova ausência de N+1 em toda combinação
de relacionamentos, nem capacidade produtiva para bases arbitrariamente grandes.
O benchmark existente, com 10.000 eventos e retorno de 50, registrou 14 consultas
nas duas rodadas, em 0,133 s e 0,132 s. EXPLAIN ANALYZE utilizou `audit_logs_pkey`;
a escolha é observada, sem forçar o planner nem alegar uso do índice composto.

## Limites e problemas de preparação

- `final1/` parou antes do pytest porque os testes novos alteraram os vínculos do
  inventário estático. O CSV foi regenerado sem mudar as 165 rotas. Não conta como regressão.
- `ops-preflight/` mostrou que parar PostgreSQL em tmpfs apaga a base de teste.
  As provas operacionais de parada/retorno usam `compose.validation-database.yml`, com
  volumes novos exclusivos removidos ao terminar. `ops-preflight2/` passou, mas a
  prova de aceite é `ops-final/`, com marcador e fontes finais.
- `accept1/` e `accept2/` tentaram também executar toda a regressão em volumes de
  disco. O tempo passou a ser dominado por fsync dos resets de fixtures; foram
  interrompidas, sem contar como regressões aprovadas. `verify1/` e `verify2/` usam
  o tmpfs oficial da suíte. Nenhum teste foi removido para acelerar essas rodadas;
  as provas operacionais mantêm o armazenamento persistente.
- `proxy/red` e `proxy/red2` são erros do runner (resolução recursiva do helper e
  argumento tmpfs com vírgulas sem aspas); o red válido é `red3`. Não são defeitos nginx.
- O runner de teste usa init para recolher processos filhos do navegador, após
  erros de setup Chromium observados nas rodadas UI intermediárias.
- Depois de observar aproximadamente 29m16s somente no pytest, o timeout do workflow
  foi ampliado de 30 para 45 minutos. O YAML foi revalidado localmente; nenhum job
  remoto foi executado. Essa alteração de configuração de CI ocorreu depois das
  regressões e não altera aplicação, testes, migrations ou imagens exercitadas.
- Manifestos v1 não são aceitos pelo novo restore. O v2 exige digest vindo de custódia
  confiável. Um administrador que controle daemon, imagem, snapshot e digest pode
  ultrapassar esses controles; não há transação distribuída atômica DB/filesystem.
- Restore ambíguo conserva marcador e exige intervenção/reconciliação ou destino
  novo. Nunca se deve remover o marcador apenas para liberar readiness.
- A sonda verifica seu sentinela, não todos os documentos históricos ou durabilidade
  física. Backups não incluem roles/senhas/configuração do cluster; não há agendamento,
  criptografia externa, imutabilidade ou replicação instalados por esta tarefa.
- Alertas foram avaliados com séries temporais sintéticas; coletor e canal produtivos
  não foram instalados. Métricas são locais ao processo. Ausência é avaliada para uma
  instalação monitorada; múltiplas instâncias exigem rótulos e agregação adequados.
- Chromium/Axe cobrem as telas e fluxos exercitados, larguras 320–1440 px, teclado,
  foco e assets locais; não certificam todos os navegadores, leitores de tela ou
  aparelhos. Offline significa página carregada, erro anunciado e recuperação;
  não há início ou venda offline. CSP ainda permite unsafe-inline legado.
- Não houve push, deploy, execução remota de CI, certificação bancária/fiscal ou
  varredura completa de CVEs. O resultado é exclusivamente de homologação local.

## Reprodução e fechamento

[Limpeza final](sprint-06-validacao/cleanup-final.json): nenhum container, rede ou
volume `oceanblue-s06-*` restante; serviços alheios preservados. Imagens locais
ficam disponíveis para reprodução. [Versões](sprint-06-validacao/versions.json),
[aceite consolidado](sprint-06-validacao/acceptance.json) e
[manifesto SHA-256 dos artefatos](sprint-06-validacao/evidence-sha256.json)
permitem conferir ambiente, gates e integridade dos arquivos de evidência.
O manifesto exclui somente a si próprio; não é assinatura de custódia externa.

```powershell
npm ci --ignore-scripts
pwsh -NoProfile -File scripts/validate_sprint06.ps1 -Project oceanblue-s06-replay-one -EvidenceDirectory docs/evidencias/producao/s06-replay-one
pwsh -NoProfile -File scripts/validate_sprint06.ps1 -Project oceanblue-s06-replay-two -EvidenceDirectory docs/evidencias/producao/s06-replay-two
pwsh -NoProfile -File scripts/validate_operational_proof.ps1 -Project oceanblue-s06-replay-ops -ImagePrefix oceanblue-s06-replay-one -EvidenceDirectory docs/evidencias/producao/s06-replay-ops
pwsh -NoProfile -File scripts/validate_snapshot_adversarial.ps1 -Phase green -EvidenceDirectory docs/evidencias/producao/s06-replay-snapshot
pwsh -NoProfile -File scripts/validate_proxy_logs.ps1 -Project oceanblue-s06-proxy-log-replay -EvidenceDirectory docs/evidencias/producao/s06-replay-proxy
```

Use diretórios/nomes novos; não sobrescreva evidências. O README de cada frente
descreve reprodução dos controles negativos. O SHA do único commit local será
informado no encerramento, evitando autorreferência circular neste documento.
