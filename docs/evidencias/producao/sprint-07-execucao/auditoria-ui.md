# Auditoria UI — Sprint 07

Base: `7b0c97f`. Escopo: novo teste browser, tres motores em `Dockerfile.test`, correcoes confirmadas em templates/JavaScript e evidencia UI. Sem commit; release tooling, testes anteriores e gates preservados.

## Cobertura e resultado anterior (correcao tablet)

- **72/72 casos browser aprovados**, 24 por motor real: Chromium 140.0.7339.16, Firefox 141.0, WebKit 26.0. Zero falhas, erros ou skips.
- 54 grupos de navegacao: 25 telas × 320/768/1440 px × tres motores = **225 verificacoes executadas**. Mais 18 jornadas em 390/1440 px.
- Jornadas reais: categoria/produto/cliente → estoque → venda de R$25,00 → comprovante → saldo 7 para 5 → financeiro/auditoria; role/funcionario/edicao/login restrito; paginas de senha e provisionamento com novo login e isolamento de empresa.
- Axe local WCAG 2 A/AA e 2.1 AA sem exclusoes; teclado, skip link, menu mobile, overflow, estilos locais, erros JavaScript e HTTP verificados.
- Execucao integral do modulo: **2489,288 s (41min29s)** no JUnit, parcialmente concorrente com a regressao original. Exit code 1 somente pelo gate global de cobertura mantido em 50%: recorte browser atingiu 45,69%. Nao e falha de teste nem aprovacao global da release.
- Parent ainda executara novo scan vinculado e **duas suites completas**. Manter timeout de 90 minutos; nenhuma reducao de cobertura, skip ou recolha duplicada foi introduzida.

## Reabertura e correcao tablet

A regressao original do parent terminou com 867 aprovados e uma falha: `chromium-stock-sales-768`, exclusivamente overflow em `/api/estoque/indicadores/view`; Axe, HTTP, JavaScript e acessos externos limpos. Firefox/WebKit originais passaram.

A linha de quatro filtros mudava para `sm:flex-row`, mas nao podia quebrar: larguras declaradas totalizavam 784 px, mais 36 px de espacos, pressionando os minimos nativos do Chromium no conteudo tablet. **Unico delta de codigo apos o primeiro freeze:** adicionar `flex-wrap` nessa linha em `estoque_indicadores.html`, sem ocultar controles nem mudar a assercao de overflow.

Reteste focal stock-sales/768: **3/3 motores aprovados em 149,75 s**, indicador com `overflow=false`. Depois, os 72 casos completos passaram sobre o mesmo codigo corrigido.

## Demais correcoes confirmadas

- Modal de categorias invisivel por conflito de display e referencia a CSS inexistente em funcionarios.
- Nomes em filtros/botoes; tabelas focaveis; contraste de textos, header, alertas e toasts; quebra da barra de funcionarios em 320 px.
- Revisao visual encontrou calendario escuro no Chromium e selects claros com texto branco no WebKit: controles nativos usam `color-scheme: dark` somente no modo moderno. Estilo e preenchimento verificados; screenshots dos tres motores inspecionados. Modo classico preservado.
- Erro SQL do dashboard comunicado e corrigido pelo responsavel backend, sem alteracao backend nesta entrega.

## Isolamento, evidencia e cleanup

Fixtures de banco reaproveitadas; banco/contexto/cookies isolados por caso. Servidor e motores reutilizados. Navegador limitado a `http://127.0.0.1:8767`, WebSockets bloqueados, service workers desativados; protecao de sockets anterior intacta. Backend Docker exclusivo `internal: true`, sem portas publicadas.

Resumo focal e JUnit: [ui-correction/summary.json](ui-correction/summary.json) e [ui-correction/junit.xml](ui-correction/junit.xml). Sem duplicar PNG em Git. Saida completa em `C:/Users/Rabel/AppData/Local/Temp/sprint07-ui-all72-final`: **72 JSON + 72 PNG, 13.261.393 bytes**, exatamente dois arquivos por caso, sem traces/HTML/logs de sucesso. Red original preservado em `C:/Users/Rabel/AppData/Local/Temp/sprint07-indicators768-red.json` e `sprint07-indicators768-red-trace.zip`.

Runner `oceanblue-s07-ui-focal`, banco e rede exclusivos removidos apos coleta. Este freeze anterior foi reaberto pelo bloqueio visual descrito abaixo; nao representa aprovacao do candidato atual.

