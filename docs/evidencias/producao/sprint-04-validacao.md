# Sprint 4 — validacao destrutiva independente

Data: 2026-09-07, America/Sao_Paulo. Evidencias exclusivamente locais.

## Decisao

**GO para a Sprint 4 no escopo local validado. Zero falhas criticas ou altas conhecidas abertas.** Tres defeitos corrigidos, 48 regressoes novas e **413 testes aprovados em duas execucoes completas**, ambas sem falhas, erros ou skips. Este GO nao autoriza deploy nem integracoes externas.

| Gate final | Resultado observado |
|---|---|
| Dependencias/inventario | `pip check` em teste e producao; 149 rotas conferidas |
| Migrations/schema | 24 revisions, head `7a8b9c0d1e2f`, upgrade individual/downgrade base/reupgrade e sentinelas; 47 tabelas compativeis |
| Primeira regressao | 413 aprovados, 0 falhas/erros/skips; JUnit 799,027 segundos |
| Segunda regressao | 413 aprovados, 0 falhas/erros/skips; JUnit 785,836 segundos |
| Cobertura nas duas | 8.074/10.957 linhas e 1.380/2.472 ramos; combinado 9.454/13.429 = **70,40%**; gate de 50% preservado |
| E2E nas duas | Quatro cenarios por execucao, Chromium 140.0.7339.16 e Playwright 1.55.0; zero erros JavaScript e requisicoes externas |
| Imagem produtiva | UID 1000, default production, quatro variaveis obrigatorias ausentes recusadas antes de conectar ao banco |
| Smoke | Entrypoint/migrations/Gunicorn; health/readiness 200 e proxy forjado 403 |
| Banco interrompido | Health 200, readiness 503 e login falha fechado sem emitir sessao |
| Correspondencia de fontes | **260 arquivos identicos byte a byte**, tanto na primeira imagem quanto na final; fontes executaveis nao mudaram depois dos builds |
| Limpeza | Nenhum container ou rede dos dois projetos permanece; auxiliar de inventario removido; servicos preexistentes preservados |

Imagem final de teste: `sha256:97b1f05db4b2f81026ff091ccc5def9d4ecb08ae5cade1ecd214159db4974915`. Imagem de producao: `sha256:60f614eded6a8adf1e5a273a8115e6827a4bb74be00c60a8a6e0f280c71e842f`.

## Base e isolamento

Worktree inicialmente limpo e destacado em `352a77c`; sincronizado por fast-forward exclusivamente com a **main local `ef81ccbb0d7f16b12092332ac2d1a9867c4264a3`**. Confirmada a presenca e lido `sprint-04-execucao.md`, alem dos GOs independentes das Sprints 1, 2 e 3. Nenhum fetch ou consulta remota foi usado como evidencia desta validacao.

Projetos exclusivos `oceanblue-s04-attack` e `oceanblue-s04-validation-final`, PostgreSQL **16.12 real**, banco `oceanblue_test` em tmpfs, redes internas e sem portas publicadas ou mounts do checkout. O container auxiliar `oceanblue-s04-inventory` apenas regenerou o inventario, com rede desabilitada. Dados e credenciais sao sinteticos. Os containers preexistentes `blueocean_api`, `blueocean_db`, `wnr_triagem_api` e `wnr_triagem_db` foram preservados.

Nenhum push, integracao de entrega, deploy, CI remoto ou integracao real de boleto, Nota Fiscal ou WhatsApp. O transporte SMTP foi substituido nos cenarios de envio; HTTP, Gunicorn, Chromium, sessoes concorrentes e PostgreSQL foram reais. A rede interna e o bloqueio de conexoes dos testes impedem contato com provedores externos.

## Defeitos reproduzidos e corrigidos

