# Sprint 7 — validação independente final

Data: 2026-09-08, America/Sao_Paulo. Versão avaliada: `2.1.0-rc.1`.

## Decisão

**GO técnico para o candidato local da Sprint 7.** O código e o pacote selado estão prontos
para entrega/revisão no escopo validado: duas suítes integrais consecutivas, PostgreSQL 16,
navegadores reais, segurança, carga, recuperação, rollback e assemble terminaram sem falhas,
erros ou skips. Não foi encontrado bloqueador P0/P1 dentro desse escopo.

**NO-GO para instalar ou publicar em produção.** Essa decisão exige o aceite do ambiente real,
incluindo scan de CVEs do sistema operacional/imagem, certificados e domínio definitivos,
segredos no cofre, durabilidade dos volumes, alertas, política de backup e capacidade. Nenhum
deploy, push ou contato com provedor externo foi realizado.

O checkout de validação começou exatamente em
`2163ed9d72babf5020118094ec50691f4400f3f9`. O único commit desta validação é o commit
que contém este relatório; seu pai deve resolver para esse SHA. O campo `base_commit` do
manifesto de release conserva a base histórica da Sprint 6 usada pelo ensaio de rollback e
não substitui essa prova de filiação Git.

## Método independente

- Leitura obrigatória de `sprint-07-execucao.md`, inventário, rotas, migrations, serviços,
  testes e documentação, sem assumir a conclusão anterior como evidência suficiente.
- Recursos descartáveis exclusivos sob o prefixo `oceanblue-s07-independent-rc2`, com
  PostgreSQL 16 real; integrações externas permaneceram desligadas.
- Banco novo, migrations completas, sentinela de upgrade, downgrade/reupgrade e comparação
  entre schema migrado e modelos em cada uma das duas rodadas integrais.
- Fluxos válidos e adversariais de autenticação, autorização, multitenancy, cadastros,
  estoque, PDV, financeiro, auditoria, importação/exportação, idempotência e rollback.
- Chromium, Firefox e WebKit em 320, 390, 768 e 1440 px conforme a matriz; Axe sem exclusões,
  teclado/foco, geometria, rolagem, JavaScript, HTTP, assets locais e bloqueio de externos.
- Falhas operacionais reais de worker, banco, proxy, storage cheio/somente leitura,
  backup/restore, adulteração, rollback, TLS, logs e alertas.
- Scan pós-congelamento dos locks, instalações por hash, SBOMs, advisories, licenças e Gitleaks.

## Resultado integral

Projeto aceito: `oceanblue-s07-independent-rc2`.

| Gate | Regressão | Reteste independente |
| --- | ---: | ---: |
| Casos | 868 | 868 |
| Anteriores preservados / novos | 758 / 110 | 758 / 110 |
| Falhas / erros / skips | 0 / 0 / 0 | 0 / 0 / 0 |
| Duração JUnit | 3.432,957 s | 3.166,911 s |
| Linhas | 9.401 / 11.700 | 9.401 / 11.700 |
| Ramos | 1.701 / 2.672 | 1.701 / 2.672 |
| Cobertura combinada | 77,2474% | 77,2474% |
| Casos de navegador Sprint 7 | 72 | 72 |

O [resumo integral](sprint-07-validacao/final-candidate/regression-summary.json), os
[resultados JUnit da regressão](sprint-07-validacao/final-candidate/regression/junit.xml)
e os [resultados JUnit do reteste](sprint-07-validacao/final-candidate/retest/junit.xml)
demonstram as contagens. A cobertura não soma recortes focais e supera o gate configurado.

O inventário final relaciona 165 rotas, 354 arquivos e 1.748 definições AST. Cada rodada
registrou 1.125 observações HTTP in-process; subprocessos de navegador possuem evidência
própria. A [rastreabilidade requisito–rota–serviço–teste](sprint-07-validacao/final-candidate/traceability.csv)
separa vínculo estático de requisições efetivamente observadas e não apresenta vínculo
estático como prova de execução completa.

## Segurança e dados

Os casos preservados e os 29 casos de auditoria da Sprint 7 cobriram isolamento por tenant e
empresa, autorização por função, CSRF, rate limit, trial, headers, IDs booleanos/fracionários,
IDs de outro registro, paginação, exposição de dados, transações, concorrência e idempotência.
Falhas forçadas não deixaram baixa de estoque, venda, lançamento ou auditoria parcial.

