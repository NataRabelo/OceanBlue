# Sprint 7 — fechamento e candidato final

Data de início: 2026-09-07, America/Sao_Paulo. Versão `2.1.0-rc.1`.
Base sincronizada por fast-forward: `7b0c97f87ec8cf1a9584c389717383c457bc764f`.

## Gate de entrada

GO lido em `sprint-06-validacao.md`. O run remoto
[34102472661](https://github.com/NataRabelo/OceanBlue/actions/runs/34102472661)
retornou `completed/success` para o mesmo SHA; atualização remota em `2026-09-07T09:05:13Z`.
O runner repete a conferência de ancestralidade, decisão e resultado remoto.

## Decisão

**GO para o candidato local `2.1.0-rc.1` da Sprint 7**, vinculado às duas regressões
integrais rc6, ao gate operacional e à verificação final do pacote/manifestos pelo runner
`assemble`. O conjunto verificável de evidências, não um resultado focal, sustenta o aceite.
**Não é autorização de deploy produtivo.** A instalação permanece NO-GO até cumprir os
itens próprios do checklist de produção, incluindo o scan de CVEs da imagem/SO.
Não houve push, deploy ou contato com provedores de negócio. O run remoto citado é da
base Sprint 6; os novos gates da Sprint 7 são locais, sem alegar um CI remoto não executado.

## Método e escopo

- Confronto do inventário original com os relatórios das Sprints 1–6, rotas, serviços,
  jobs, migrations, telas e documentação atuais.
- PostgreSQL 16 real em recursos descartáveis exclusivos; redes internas e navegadores
  limitados ao servidor local de testes. Os três serviços preexistentes foram preservados.
- Duas regressões integrais com criação do banco do zero, migrations individualmente,
  sentinela de upgrade, downgrade/reupgrade e comparação do schema com os modelos.
- Testes anteriores preservados; sem skip/xfail novo ou redução do gate de cobertura.
- Jornadas críticas reais de cadastro, cliente, estoque, PDV, financeiro, auditoria,
  roles/funcionários e administração de tenant, com navegador e backend reais.
- Boleto/Fiscal continuam inacessíveis em produção. Testes internos legados e simuladores
  permanecem preservados. WhatsApp/SMTP e demais transportes reais permanecem bloqueados.
- Provas operacionais de TLS, falhas de processo/banco/storage/proxy, backup/restore,
  recusa de snapshot adulterado, rollback e alertas.

## Auditorias e correções

### Resultado das duas regressões finais

Projeto autoritativo: `oceanblue-s07-rc6`. Nenhuma fonte mudou entre o scan final e
essas duas rodadas independentes. Cada runner terminou com código de saída **0**, incluindo
smoke produtivo não-root, segurança, indisponibilidade de storage/banco e limpeza.

| Gate | Regressão | Reteste independente |
| --- | ---: | ---: |
| Casos aprovados / anteriores preservados | 868 / 758 | 868 / 758 |
| Falhas / erros / skips | 0 / 0 / 0 | 0 / 0 / 0 |
| Duração JUnit | 3.381,763 s | 3.532,858 s |
| Cobertura combinada de linhas e ramos | 77,2474% | 77,2474% |
| Casos UI novos / estados Axe | 72 / 345 | 72 / 345 |
| Capturas representativas / traces ZIP retidos | 15 / 0 | 15 / 0 |

São 9.401/11.700 linhas e 1.701/2.672 ramos em cada rodada, acima dos **73,9354%**
combinados da base Sprint 6. Os 110 casos novos não substituem nenhum dos 758 anteriores.
O [resumo verificável](sprint-07-execucao/regression-summary.json) compara identidades,
contagens e cobertura; recortes focais anteriores não são somados como cobertura adicional.

Em cada rodada os JSONs UI confirmam 225 verificações de skip com foco/geometria,
225 de rolagem normal, 75 retornos de foco do menu lateral, 12 menus de usuário abertos
e 12 retornos de foco. Seis jornadas verificam preços persistidos e foco decimal; seis
verificam prontidão do script de roles. Nenhuma violação Axe, overflow de documento ou
erro HTTP/JavaScript/contato externo foi aceito. As 15 capturas da primeira rodada final
foram abertas e revisadas individualmente após as últimas correções.

A [rastreabilidade](sprint-07-execucao/traceability.csv) mantém 165 rotas. Há 1.125
observações HTTP in-process e 169 nomes de endpoint em cada rodada, dos quais **160/165**
pertencem ao inventário. Os nove demais pertencem a contextos auxiliares de teste/health.
Não foram observados nesse coletor `main.index`, `main.browserconfig`, `main.estoque_home`,
`main.favicon` e `main.site_webmanifest`; o hub de estoque tem prova própria no navegador.
Não se declara cobertura HTTP completa a partir de vínculos estáticos. O inventário de
componentes tem 354 arquivos; seu escopo difere dos 323 arquivos de cada imagem testada
e dos 339 arquivos vinculados pelo scan fora de `docs/`.

### Medições locais

Com 10.000 eventos sintéticos, paginação retorna 50 registros em 14 consultas:
0,09364 s na regressão e 0,09150 s no reteste. A carga in-process Flask/PostgreSQL
executa 120 requisições com concorrência 8 e 20.000 registros: zero erros, p95 de
2,1590 s e 1,2775 s, respectivamente. Isso não é latência TLS nem capacidade produtiva.
Nos dois ensaios de contenção, 16 vendas concorrentes disputam estoque 12: 12 aceitas,
quatro recusadas sem estoque e lançamentos financeiros somando R$120,00. Consultas de vendas,
lançamentos e movimentos permanecem em 15/14/14 para um e 25 registros.
Os orçamentos destes testes são gates de regressão locais, não SLA.

### Disposição funcional e visual

A [auditoria de módulos](sprint-07-execucao/auditoria-modulos.md) dá disposição aos
106 arquivos Python de `app`, incluindo 11 arquivos locais dormentes de boleto/fiscal.
O inventário mantém 165 rotas. Foram corrigidos IDs booleanos/fracionários aceitos como
outros registros, divergências de data brasileira/UTC, indicadores que ignoravam devoluções
parciais e reativação indevida de cadastros importados. Não houve reescrita de histórico
financeiro nem introdução de novo critério de rateio ou custeio.

A [auditoria de interface](sprint-07-execucao/auditoria-ui.md) combina Axe local sem
exclusões, teclado, responsividade e inspeção humana. A matriz nova tem 72 casos:
54 grupos de navegação, cobrindo 25 telas × três larguras × três motores, e 18 jornadas
completas em 390/1440 px. Foram corrigidos controles sem nome, contraste, foco de tabelas,
modal invisível, CSS inexistente, barra mobile e controles nativos ilegíveis. O visual
clássico não recebeu o esquema escuro específico dos controles modernos.

A primeira regressão completa foi corretamente **rejeitada: 867 aprovados, uma falha**
de overflow em indicadores a 768 px no Chromium. A correção foi uma classe `flex-wrap`,
sem ocultar filtros nem enfraquecer a asserção. O módulo browser corrigido passou seus
72 casos; esse recorte não substitui as regressões completas nem seu gate de cobertura.
O scan anterior também foi recusado após essa mudança de fonte, comprovando que a
verificação não reaproveita aprovação desatualizada. A sequência negativa e a correção
estão em [defeitos](sprint-07-execucao/defeitos.md), `failed-candidate/` e `ui-correction/`.

Uma segunda candidata passou duas rodadas de 868 testes e o gate operacional, mas a
revisão humana de todos os 15 PNGs representativos encontrou conteúdo encoberto pelo
cabeçalho após usar o link de pular para conteúdo. A aceitação visual foi **rejeitada**,
apesar de Axe e foco estarem verdes. `visual-rejected-candidate/` conserva essa distinção;
as evidências completas supersedidas ficam ignoradas em `.release-work/`. A correção
incluiu verificação geométrica, margem de rolagem medida e superfície opaca de contraste
adequado. O recorte de 72 casos passou, mas retornou código 1 por cobertura global;
por isso não substitui duas regressões integrais com código 0.

A terceira candidata reproduziu contraste transitório insuficiente no botão de finalizar
venda em Chromium 390 px. A animação de cores entre desabilitado e habilitado interpolava
um estado de 3,536:1, embora as cores finais fossem adequadas. A correção remove somente
a transição desse botão, sem atrasar ou excluir a análise Axe. Essa nova rejeição exige
outro scan vinculado e duas regressões completas; não se reaproveitam gates anteriores.

A quarta candidata passou a primeira integral de 868, mas o reteste independente foi
rejeitado com 867 aprovados e uma falha Firefox/1440. Uma seleção adiada de campo decimal
recuperava o foco do campo anterior; o valor de quantidade sobrescreveu o preço de atacado
antes do envio. O total do PDV refletiu corretamente esse cadastro incorreto. A correção
protege a seleção com a conferência do foco atual, sem alterar preços, regras comerciais,
timeouts ou tentativas. `decimal-focus-rejected-candidate/` mantém as duas rodadas distintas;
essa correção também exige novo scan e duas integrais completas antes de qualquer GO.

A quinta candidata foi rejeitada com 867 aprovados e um caso Firefox/1440 com falha
e erro de teardown: o botão Nova Role estava disponível antes de seu script terminar de
carregar, causando `rolePage is not defined`. A correção mantém o botão nativamente
desabilitado até a inicialização da página. Uma prova determinística retém apenas a
requisição local real do script, sem substituição de resposta ou espera para mascarar o erro.
`role-readiness-rejected-candidate/` preserva o resultado; novo congelamento e ciclo integral
são obrigatórios. Nenhuma dessas candidatas rejeitadas constitui aceite parcial.

Os 110 casos adicionados são 29 funcionais, 72 de navegador e nove de release; os 758
anteriores permaneceram nas duas rodadas finais. Rastreabilidade estática de serviço
não equivale a cobertura HTTP: o CSV final separa vínculo de código de requisições
efetivamente observadas, seus testes e status. Navegadores em subprocessos têm evidência
própria. O inventário de arquivos/AST não afirma execução de todas as funções ou ramos.

## Cadeia de fornecimento

O scan completo final ocorreu em 2026-09-07, das 16:09:10 às 16:13:02 de Brasília,
após congelar também a prontidão de Nova Role e a observação correta do aviso temporário.
`role-readiness-rejected-candidate/` inclui a recusa efetiva do scan anterior desatualizado.
A [evidência de supply chain](sprint-07-execucao/supply-chain/README.md)
registra instalações com hashes, `pip check`, advisories, licenças e SBOMs vinculados aos
locks e aos 339 arquivos do candidato fora de `docs/`. Os ambientes finais contêm 28
distribuições Python produtivas, 41 de desenvolvimento e 76 localizações npm travadas.
Os scans Python/npm retornaram zero advisories conhecidos naquele momento; não são
detecção de malware nem garantia contra vulnerabilidades desconhecidas.

As dez detecções de fonte do Gitleaks correspondem a linhas sintéticas individualmente
revisadas. As 19.698 detecções em evidências históricas continuam explicitamente pendentes
de revisão; não se certifica um histórico livre de segredos nem sua publicação irrestrita.
O pacote não duplica os traces históricos brutos. SBOMs Python seguem CycloneDX 1.6;
o npm usa 1.5, com conferência exata do lock e das referências, sem alegação de validação
independente de schema. Metadados LGPL com exceções e MPL exigem atenção de distribuição;
o inventário de licenças não constitui aprovação jurídica.

## Gate operacional e artefato

O runner `operations` da rc6 terminou com **código 0**. As provas usam PostgreSQL real,
TLS com certificado sintético verificado e redes/volumes descartáveis exclusivos.

| Prova | Resultado final |
| --- | --- |
| Falha/retorno de worker, banco, proxy, storage cheio e somente leitura | Comportamento esperado e recuperação verificados |
| Backup com escritores interrompidos | 17,5877 s; backup com escritores ativos recusado |
| Restore até smoke | 39,7290 s; três vendas e três lançamentos preservados |
| Rollback | Imagem anterior reconstruída da base Git executa sobre schema restaurado; reconciliação preservada |
| Snapshot adversarial | 32/32; zero falhas; recursos removidos |
| Carga TLS → nginx → Gunicorn → PostgreSQL | 120 requisições, concorrência 8, zero erros, p95 0,37025 s |
| Logs do proxy em erro 502 | Estruturados; zero sentinelas sintéticas vazadas |
| Alertas | Dois arquivos de testes Promtool aprovados |
| Segredos obrigatórios ausentes | Quatro inicializações recusadas antes de acessar o banco |

O dataset de recuperação tinha três vendas/três lançamentos, escritores interrompidos
e nenhuma escrita de negócio pós-snapshot: zero venda capturada perdida **não é promessa
de RPO zero produtivo**. A carga TLS usa três vendas, três lançamentos e 94 unidades de
estoque; login/auditoria posterior não faz parte da prova de RPO. Tempos são medições
locais, não SLA ou dimensionamento. Os três serviços preexistentes foram preservados;
os projetos descartáveis não deixaram containers, redes ou volumes.

O arquivo de distribuição é `dist/oceanblue-2.1.0-rc.1.tar.gz`. O
[manifesto externo](sprint-07-execucao/release-manifest.json) registra versão, base,
head de migration `a0d1e2f3a4b5`, inventário, tamanho e SHA-256 do pacote; o
[inventário de hashes](sprint-07-execucao/evidence-sha256.json) cobre as evidências finais.
Esses dois arquivos ficam fora do próprio pacote para evitar autorreferência.
`assemble` recusa fontes divergentes, reconfirma os quatro manifestos de imagens de
teste/smoke, extrai o arquivo em diretório novo e reconstrói uma imagem. O entrypoint
`wsgi` e `/api/health` são exercitados com rede desabilitada e sem banco, conferindo
`VERSION`; [saída de startup](sprint-07-execucao/package-startup.txt) e identidade da
imagem reconstruída são conservadas externamente. A verificação confere o hash de cada
membro do arquivo e de cada evidência, além dos gates JUnit/cobertura.

## Reprodução

Requisitos: checkout Git contendo a base fixada, Docker Linux, PowerShell 7, Python 3.12,
Node e acesso a registries/advisories durante a preparação. Nenhuma credencial de negócio.

```powershell
pwsh -NoProfile -File scripts/validate_release_candidate.ps1 -Project oceanblue-s07-replay -EvidenceDirectory docs/evidencias/producao/sprint-07-replay -Python python
```

O padrão `all` exige projeto novo. As fases `regression`, `retest`, `operations`, `assemble`
permitem investigar falhas sem reapresentar uma fase parcial como aprovação completa.
`assemble` exige as duas regressões, provas operacionais e scans vinculados às fontes finais.
A prova operacional exige subrede `172.30.62.0/24` livre e reconstrói a imagem anterior
do Git, sem depender de imagens locais de outras tarefas.

O pacote determinístico de fontes é gerado em `dist/`; o Git conserva seu manifesto e hash.
Determinístico significa o mesmo arquivo para o mesmo conjunto de bytes de fontes e
evidências; uma nova execução de testes/scans produz medidas e timestamps novos e,
portanto, pode gerar outro hash de pacote.
Ele permite reconstruir a aplicação e rodar o Compose de testes. O runner de release completo
também exige o histórico Git/base e os relatórios de entrada. Camadas de build e pacotes de SO
impedem prometer imagem Docker byte a byte idêntica em toda reconstrução futura.
Os hashes representam bytes exatos do checkout testado e do arquivo distribuído. Conversão
de finais de linha pelo Git pode mudar esses bytes; para conferir o artefato original,
use o pacote e seus manifestos externos, ou regenere evidências no novo checkout.

## Evidências e limites

Resultados finais, métricas, defeitos, rastreabilidade, SBOM, hashes e capturas estão
consolidados no diretório `sprint-07-execucao/`. Artefatos binários de sucesso
e dumps sintéticos ficam em `.release-work/`, ignorado pelo Git. JSON de Axe é resumido
com hash do original, regras verificadas e violações; capturas representativas são limitadas.
Os viewports são executados em motores headless no Linux, não em aparelhos físicos nem
no aplicativo Safari. Axe, geometria, teclado e revisão de capturas não equivalem a
certificação WCAG ou homologação com leitores de tela e tecnologias assistivas reais.

O [checklist de produção](../../10-planejamento-sprints/checklist-producao.md) define o
NO-GO por gate ausente/falho e os itens ainda dependentes da instalação: TLS/domínio reais,
cofre, volumes, grants, custódia e agendamento de backups, alertas externos e medição de capacidade.
O [runbook](../../02-instalacao-e-ambiente/producao-sprint-06.md) detalha recuperação e reconciliação.

Docker Scout 1.24.0 foi encontrado, mas recusou a consulta sem autenticação. Nenhum relatório
de CVEs do SO foi gerado; não se alega ausência de vulnerabilidades de Debian, CPython,
bibliotecas nativas ou navegadores a partir dos scans Python/npm.
