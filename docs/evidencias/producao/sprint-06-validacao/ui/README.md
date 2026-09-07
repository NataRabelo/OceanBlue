# Sprint 06 — validação independente da UI

Execução de 2026-09-07. Escopo: testes browser e correções de foco em Auditoria e Operações. Sem commit e sem integrações externas.

**Resultado final: 26/26 passaram em 358,97 s, sem falhas, erros ou skips.** São 20 casos adversariais novos e seis testes existentes da Sprint 06, incluindo venda, retentativa e estorno mobile. App e testes congelados após o GREEN focal do skip-link, sem novas alterações durante a regressão final.

## Ambiente e isolamento

- Imagem existente `oceanblue-s06-complete-test`, ID `sha256:0e93bf35b7a44c0525d1ae30c9d0b2cf137e0739efe7ad1ddbf36ebccc480429`.
- A comparação de 285 arquivos de `app`, `tests`, `scripts` e `migrations` com o HEAD `804256ae6edafb4a2db99dcdb39ddacb987f9148` não encontrou diferenças de conteúdo, normalizando somente CRLF/LF. Ver `image-head-comparison.json` e os manifestos SHA-256.
- Alterações simultâneas de outras frentes no workspace não entram nesta execução: a imagem fornece o baseline; somente os dois testes Sprint 06, `header.js` e `operational.css` são montados sobre `/app`, todos somente leitura. `image-workspace-comparison.json` registra diferenças observadas durante a execução concorrente, sem atribuí-las a esta frente.
- Projeto Compose exclusivo `oceanblue-s06-ui-independent`, rede interna, PostgreSQL exclusivo em tmpfs, sem portas publicadas. Não utiliza o banco `blueocean_db` nem serviços de outras aplicações.
- Aplicação, Gunicorn, Chromium e pytest executam dentro do container. Sem bind do workspace inteiro ou da pasta de evidências. Bytecode e cache pytest desabilitados; resultados em `/tmp`, copiados depois para esta pasta. A comparação local de hashes somente lê fontes e grava seus relatórios nesta pasta.
- `init: true` permite recolher processos filhos do navegador. A primeira execução RED não tinha essa opção e apresentou um encerramento de Chromium durante setup, registrado separadamente das falhas da aplicação.

## Achados reproduzidos e correções

| Defeito | Reprodução | Correção restrita |
| --- | --- | --- |
| Foco sai da lateral móvel para o fundo | Abrir por Enter, depois Shift+Tab | Tab/Shift+Tab circulam pelos controles visíveis da lateral; Escape fecha e devolve foco ao acionador |
| Lateral ultrapassa a tela em 320 px | Lateral mede 332 px | `max-width: 100vw` no CSS operacional móvel |
| Foco fica em controle oculto ao mudar a largura | Fechar menu some no desktop; links da lateral recolhida somem no mobile | Mudança do breakpoint transfere foco para controle visível |
| Lateral móvel restaurada não recebe foco | Recarregar página com menu expandido persistido | Inicialização posiciona o foco no botão de fechar |
| Menu de usuário permanece aberto pelo teclado | Tab para link e Escape | Escape fecha e restaura foco; Tab para fora fecha sem roubar foco; estado `aria-expanded` e `aria-controls` sincronizado |
| Link de salto retorna à navegação | Enter em `Ir para o conteúdo` foca o wrapper que contém o cabeçalho | Destino passa a ser o `main`; o próximo Tab alcança o primeiro controle operacional |

Os testes percorrem Auditoria e Operações; larguras 320, 390, 767, 1024 e 1440 px; Enter, Space, Tab, Shift+Tab e Escape; retorno de foco; contorno visível e limites geométricos. Também verificam o salto direto ao conteúdo, assets locais com resposta 200 e CSS/ícones carregados, consulta sem rede, recuperação pela mesma tecla após reconexão e axe WCAG 2 A/AA e 2.1 AA. A propriedade de `tests/test_sprint06_browser.py` foi ampliada explicitamente pelo solicitante para fortalecer a expectativa de foco no `main`; não foi necessário alterar `base.html`.

## Evidências

