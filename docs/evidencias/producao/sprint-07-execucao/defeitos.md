# Relatório de defeitos — Sprint 7

Resultados focais não são somados aos integrais como casos independentes. Erros de preparação
dos runners ficam separados dos defeitos de produto. As exigências de novas regressões
registradas nas linhas históricas abaixo foram cumpridas pelas duas integrais rc6:
868 aprovados em cada, zero falhas/erros/skips, processo e runner exit0, cobertura 77,2474%.
Todos os defeitos RC07-01 a RC07-11 estão corrigidos no candidato; provas operacionais
também retornaram exit0. Integridade do pacote e decisão final constam no relatório principal.

| ID | Defeito e impacto | Correção | Verificação |
| --- | --- | --- | --- |
| RC07-01 | Health anunciava `1.0.0`, divergente do pacote e impedindo identificar a versão servida | `app/health.py` lê `VERSION`; rótulo OCI e manifesto usam `2.1.0-rc.1` | `test_health_reports_packaged_release_version`, contrato de configuração e smoke |
| RC07-02 | Checklist vigente mandava habilitar Asaas/Focus apesar do bloqueio produtivo | Checklist substituído; relatórios antigos identificados como históricos | Revisão documental, flags e testes produtivos anteriores preservados |
| RC07-03 | Provas dependiam de nomes/digests de imagens de outras tarefas já existentes no host | Imagens parametrizadas; rollback reconstruído do Git da Sprint 6 e identificado por digest local | Runner final e provas operacionais |
| RC07-04 | Dependências travadas tinham advisories conhecidos; pip vulnerável também era herdado pela imagem produtiva | Atualização dirigida de pins e locks, incluindo pip produtivo | pip-audit antes/depois, instalação com hashes, pip check, regressão integral |
| RC07-05 | Inventário de fontes omitia `wsgi.py`, permitindo divergência do entrypoint sem detecção; o pacote também precisava desse arquivo | Inclusão explícita nos manifestos e no arquivo de release | Teste focal do inventário e inicialização real da imagem reconstruída do pacote |
| RC07-06 | Filtros de indicadores não quebravam linha em tablet; Chromium exigia largura mínima que ultrapassava o documento em 768 px | Uma classe `flex-wrap` na linha de filtros, mantendo controles e asserções | Primeira regressão integral: 867 aprovados e uma falha; `failed-candidate/` preserva JUnit, observação e fontes da imagem rejeitada. Recorte corrigido dos três motores passou; duas regressões finais novas são obrigatórias |
| RC07-07 | Link de pular para conteúdo posicionava o início do `main` sob o cabeçalho sticky translúcido. Em Firefox/WebKit o texto ficava sobreposto; Chromium desfocava o conteúdo encoberto | Margem de rolagem/foco medida e superfície opaca de contraste adequado; asserções geométricas na matriz existente | Rejeição histórica em `visual-rejected-candidate/`. As duas integrais rc6 verificam 225 skips cada; revisão individual dos 15 PNGs finais confirma correção |
| RC07-08 | Regra global `coverage.xml` ignorava os relatórios curados novos, que poderiam faltar no commit apesar de existirem no pacote local | Exceção limitada ao diretório de evidências da Sprint 7; artefatos brutos continuam ignorados | Conferência real com `git check-ignore`; inventário final de evidências e arquivos staged |
| RC07-09 | Transição de cores do botão de finalizar venda produzia contraste de 3,536:1 durante a habilitação, reproduzido pelo Axe em Chromium 390 px | Remoção somente da transição do botão; verificação imediata de duração zero na jornada existente, sem espera ou exclusão no Axe | Candidata rc3 rejeitada; prova negativa e reteste focal em `pdv-correction/`; novo scan e duas regressões integrais obrigatórios |
| RC07-10 | Seleção decimal adiada podia recuperar foco no Firefox e sobrescrever o preço de atacado ao preencher a quantidade seguinte | Conferência de `document.activeElement` antes da seleção adiada; prova de foco e dos valores persistidos na mesma jornada | Reteste independente rc4 rejeitado: 867 aprovados e uma falha, após primeira integral 868 verde; novo congelamento, scan e duas integrais obrigatórios |
| RC07-11 | Nova Role podia ser acionada antes de `role.js` terminar de carregar, causando erro JavaScript e não abrindo o formulário | Botão nativamente desabilitado até a inicialização síncrona de `rolePage`; prova controlada retendo e liberando a requisição local real | Candidata rc5 rejeitada: 867 aprovados, uma falha e um erro de teardown do mesmo caso; red/green focal e duas integrais finais obrigatórios |

Reauditoria funcional: `auditoria-modulos.md` e `module-audit/` registram IDs ambíguos,
datas operacionais brasileiras, devoluções parciais e preservação de cadastros desativados.
A prova negativa ampliada reproduziu 26 falhas e manteve um controle válido; os 29 casos
novos de módulo entram nas duas regressões finais, sem somar execuções focais repetidas.
Reauditoria de UI: `auditoria-ui.md` registra problemas realmente reproduzidos e correções.

## Preparação dos runners

O primeiro preflight operacional parou corretamente porque o teste de carga exigia três
eventos de auditoria por empresa, embora o seed de serviços não gere esses eventos HTTP.
O contrato foi corrigido para exigir eventos reais existentes na listagem autorizada,
sem fabricar linhas nem reduzir as asserções de vendas, estoque e financeiro.
O segundo preflight passou integralmente: 120 requisições TLS autenticadas, 32 cenários
de snapshot, recuperação, rollback, proxy, alertas e recusa de quatro segredos ausentes.
Esses resultados preliminares não substituem o gate operacional do candidato congelado.

Após o primeiro scan final aprovado, a preparação da regressão revelou que o shim
`npm.ps1` do host reinterpretava a chamada indireta com redirecionamento como comando
`Program`. Nenhum teste havia começado. O runner seleciona `npm.cmd` no Windows e
mantém `npm` nos demais sistemas; a mesma chamada passou com `npm ci`, 76 pacotes
auditados e zero advisories. Como houve alteração no runner, o scan vinculado completo
foi repetido antes da primeira regressão integral.

Bloqueios operacionais não são defeitos funcionais ocultados: TLS/backup/alertas/capacidade
da instalação dependem do operador. Emissão bancária/fiscal real está excluída explicitamente.
Scans de dependências não são auditoria universal de segurança nem certificação legal de licenças.