## Reabertura visual do header e novo freeze

Mesmo apos duas suites de 868 verdes do parent, a revisao humana dos 15 PNG curados encontrou colisao real do titulo principal sob o header sticky. O candidato rc2 foi rejeitado; red canonico e provas anteriores permanecem em `visual-rejected-candidate/`. Nao houve outro bloqueio funcional confirmado nesses 15: input branco de auditoria usa texto escuro, tabela horizontal tem regiao de teclado e toast de acesso negado e transitorio intencional.

- **Red reproduzido nos tres motores/320:** main e heading em y=0 sob header com base y=81, foco preservado em main. JUnit: 3 falhas em 101,547 s.
- **Correcao raiz:** scroll-margin-top do main acompanha altura real do header +16 px via ResizeObserver, mantendo ancora/foco nativos. Header e dropdown modernos recebem superficie opaca; pequenos labels confirmados passam de contraste 3,751:1 para **6,963:1**. Sem redesign, reset de scroll para screenshot, ocultacao, exclusoes Axe ou alteracao CSP.
- **Full72 final: 72 aprovados, zero falhas/erros/skips, 1886,495 s (31min26s)**. 24 por motor; todos os 54 casos de navegacao e 18 jornadas preservados. 225 verificacoes de skip com foco/geometria, 225 de scroll normal, 75 retornos do menu mobile e 12 menus de usuario abertos +12 retornos de foco. Axe executado em 345 estados, sem violacoes, overflow ou erros HTTP/JS/externos.
- Em Importacao/320, todos os motores mantem heading/main em y=97 abaixo do header y=81 apos skip e Escape. Scroll normal real PageDown mantem header legivel. Menus Home/modulo em 320/1440 aguardam fim da animacao antes de Axe e medicao explicita de contraste.
- Revisao visual propria final: **15 capturas correspondentes +6 estados skip/scroll +12 menus abertos**, sem bloqueio adicional. Parent tambem revisou os 15 originais e seis estados corrigidos. Somente dois PNG verdes WebKit de probe preservados no repositorio.
- Exit code 1 exclusivamente pelo gate global de 50% preservado: recorte browser 45,69%. **Nao e aprovacao global da release**; novo scan vinculado, duas suites completas e operacoes do parent ainda obrigatorios.

Prova compacta: [resumo e totais distintos de probes](ui-correction/header-summary.json), [JUnit red](ui-correction/header-red-junit.xml), [JUnit full72 green](ui-correction/header-green-junit.xml), [skip WebKit](ui-correction/sprint07-webkit-320-skip-to-content.png) e [scroll normal WebKit](ui-correction/sprint07-webkit-320-normal-scroll.png). Runs intermediarios nao sao somados como cobertura distinta; resultado final acima pertence exclusivamente ao ultimo full72.

Saida integral: `C:/Users/Rabel/AppData/Local/Temp/sprint07-ui-header-all72-final`, 72 JSON +72 PNG, 13.086.733 bytes, exatamente dois arquivos por caso e nenhum trace/HTML/log de sucesso. Probes adicionais ficam em `C:/Users/Rabel/AppData/Local/Temp/sprint07-header-visuals`, fora dos diretorios canonicos.

**Novo freeze UI:** runner `oceanblue-s07-ui-geometry`, banco e rede exclusivos removidos apos coleta; recursos do parent intocados. Sem mudancas adicionais planejadas e sem commit. Fonte pronta para novo binding rc3; aceite final pertence aos gates completos do parent.

## Reabertura rc3: contraste transitorio no PDV

O rc3 terminou com 867 aprovados e uma falha em 3229,49 s: `catalog_client_sale_stock_financial_audit_journey[chromium-390]`, Axe `color-contrast` no botao `#pdv-finalizar-venda` durante `confirm-sale`. JSON original preservado, sem novo red fabricado: texto `#0a0f20`, fundo `#167862`, contraste 3,53:1 abaixo de 4,5:1. Venda R$25,00 e estoque final 5 permaneceram corretos.

O trace mostra Axe iniciando 87,265 ms apos retorno da confirmacao do pagamento, dentro da transicao CSS de 150 ms que animava texto/fundo ao habilitar o botao. A cor intermediaria era ilegivel; estados finais normal/hover tinham contraste suficiente. **Patch de produto limitado a remover somente `transition` desse botao.** A mesma jornada agora registra e exige imediatamente `disabled=false` e `transitionDuration=0s`, sem esperar a animacao nem enfraquecer Axe. Nenhum caso adicionado; total 868 mantido.