| ID | Severidade | Antes, reproduzido nesta tarefa | Correcao e prova |
|---|---|---|---|
| VAL04-01 | Media | Recusa de TLS ou destino fora da allowlist ocorria antes de qualquer transporte, mas deixava o alerta `INCERTO`, bloqueando retentativa mesmo depois da correcao da configuracao. | Excecao especifica `PreDeliveryError`, ainda derivada de `PermissionError`, identifica essas recusas anteriores ao transporte. Ficam `FALHOU` e podem ser retentadas; timeout, desconexao e perda da confirmacao continuam `INCERTO`. Dois testes falharam antes e passaram depois. |
| VAL04-02 | Media | No Chromium, carrinho com 0,10 + 0,70 exibia subtotal 0,80, mas a soma binaria ficava abaixo do minimo 0,80 do cupom. A UI cobrava 0,80 enquanto o servidor aplicava o desconto e esperava 0,72. | Subtotal calculado em centavos inteiros nos resumos, base do cashback e confirmacao. E2E realiza a venda com 0,01 em dinheiro e 0,71 em Pix; pagamentos, financeiro e baixa dos dois produtos conferidos diretamente no PostgreSQL. |
| VAL04-03 | Alta | Identificadores fracionados eram truncados por `int()`, e `true` virava 1. Empresa, produto, cliente e forma de pagamento podiam ser associados a um registro diferente do identificador enviado; oito ataques persistiram vendas em vez de recusar o payload. | Conversao estrita para inteiro positivo, reutilizando a regra de quantidade. Oito regressoes exigem rejeicao e snapshot identico de todas as tabelas. Identificadores validos continuam exercitados pelos testes HTTP e E2E. |

Nenhuma migration adicional foi necessaria: as correcoes alteram validacao de entrada, calculo no navegador e classificacao de falha anterior ao transporte. As constraints e os gates anteriores continuam habilitados.

## Matriz de ataques e invariantes

| Area | Provas executaveis |
|---|---|
| Ultimo estoque, precos e linhas repetidas | Tres sessoes PostgreSQL disputam o ultimo saldo em varejo, automatico abaixo/no limite e atacado no limite, com linhas repetidas. Uma vencedora, nenhuma baixa excedente; cancelamento integral restaura o saldo e zera o financeiro liquido. Casos anteriores preservam rejeicao abaixo do minimo e adulteracao do preco. |
| Centavos, pagamentos e descontos | Novo E2E do minimo 0,80; regressoes anteriores de HALF_UP, pagamento que arredonda para zero, somas divergentes, NaN/infinitos, limite monetario, desconto quase total e rateios de devolucao. Permissoes de desconto e seus limites continuam verificados pela API. |
| Cupons | Periodo inclusivo no calendario brasileiro, cupom expirado sem efeitos, cliente/empresa/subtotal/teto, ultimo uso global e por cliente concorrentes, uso oculto em outra empresa, rollback sem consumo e preservacao de uso historico apos cancelamento. Criacao/edicao/exclusao HTTP sem CSRF e com permissao revogada recusadas. |
| Falhas entre venda, estoque, financeiro, cashback e fila | Novo cenario combina cupom de uso unico, cashback e alerta de ruptura. Falha apos INSERT real, parametrizada em nove fronteiras: venda, item, pagamento, estoque, financeiro, credito de cashback, movimento da carteira, entrega de alerta e idempotencia. Snapshot de todas as tabelas identico ao anterior, nenhum envio e retry com uma unica venda. Replay posterior conserva o snapshot. |
| Replay e payload divergente | Mesma chave com desconto, modalidade, cupom ou cashback alterados e rejeitada sem mudancas em nenhuma tabela. Suite anterior cobre concorrencia da mesma chave, autorizacao revalidada e replay de cancelamento. |
| Cancelamento e reimpressao | Casos existentes de devolucao parcial/integral, concorrencia entre ambas, rollback em cada etapa, estorno repartido por origem, credito usado/gerado, cancelamento integral apos parcial e leituras repetidas sem efeitos. Dois E2E anteriores preservados, com e sem cashback, incluindo resposta de venda perdida e reimpressao real. |
| Workers e crash | Falhas abruptas nas fronteiras de claim, antes/depois do transporte e commit da confirmacao, descartando a sessao e relendo o estado persistido. Tres casos adicionais encerram um processo Python real com `os._exit(73)`: antes do commit fica PENDENTE e recuperavel; depois do claim fica INCERTO, inclusive com marcador local de aceite do transporte sintetico, sem reenvio. Bloqueios sao liberados pelo PostgreSQL. |
| Rejeicao e ambiguidade SMTP | Destinatario/DATA recusados ficam FALHOU; desconexao e timeout ficam INCERTO; erros privados nao aparecem no historico. Reprocessamento comum nao duplica tentativa. Quatro retries concorrentes e falha isolada por destinatario continuam cobertos na suite anterior. |
| Resumo e historico | Quatorze produtos, incluindo treze em ruptura: a lista visual fica em doze, mas o resumo persiste treze rupturas e um estoque baixo. Uma entrega por destinatario/dia, repeticao sem efeitos, novo dia gera novo resumo. Teste anterior disputa a rotina com tres workers. |
| Tenant, empresa, permissoes e CSRF | Revogacao de acesso global a empresas ou de gerenciar alertas impede retentativa, sem incrementar tentativas. Cobertura anterior preserva tenant estrangeiro, configuracao, historico, escritas sem CSRF e bloqueio de WhatsApp. |
| Navegador sem CDN | Quatro E2E Chromium contra Gunicorn com dois workers e PostgreSQL: venda/cancelamentos/reimpressao com e sem cashback; cadastro de cupom/historico/retentativa; minimo de cupom com centavos e pagamento repartido. Toda requisicao externa e recusada e contabilizada pelo fixture. |