Os cenários válidos mantiveram reconciliação entre venda, estoque, financeiro e auditoria.
Em contenção, 16 vendas disputaram estoque 12 nas duas rodadas: 12 foram aceitas, quatro
recusadas sem estoque e o razão totalizou R$ 120,00, sem oversell ou duplicidade.

As flags de Boleto, Fiscal e provedores externos permaneceram `false`; os caminhos de
produção correspondentes continuaram inacessíveis. Nenhum segredo real foi necessário.

## Interface e jornadas

A matriz automatizada atravessou 25 telas nos três motores e nas larguras de celular,
tablet e desktop, além de 18 jornadas completas em 390/1440 px. Todos os checks de Axe,
foco, teclado, skip-link, cabeçalho fixo, overflow de documento, rolagem interna, assets,
erros JavaScript/HTTP e chamadas externas passaram nas duas rodadas.

Foram rechecadas explicitamente as regressões críticas:

- estoque em 768 px sem overflow nem conteúdo oculto;
- skip-link com o conteúdo abaixo do cabeçalho fixo e contraste preservado;
- botão de finalizar venda sem contraste transitório inválido;
- foco decimal preservando preço atacado de R$ 10,00 e mínimo 3;
- `Nova Role` nativamente desabilitado até o script estar pronto, seguido de CRUD,
  login restrito e toast de acesso negado.

Os 15 PNGs representativos da regressão aceita foram abertos e inspecionados novamente.
Não foi observado clipping, sobreposição ou perda de conteúdo; a tabela larga de auditoria
em celular usa sua rolagem horizontal interna intencional, sem overflow do documento.

## Desempenho

| Medição local | Regressão | Reteste |
| --- | ---: | ---: |
| Auditoria, 20.000 registros, 120 requests, concorrência 8 | p95 1,3892 s | p95 1,5855 s |
| Máximo observado | 1,4905 s | 2,2275 s |
| Erros | 0 | 0 |
| Benchmark paginado, 10.000 eventos / 50 retornados | 0,1050 s, 14 queries | 0,0959 s, 14 queries |

As consultas críticas permaneceram em 15/14/14 para vendas, lançamentos e movimentos,
independentemente de retornar um ou 25 registros. Essas medições são gates sintéticos locais,
não SLA nem dimensionamento produtivo.

## Operação e recuperação

O gate operacional terminou com código 0. Backup com escritores ativos foi recusado; após
quiescência, o backup levou 18,6204 s e o restore até smoke 30,3924 s. Três vendas e três
lançamentos capturados foram restaurados, com zero venda capturada perdida. Como não houve
escrita de negócio após o snapshot, isso não promete RPO zero produtivo.

O [snapshot adversarial](sprint-07-validacao/final-candidate/snapshot/summary.json) passou
32/32 casos com PostgreSQL 16 real, rede desabilitada e remoção dos recursos. Foram recusados
manifestos, hashes, revisão, versão, path traversal, custódia, destinos não vazios, links,
interrupções e falhas de cópia/rollback. O pacote operacional também recusou snapshot
adulterado e confirmou rollback pela imagem anterior reconstruída da base fixada.

A carga TLS → nginx → Gunicorn → PostgreSQL executou 120 requisições com concorrência 8,
zero erros, p95 0,4851 s e máximo 0,5202 s. A queda do proxy retornou 502 com log estruturado
e zero sentinela sintética vazada. Worker, banco, proxy e storage recuperaram; os dois arquivos
Promtool passaram; quatro inicializações sem segredos obrigatórios falharam antes de acessar
o banco. São provas locais com certificado sintético, não homologação do ambiente real.

## Cadeia de fornecimento

O [scan pós-congelamento](sprint-07-validacao/final-candidate/supply-chain/summary.json)
validou hashes dos locks e inventários exatos: 28 distribuições Python de produção, 41 de
desenvolvimento e 76 componentes npm. `pip check`, instalações por hash, SBOMs e npm audit
passaram; Python e npm retornaram zero advisories conhecidos no instante da consulta.