Focal autorizado, iniciado somente apos fim do rc3: `python -m pytest tests/test_sprint07_browser.py -k test_catalog_client_sale_stock_financial_audit_journey --no-cov --tb=short -q --junitxml=/tmp/sprint07-pdv-focal6.xml`. **Processo exit0: 6 aprovados, 66 deselected, zero falhas/erros/skips, 264,010 s (4min24s)**; Chromium/Firefox/WebKit em 390/1440. Todas as seis mediram transicao 0s, sem violacoes Axe, overflow ou erros HTTP/JS/externos. `--no-cov` vale somente para este focal solicitado; configuracao global e minimo 50% intactos. **Nao e gate global:** novo scan rc4 e duas FULL868 com cobertura e exit0 continuam obrigatorios. Nenhum novo full72 focal executado.

Prova compacta: [red original e timings](pdv-correction/red.json), [resumo/command/exit0](pdv-correction/summary.json) e [JUnit focal6](pdv-correction/green-junit.xml). Saida completa em `C:/Users/Rabel/AppData/Local/Temp/sprint07-pdv-focal6-final`, seis JSON +seis PNG, sem traces de sucesso ou duplicacao de PNG no repositorio.

**Freeze UI para rc4 confirmado:** runner `oceanblue-s07-ui-pdv`, banco e rede exclusivos removidos apos coleta; nenhum recurso do parent alterado. Sem commit e sem outras alteracoes planejadas.

## Reabertura rc4: foco decimal sobrescrevia campo anterior

A primeira FULL868 rc4 passou, mas o retest encontrou total R$6,00 em vez de R$25,00 na jornada Firefox/1440. Leitura do trace e respostas esclareceu: varejo continuava 12,50; o formulario ja enviava atacado 3,00 e minimo 1. O PDV aplicava corretamente 2×3 no modo automatico. O trace registra atacado 10,00 apos `call@10292`; o preenchimento seguinte, `call@10294`, destinado ao minimo, escreveu 3 no atacado.

**Raiz comprovada antes do patch:** callback `requestAnimationFrame` da mascara chamava `input.select()` mesmo apos mudanca de foco, recuperando o campo antigo no Firefox. Probe deterministico no mesmo caso: foco A=atacado, B=minimo imediatamente, mas proximo frame voltava a A. Red real: uma falha, exit1, JUnit 26,741 s; nenhuma simulacao de resultado ou novo red inventado.

**Unica alteracao de runtime:** guard `if (document.activeElement !== input) return;` dentro do callback existente, antes de `input.select()`. A jornada existente agora exige A→B→proximo RAF preservando B, valores visiveis 12,50/10,00/min3 e resposta persistida 12.50/10.00/min3 antes de chegar ao PDV. Sem sleeps/retries, alteracao de precos/backend, enfraquecimento de Axe ou novos casos; total868 mantido.

Focal autorizado apos encerramento do full rc4: `python -m pytest tests/test_sprint07_browser.py -k test_catalog_client_sale_stock_financial_audit_journey --no-cov --tb=short -q --junitxml=/tmp/sprint07-decimal-focal6.xml`. **Exit0: seis aprovados, 66 deselected, zero falhas/erros/skips; JUnit290,802 s (4min51s)**. Chromium/Firefox/WebKit ×390/1440 preservaram foco B, dados persistidos, venda25 e estoque5; zero violacoes Axe/overflow/HTTP/JS/externos. Nenhum full72 adicional. `--no-cov` somente focal; gate global50% intacto. Aceite ainda exige scan rc5 e ambas FULL868 com cobertura/exit0, alem das operacoes do parent.

Prova compacta: [red observado e deterministico](decimal-focus-correction/red.json), [JUnit red](decimal-focus-correction/red-junit.xml), [resumo/exit0](decimal-focus-correction/summary.json) e [JUnit seis green](decimal-focus-correction/green-junit.xml). Saida integral `C:/Users/Rabel/AppData/Local/Temp/sprint07-decimal-focal6-final`: seis JSON +seis PNG, nenhum trace de sucesso ou PNG duplicado no repositorio.