Os **48 novos casos** estao em `tests/test_sprint04_adversarial.py` (47) e `tests/test_sprint04_browser_adversarial.py` (1), com processo auxiliar em `tests/alert_worker_probe.py`. Nenhum teste anterior foi removido, desabilitado ou convertido em skip/xfail. O inventario das 149 rotas foi regenerado, preservando sua ressalva de que vinculo estatico nao equivale a cobertura HTTP.

## Antes, retestes e artefatos

Todos os links desta secao apontam para [sprint-04-validacao/](sprint-04-validacao/).

- `before.txt`/`before.xml`: **2 falhas e 33 aprovados**, expondo a classificacao incorreta anterior ao transporte.
- `browser-before.txt`/`browser-fixture-before.xml`: falha na fixture inicial, que criava varejo de 0,70 com atacado padrao de 8,00. Corrigido o dado sintetico; nao foi contado como defeito do aplicativo.
- `retest.txt`/`retest.xml` e `e2e-before/`: **35 aprovados e 1 falha**, reproduzindo no Chromium o minimo de cupom exibido como 0,80 mas recusado na comparacao binaria.
- `identifiers-before.txt`/`identifiers-before.xml`: **8 falhas**, demonstrando truncamento/aceite de booleanos nos quatro identificadores.
- `fixes.txt`/`fixes.xml` e `e2e-retest/`: **44 aprovados**, incluindo os tres defeitos corrigidos e venda real de 0,72. Screenshot do resultado inspecionado visualmente.
- `extra.txt`/`extra.xml`: **4 aprovados**, com encerramentos reais de processo e resumo acima do limite visual.
- `regression.txt`/`regression.xml`, `coverage-regression.xml` e `e2e-regression/`: primeira regressao completa, no projeto de ataque. `source-regression.json`/`source-regression-check.txt` conferem os 260 arquivos da imagem.
- `final/`: segunda regressao completa em banco novo; build, migrations, JUnit, cobertura, imagens, correspondencia de fontes, E2E, smoke e limpeza.
- `environment.txt`, `cleanup-attack.txt`, `cleanup-check.txt` e `sha256sums.txt`: isolamento, limpeza e integridade dos artefatos. O Compose emitiu mensagens de erro ao tentar parar alguns containers de testes ja encerrados; a remocao subsequente e a ausencia de recursos foram conferidas. Os erros SQL esperados dos ataques aparecem nos logs; a decisao final considera as assertions e os resultados JUnit.

## Reproducao

Em checkout desta entrega, com Docker Linux e PowerShell 7, execute com nome de projeto livre e pasta de evidencias nova:

```powershell
pwsh -NoProfile -File scripts/validate_sprint04.ps1 -Project oceanblue-s04-independent-repro -EvidenceDirectory docs/evidencias/producao/sprint-04-repro
```

O runner constroi imagens, confere dependencias/inventario, percorre migrations, executa toda a suite, coleta traces/screenshots, compara hashes de fontes, verifica a imagem produtiva e o smoke, interrompe seu PostgreSQL para testar indisponibilidade e remove seus recursos em `finally`. O novo parametro evita sobrescrever as evidencias anteriores de execucao. Para repetir a regressao e todos os gates, use outro nome de projeto livre e outra pasta de evidencias.

## Limites do aceite

O navegador verificado e o Chromium empacotado no Playwright do projeto; nao foi inferida compatibilidade com Firefox, WebKit ou outras versoes. A aplicacao funciona com recursos locais nos E2E. SMTP externo, carga produtiva, entrega na caixa final e scheduling produtivo permanecem fora deste aceite. INCERTO requer conciliacao operacional: nao se promete exactly-once nem retentativa automatica de envio ambiguo. Nenhum provedor foi homologado, e os simuladores de boleto/Nota Fiscal nao foram convertidos em integracoes reais.

Este documento nao autoriza push, merge, deploy ou ativacao de integracoes externas. O commit local final e informado no encerramento da tarefa, sem auto-referencia circular neste arquivo.