O Gitleaks aprovou o gate de runtime com dez fixtures sintéticas revisadas. As 20.667
detecções em evidências históricas continuam classificadas para revisão, não como credenciais
produtivas confirmadas nem como histórico certificado livre de segredos. A publicação desse
acervo exige revisão/redação própria. Metadados LGPL/Mozilla também exigem aceite jurídico.

Docker Scout 1.24.0 foi encontrado, mas exigiu autenticação. Nenhum relatório de CVEs do SO
foi produzido; portanto não se alega ausência de vulnerabilidades em Debian, CPython,
bibliotecas nativas ou navegadores. Esse é bloqueador explícito para instalação produtiva.

## Candidata rejeitada

Uma candidata anterior foi corretamente rejeitada: sua primeira integral passou 868/868,
mas o reteste terminou 864/868. Houve um estouro do orçamento de tempo da leitura concorrente
de auditoria e três timeouts de navegação, acompanhados por timeout/SIGKILL de worker e apenas
cerca de 653 MiB livres no host. As páginas afetadas tinham HTTP 200 e nenhum erro funcional,
JavaScript, HTTP, Axe ou externo registrado.

Os quatro mesmos node IDs passaram 4/4 em 104,026 s num PostgreSQL 16 novo, com os limites
originais. Esse diagnóstico sustentou saturação ambiental, mas **não** converteu o reteste em
aceite. Não houve retry automático, aumento de timeout, relaxamento de asserção ou alteração
de código/teste. A candidata final reiniciou toda a sequência e passou duas integrais. O
[resumo da rejeição](sprint-07-validacao/rejected-candidate/summary.json) e os traces preservados
mantêm a cadeia de decisão.

## Artefato e reprodução

O artefato final é `dist/oceanblue-2.1.0-rc.1.tar.gz`, com 5.418.303 bytes e SHA-256
`3aafe423cb3aafae30c1a72660a87fe033cb2b1b8d895fd495dde2b971ce00f4`. O
[manifesto](sprint-07-validacao/final-candidate/release-manifest.json) inventaria 812 membros;
o [inventário de evidências](sprint-07-validacao/final-candidate/evidence-sha256.json) valida
459 arquivos externos.

Após fechar as evidências, três regenerações consecutivas do arquivo foram idênticas byte a
byte. Cada membro e cada hash externo foram reverificados. O arquivo selado foi extraído em
diretório novo, reconstruído e executado sem rede e sem banco; o WSGI importou e `/api/health`
retornou 200 com a versão correta. A [prova de reprodutibilidade](sprint-07-validacao/package-reproducibility.json)
registra hashes, tamanho, contagens e identidade da imagem de smoke. Não se afirma build
Docker byte a byte por causa de camadas e metadados externos.

Reprodução integral, em projeto e diretório de evidência novos:

```powershell
pwsh -NoProfile -File scripts/validate_release_candidate.ps1 -Project oceanblue-s07-independent-replay -EvidenceDirectory docs/evidencias/producao/sprint-07-validacao-replay -Python python
```

Requisitos: Docker Linux, PowerShell 7, Python 3.12, Node, checkout que preserve bytes
(`git -c core.autocrlf=false`) e acesso aos registries/advisories durante o scan. O modo
integral exige projeto novo, coleta evidências mesmo em falha e remove recursos descartáveis.
Fases focais servem somente para diagnóstico e não substituem o gate.

## Riscos residuais priorizados

| Prioridade | Risco / ação obrigatória |
| --- | --- |
| P2 — bloqueia deploy | Autenticar um scanner e aprovar CVEs da imagem/SO final. |
| P2 — bloqueia deploy | Homologar TLS/domínio, cofre de segredos, volumes, alertas, backup e capacidade no ambiente real. |
| P2 — publicação | Revisar/redigir as 20.667 detecções históricas antes de distribuir o acervo de evidências. |
| P2 — jurídico | Aprovar obrigações LGPL/Mozilla e demais licenças da distribuição. |
| P3 — acessibilidade | Complementar Axe/teclado/geometria com leitores de tela e dispositivos físicos. |
| P3 — capacidade | Executar teste de capacidade e RPO/RTO no hardware, volume e concorrência produtivos. |

Nenhum item P0/P1 permanece no escopo técnico validado. Os P2 de ambiente impedem somente
a autorização de instalação/deploy e não invalidam o candidato local selado.