**Freeze UI para rc5 confirmado:** runner `oceanblue-s07-ui-decimal`, banco e rede exclusivos removidos; parent intocado. Prova/documentacao finalizadas, sem commit nem outras alteracoes planejadas.

## Reabertura rc5: disponibilidade do botao Nova Role

O trace Firefox/1440 confirmou botao Nova Role visivel/habilitado antes de `role.js` carregar: clique gerou `rolePage is not defined` em 477006,464 ms; requisicao real do script iniciou em 476219,934 ms e durou 3080,071 ms (HTTP200), inicializando normalmente depois. Nao era residuo de contexto/GC nem falha de backend. Red deterministico antes do patch reteve somente a URL exata localhost de `role.js`, sem resposta simulada: botao habilitado com `rolePage` ausente, uma falha/exit1 em 30,128 s.

**Correcao de produto limitada a Nova Role:** id e `disabled` nativo no HTML; habilitacao somente apos retorno de `window.rolePage.init()`. Esse metodo vincula forms/modal sincronicamente e dispara listagem assincrona; nenhum await ficticio ou bloqueio da listagem foi introduzido. Na mesma jornada, script real fica retido para exigir disabled/nao inicializado, e e liberado em finally antes de exigir habilitado/inicializado e executar CRUD/login real. Total868 e todas as assercoes anteriores preservados.

O primeiro focal6 terminou 5 aprovados/1 falha em 224,068 s, embora todas as seis verificacoes de disponibilidade passassem. Falha adicional de observacao do toast no Firefox/390: favicon demorou 8364,687 ms, mas o toast intencional desaparece em 6000+500 ms. Frames reais do trace foram inspecionados: mensagem visivel em 32399,282 ms e ausente em 38930,144 ms; teste antigo so verificava em 40516,905 ms apos networkidle. **Ajuste somente no teste autorizado:** DOMContentLoaded → status200/homeURL/texto do toast/noRoleTable → networkidle. Mesmos timeouts, controle de acesso e Axe; nenhum runtime de toast alterado. Tentativa intermediaria interrompida para carregar a ordem final foi descartada, nao aceita.

Novo focal completo das seis jornadas admin: `python -m pytest tests/test_sprint07_browser.py -k test_admin_role_employee_and_restricted_login_journey --no-cov --tb=short -q --junitxml=/tmp/sprint07-role-focal6-green.xml`. **Exit0: seis aprovados, 66 deselected, zero falhas/erros/skips, JUnit166,803 s (2min47s)**. Chromium/Firefox/WebKit ×390/1440: botao disabled antes do script e habilitado depois, CRUD/login restrito completos, zero Axe/overflow/HTTP/JS/externos. Sem sleeps/retries/noops/exclusoes e sem novo full72. Cobertura desativada apenas nesse focal solicitado; gate global50% intacto.

Prova compacta em `role-readiness-correction/`: [red observado/deterministico](role-readiness-correction/red.json), [JUnit red](role-readiness-correction/red-junit.xml), [focal5/1 rejeitado e timings](role-readiness-correction/toast-rejected.json), [JUnit rejeitado](role-readiness-correction/toast-rejected-junit.xml), [resumo final](role-readiness-correction/summary.json) e [JUnit seis aprovados](role-readiness-correction/green-junit.xml). Saida completa `C:/Users/Rabel/AppData/Local/Temp/sprint07-role-focal6-green-final`: seis JSON +seis PNG, nenhum trace de sucesso ou PNG duplicado no repositorio.

**Freeze UI para rc6 confirmado:** runner `oceanblue-s07-ui-role`, banco e rede exclusivos removidos; recursos parent intocados. Sem commit nem outras alteracoes planejadas. Nao e GO global: novo scan vinculado, ambas FULL868 com cobertura/exit0 e operacoes do parent continuam obrigatorios.

## Rc6: primeira integral e revisao das 15 capturas reais

Primeira FULL rc6 concluida com **868 aprovados, zero falhas/erros/skips, exit0 e 3381,763 s**, incluindo 72 casos UI e 345 estados Axe. JUnit e JSON consultados em `regression/`; esta secao registra apenas essa primeira rodada. No momento da revisao, retest e aceite operacional final ainda pendentes; **nao constitui GO isolado**.