- `green/pytest.txt`, `green/junit.xml`, `green/e2e/`: regressão final completa, saída 0. Nesta rodada não houve erro de inicialização do Chromium. As falhas transitórias anteriores permanecem nos registros; não foi adicionado retry para mascarar asserts ou crashes.
- `final-summary.json`: 26 registros browser, Chromium 140.0.7339.16, zero erros JavaScript e zero requisições externas; 21 respostas de assets nos dois casos offline e zero violações axe nesses casos. Confirma também que os quatro hashes congelados permaneceram iguais até o encerramento.
- `cleanup.txt`: runners exclusivos removidos e projeto `oceanblue-s06-ui-independent` encerrado após a cópia das evidências; banco tmpfs e rede descartados. As imagens e os serviços de outras frentes foram preservados.
- `red/pytest.txt`, `red/junit.xml`, `red/e2e/`: execução inicial com 13 falhas, 6 sucessos e 1 erro em 277,95 s. Doze falhas reproduzem os cinco defeitos da tabela. A falha restante era uma leitura instantânea do contorno durante transição CSS: o teste final espera o estilo estabilizar. O erro foi no setup do Chromium, antes da UI.
- `header.red.js.txt` e `operational.red.css.txt`: fontes anteriores às correções, usadas para reprodução RED.
- `iteration-1/`: rodada interrompida ao detectar que ocultar a lateral pode apagar `document.activeElement` antes do evento de breakpoint; a correção mantém o último elemento focado. Dois erros adicionais de inicialização do Chromium foram registrados, incluindo SIGSEGV. `iteration-2/`: dez casos passaram, incluindo as duas transições de breakpoint, antes da interrupção solicitada para ampliar a correção do link de salto.
- `header.skip-red.js.txt` e `compose.skip-red.yml`: estado imediatamente anterior à correção do link de salto. Para reproduzir apenas esse RED, use o overlay e `-k skip_link` no teste adversarial.
- `skip-red/`: duas falhas em 31,08 s, ambas por `main` sem foco. `skip-green/`: os mesmos dois casos passaram em 43,72 s, verificando foco em `main` e próximo Tab no primeiro campo operacional.
- `frozen-source-sha256.json`: hashes dos quatro arquivos finais congelados após o GREEN focal. `canonical-ui-sha256.json` registra a comparação bem-sucedida com a imagem preflight **antes** da ampliação do skip-link; a build final deve incorporar os hashes atuais.
- Cada caso finalizado contém screenshot, HTML, versão do navegador, erros JavaScript, requisições externas e trace Playwright. Os casos de assets/offline incluem `assets-offline.json` com respostas, falhas provocadas e violações axe.

## Reprodução

Na raiz do workspace, em PowerShell:

```powershell
$env:OCEANBLUE_UI_WORKSPACE = (Get-Location).Path
$uiCompose = 'docs/evidencias/producao/sprint-06-validacao/ui/compose.ui.yml'
docker compose -p oceanblue-s06-ui-independent -f $uiCompose up -d db-test
docker compose -p oceanblue-s06-ui-independent -f $uiCompose run --name oceanblue-s06-ui-green test python -m pytest tests/test_sprint06_browser.py tests/test_sprint06_browser_adversarial.py --no-cov -v -p no:cacheprovider --junitxml=/tmp/junit.xml
New-Item -ItemType Directory -Force docs/evidencias/producao/sprint-06-validacao/ui/green
docker cp oceanblue-s06-ui-green:/tmp/junit.xml docs/evidencias/producao/sprint-06-validacao/ui/green/junit.xml
docker cp oceanblue-s06-ui-green:/tmp/e2e docs/evidencias/producao/sprint-06-validacao/ui/green/e2e
```

O comando padrão do serviço executa somente os 20 casos adversariais; o comando acima inclui os seis casos existentes da Sprint 06. Para repetir com o código anterior, acrescente `-f docs/evidencias/producao/sprint-06-validacao/ui/compose.red.yml` ao comando Compose e use outro nome exclusivo `oceanblue-s06-ui-*`. Não execute dois runners simultaneamente contra o mesmo banco. Depois de copiar os resultados, remova apenas os containers de teste nominados e encerre este projeto Compose.

## Limites

- Esta validação verifica o baseline da imagem com os quatro overlays, não a integração das alterações concorrentes. As integrais finais devem construir ou montar o conjunto consolidado.
- Chromium headless em Linux; viewport reduzido não equivale a aparelho real. Não cobre WebKit/Safari, Firefox, leitores de tela, gestos, teclado virtual ou todas as combinações de tema/permissão.
- Offline significa página já carregada sem acesso à rede, erro anunciado e recuperação explícita. Não há promessa de iniciar a aplicação offline, de cache persistente ou de transações offline.
- Com JavaScript, o link de salto aponta para `main`, cujo ID é preservado quando existente e recebe `tabindex=-1`. Sem JavaScript ou sem `main`, permanece o fallback original do template para `#page-content`.
- O sucesso do axe não certifica conformidade integral de acessibilidade. A consulta sem rede pode exibir o texto técnico `Failed to fetch`; tradução desse erro pertence aos scripts de módulos, não foi alterada nesta frente.
- Testes browser focados usam `--no-cov`: não substituem o gate de cobertura da suíte integral. Traces e HTML contêm somente os dados sintéticos dos fixtures.