Foram abertas e inspecionadas individualmente as **15 imagens atuais** `regression/e2e/sprint07/**/sprint07-screen.png`, nao capturas de rc4 ou probes anteriores: tres login restrito/390, tres navegacao admin/320, seis jornadas catalogo→auditoria/390 e1440, tres provisionamento→modal de produto/390; Chromium, Firefox e WebKit reais.

Conclusao visual: **nenhum novo bloqueio funcional ou de legibilidade**. Em admin/320, titulo principal inteiramente abaixo do header opaco; JSON confirma header y=81 e heading y=97, foco `main-content` no skip nos tres motores. Auditoria desktop permanece legivel; corte horizontal da tabela mobile corresponde a regiao rolavel intencional, nao a overflow da pagina. Inputs brancos de auditoria conservam estilo de texto escuro; calendarios/selects nativos e labels do modal de produto legiveis. Toast de acesso negado continua sobreposicao transitoria intencional. Sem proposta de polish ou redesign.

As chaves dos **JSONs reais dessa integral**, lidas sem alteracao, confirmam em cada combinacao de tres motores ×390/1440:

- Seis `role_before_script`: `disabled=true`, `initialized=false`, `script_held=true`; seis `role_after_script`: `disabled=false`, `initialized=true`.
- Seis `decimal_focus`: primeiro atacado, imediatamente minimo e proximo frame ainda minimo; seis `product_form_prices` com 12,50/10,00/min3 e `product_saved_prices` com 12.50/10.00/min3.
- Seis `finalize_enabled_state`: `disabled=false`, `transition_duration=0s`.
- Total72 `passed=true`; 345 estados sem violacoes Axe ou overflow.

Nesta revisao, somente esta secao documental foi acrescentada. Nenhum codigo, outro artefato, recurso ou teste novo; fonte rc6 permanece congelada para retest/operacoes do parent.

## Integracao rc4 nas suites completas

A primeira regressao rc4 passou com processo e runner exit0: 868 casos, zero falhas,
erros ou skips, JUnit 2959,179 s. Inclui os 72 casos UI, nao soma os focais novamente.
Seus JSONs confirmam 345 estados Axe sem violacoes, 225 verificacoes de skip com foco
e geometria, 225 de scroll normal com header opaco, 75 retornos de foco do menu lateral,
12 menus de usuario abertos e 12 retornos de foco. As seis jornadas PDV confirmam duracao
de transicao 0s. Conteudo acima da viewport durante PageDown e comportamento normal;
a ausencia de oclusao do inicio do main e exigida especificamente apos o skip.

Revisao humana das 15 capturas curadas dessa propria rodada, em 2026-09-07 13:52–13:54
de Brasilia: tres telas Importacao/320, seis Auditoria/390/1440 apos vendas, tres perfis
restritos/390 e tres produtos do tenant provisionado/390. Sem novo bloqueio visual.
Header e titulo permanecem separados nos tres motores; input branco de auditoria mantem
texto escuro, tabelas largas usam regiao rolavel acessivel e toast de acesso negado e
transitorio. Controles nativos variam entre motores, mas permanecem legiveis.

O aceite global ainda exige o reteste independente completo, operacoes e integridade
do pacote; esta secao nao transforma o primeiro resultado em GO isolado.

## Fechamento das duas integrais autoritativas rc6

Os registros de freeze e pendencia anteriores sao historicos. As duas rodadas finais
`regression/` e `retest/` passaram cada uma com **868 casos, zero falhas/erros/skips e
processo/runner exit0**, cobertura global habilitada de 77,2474%. Tempos JUnit:
3381,763 s e 3532,858 s. Os 72 casos UI estao incluidos em ambas, sem somar os focais.

Cada rodada registra 345 estados Axe sem violacoes, 225 skips/geometria/foco, 225
rolagens normais, 75 retornos de foco lateral, 12 menus abertos e 12 retornos de foco
do usuario. As seis jornadas PDV e seis jornadas de roles preservam os controles
deterministicos adicionados, sem relaxar o gate global. Cada rodada conserva 15 PNGs
representativos e zero ZIP de sucesso. A revisao visual rc6 registrada nesta auditoria
abriu os 15 arquivos reais da primeira rodada final, nao as capturas rc4.

Esses resultados atendem a integracao global dos recortes que retornaram exit1 por
cobertura isolada. Aceite operacional, integridade e decisao de release constam no
relatorio principal `../sprint-07-execucao.md`, nao sao inferidos de um focal.
