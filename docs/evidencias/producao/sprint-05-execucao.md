# Sprint 5 — execucao de financeiro e relacionamento

Data: 2026-09-07, America/Sao_Paulo. Execucao exclusivamente local.

## Decisao

**GO de execucao local da Sprint 5, pronta para a validacao destrutiva independente. Zero falhas
criticas ou altas conhecidas abertas no escopo implementado e exercitado.** O pipeline integral
aprovou 465 testes, sem falhas, erros ou skips, cobertura combinada de 72,46%, migrations,
imagem produtiva, smoke, falha real de banco e correspondencia de 273 arquivos de fonte.
Este GO nao substitui o aceite independente e nao autoriza push, deploy ou ativacao de provedores.

## Base e isolamento

Worktree inicialmente limpo e destacado em `352a77c7d39836e57b6d9f366d3fc7a83d0a3f3b`.
Antes de qualquer alteracao, fast-forward para a main local validada
`3b0d55db90db815bd2e4d228615a87ffeafb30a0`. Lidos os resultados/decisoes das Sprints 1–4,
incluindo o GO independente de `sprint-04-validacao.md` e suas 413 provas anteriores.
Nenhum fetch remoto foi necessario, e a main permaneceu nesse commit durante a execucao.

Projetos Compose exclusivos: `oceanblue-s05-dev` (iteracao), `oceanblue-s05-final` (primeira rodada
integral interrompida para incorporar revisao) e `oceanblue-s05-accept` (aceite final).
PostgreSQL 16.12 real em tmpfs, redes internas, sem portas publicadas e sem mount do checkout
nos containers de teste. Imagens construidas com dependencias fixadas e hashes existentes.
Dados, documentos, contatos e credenciais usados nas provas sao sinteticos.
Os servicos preexistentes `blueocean_db`, `wnr_triagem_api` e `wnr_triagem_db` nao foram alterados.

Nao houve push, deploy, contato com provedores externos, emissao bancaria/fiscal, publicacao de
mensagens ou execucao remota de CI. A validacao destrutiva independente permanece para a tarefa seguinte.

## Gates de aceite

| Gate | Resultado observado em `sprint-05-execucao/final/` |
|---|---|
| Runner | Exit 0; projeto exclusivo oceanblue-s05-accept; limpeza em finally |
| Dependencias/inventario | pip check em teste e producao; 160 rotas conferidas |
| Migrations | 25 revisions, head 8b9c0d1e2f3a; upgrade individual, downgrade base, reupgrade e tenant sentinela |
| Schema | 47 tabelas; colunas, tipos, indices e FKs compativeis com modelos |
| Regressao integral | **465 aprovados**, 0 falhas/erros/skips; JUnit 662,019 segundos |
| Casos novos | 51 casos em test_sprint05_cycles.py e 1 E2E em test_sprint05_browser.py; 413 casos anteriores preservados |
| Cobertura de linhas | 8.676/11.457 = 75,73% |
| Cobertura de ramos | 1.500/2.586 = 58,00% |
| Cobertura combinada | 10.176/14.043 = **72,46%**; gate de 50% mantido |
| Navegador | Cinco cenarios Chromium 140.0.7339.16 / Playwright 1.55.0, Gunicorn e PostgreSQL reais; zero erros JS e zero requisicoes externas |
| Imagem produtiva | UID 1000, default production, quatro variaveis obrigatorias ausentes recusadas antes de acesso ao banco |
| Smoke | Entrypoint, migrations e Gunicorn aprovados; health/readiness HTTP 200; proxy forjado recusado com 403 |
| Banco realmente interrompido | Health 200, readiness 503, login falha fechado sem emitir sessao |
| Fontes | 273 arquivos identicos byte a byte ao checkout; nenhuma fonte executavel mudou depois do build final |
| Limpeza | Zero containers/redes dos tres projetos da Sprint 5; servicos preexistentes preservados |

Imagem de teste: `sha256:911e78aca5b6e2fe786fe5afa31c75323e3295aa74c0cdeccfe5f2de684ce2b6`.
Imagem produtiva: `sha256:b2d581913deed102e29c0843665662e6d3ce1fe92319b89b70212360baf4c52f`.
Docker Engine 29.7.2; Python 3.12.12; PostgreSQL 16.12. A instalacao e as bases continuam nos locks/digests do repositorio.

Artefatos principais: [JUnit](sprint-05-execucao/final/junit.xml), [cobertura](sprint-05-execucao/final/coverage.xml),
[pipeline](sprint-05-execucao/final/pipeline.txt), [smoke](sprint-05-execucao/final/smoke.txt),
[banco interrompido](sprint-05-execucao/final/database-outage.txt),
[fontes](sprint-05-execucao/final/source-check.txt), [E2E](sprint-05-execucao/final/e2e/),
[limpeza](sprint-05-execucao/cleanup-check.txt) e [hashes SHA-256](sprint-05-execucao/sha256sums.txt).
O screenshot do novo ciclo foi inspecionado: campos e acoes legiveis apos os ajustes locais de contraste.

## Entrega e rastreabilidade

A [matriz requisito → rota → servico → teste](../../04-modulos-e-funcionalidades/ciclos-financeiros-relacionamento.md)
cobre as areas abaixo. O [inventario CSV](../../04-modulos-e-funcionalidades/inventario-requisito-rota-servico-teste.csv)
lista 160 rotas, preservando a ressalva de que descoberta estatica nao equivale a cobertura HTTP integral.

| Area | Comportamento implementado |
|---|---|
| Financeiro | Contrapartidas de estorno vinculadas, sem exclusao; trigger PostgreSQL protege valor/identidade do lancamento; idempotencia e autoria/motivo auditados |
| Caixa | FECHADO/REABERTO, controle de revisao, ajuste de valores contados, snapshot de reconciliacao e antes/depois; divergencia PDV/financeiro impede fechamento |
| Conciliacao | Vendas por empresa/periodo, centavos, cashback restituido, financeiro assinado e IDs de origem; fluxo integral sem corte silencioso de 1.000 registros |
| Adiantamentos | Solicitacao sem efeitos, autorizacao atomica, dinheiro/produto, baixa em folha, reversao de baixa, cancelamento pendente e estorno financeiro/estoque; resumo por competencia |
| Cashback | Marcador/hash por venda, credito unico, serializacao por tenant, consumo e devolucoes, expiracao automatica concorrente e cancelamento de credito vencido sem consumo |
| Mensagens | Fila antes do commit da venda; chave/payload, estados persistentes, cinco tentativas, backoff, limite de lote e diario; claim INCERTO antes de transporte e sem retentativa ambigua |
| Consentimento | Opt-in relido a cada tentativa, descadastro cancela pendencias, auditoria dedicada e tambem nas alteracoes cadastrais gerais |
| Privacidade | Exportacao autenticada de cadastro/historicos, anonimizacao de dados operacionais e respostas em cache; preservacao de referencias financeiras e documentos historicos |
| Interface | Novo painel de ciclos, links nos tres modulos, solicitacao de vale na tela existente, chave persistida nas retentativas de formulario e estados da fila |
| Operacao | CLI autenticada para expiracao e fila, adaptador bloqueado por padrao, simuladores deterministas apenas em testing, guia operacional com limites e retencao |

Nova migration `8b9c0d1e2f3a_sprint05_lifecycles.py`, sucedendo `7a8b9c0d1e2f`.
Nao cria tabelas: acrescenta colunas em clientes, vendas, adiantamentos_funcionario, fechamentos_caixa
e mensagens_cliente; constraints de estado/tentativas/chave, trigger de preservacao do financeiro
e quatro permissoes. As 47 tabelas existentes permanecem; sentinelas e comparacao de metadata fazem parte do runner.
O upgrade conserva mensagens antigas sem confirmacao como INCERTO, adiantamentos antigos como AUTORIZADO
e vendas antigas como cashback ja processado. Downgrade e destinado a teste descartavel, pois remove
os novos campos de controle; nao e procedimento de rollback operacional de dados novos.

## Achados e correcoes durante a execucao

| Achado | Correcao/prova |
|---|---|
| Mensagem enviada durante gravacao podia escapar de rollback; callback de venda podia perder fila | Fila criada na transacao da venda, sem transporte; falha apos INSERT real reverte venda, estoque, financeiro e cashback; gateway so roda depois |
| Vales nao distinguiam aprovacao, desconto em folha e estorno | Estados e revisoes, efeitos somente na autorizacao, baixa sem segunda saida, reversao de baixa obrigatoria antes de estorno |
| Identificadores de financeiro/vales truncavam fracionados e aceitavam booleanos; quantidade removia pontuacao | Conversao estrita; dez casos invalidos mais valores NaN/infinitos/zero arredondado/limites recusados sem efeitos |
| Fluxo e folha truncavam silenciosamente em 1.000 registros | Relatorios sem limite de tela; 1.002 lancamentos conferem total e quantidade |
| Expiracao podia concorrer com uso da carteira | Mesmo bloqueio transacional das vendas; tres sessoes expiram uma vez; compra com saldo vencido recusada |
| Cashback vencido sem consumo impedia cancelar a venda | Cancelamento conserva carteira zerada e conciliacao correta; casos integral e parcial |
| Resposta idempotente conservava nome/documento apos anonimizacao | Cache de respostas e conteudo/destinatario das mensagens saneados junto ao cadastro; replay nao revela os dados removidos |
| Retentativas aguardando backoff podiam ocupar todo o lote antes de pendencias elegiveis | Filtro de vencimento aplicado antes do limite do lote |
| Cadastro comum mudava consentimento sem evento especifico | Auditoria de antes/depois tambem em criar/atualizar cliente |
| Trigger de preservacao emitia categoria generica de erro | SQLSTATE 23514, consistente com erro de integridade e com os testes PostgreSQL anteriores |
| Primeira inspecao visual revelou campos sem contraste | Estilos locais dedicados e contraste dos inputs/botoes corrigidos; navegador do aceite captura o resultado final |

As quatro provas legadas de mensagens foram adaptadas ao contrato de fila, mantendo verificacoes de
sucesso/falha, elegibilidade e rollback e acrescentando processamento posterior pelo simulador.
Nenhum caso foi removido, desabilitado, marcado como skip/xfail ou usado para reduzir o gate de cobertura.

## Iteracoes preservadas

Arquivos em [sprint-05-execucao/](sprint-05-execucao/):

- `iteracoes/oceanblue-s05-probe.txt`: 124 aprovados, uma expectativa legada de callback sincrono falhou.
- `iteracoes/oceanblue-s05-cycles.txt`: 58 aprovados, tres expectativas antigas de envio imediato/chave ausente falharam.
- `iteracoes/oceanblue-s05-retest.txt`: 112 aprovados; E2E esperava cliente anonimizado ainda na lista de ativos.
  Banco e HTTP o removiam corretamente; a expectativa visual foi corrigida para lista vazia.
- `iteracoes/oceanblue-s05-expanded.txt`: 52 novos casos aprovados, com cashback, falhas, concorrencia, privacidade e navegador.
- `iteracoes/e2e/`: trace, screenshot, HTML e diagnostico do Chromium dessa rodada; anterior ao ajuste final de estilos.
- `pipeline.txt` na raiz: primeira rodada integral, interrompida intencionalmente com exit 137 apos migrations
  e testes iniciais, para incorporar auditoria geral de consentimento e SQLSTATE do trigger. Nao e prova de aceite.
- `final/`: rodada integral efetiva, em outro PostgreSQL vazio, com imagens construidas novamente.
- `cleanup-dev.txt`, `javascript.txt` e manifesto SHA-256: limpeza e verificacoes adicionais.

O Compose pode emitir erro ao tentar parar containers de teste ja encerrados; a ausencia de recursos
e conferida depois de remove-los. Erros SQL esperados de ataques constam nos logs e nao equivalem a
falhas de teste; a decisao utiliza JUnit e os gates do runner.

## Reproducao e limites

```powershell
pwsh -NoProfile -File scripts/validate_sprint05.ps1 -Project oceanblue-s05-repro -EvidenceDirectory docs/evidencias/producao/sprint-05-repro
```

Docker Linux e PowerShell 7; usar nome de projeto livre e diretorio novo. O runner reutiliza os gates
da Sprint 4, sem omitir suites: dependencias, inventario, migrations, schema, pytest/cobertura,
Chromium/Gunicorn, correspondencia de fontes, imagem produtiva, smoke e banco desligado.

O aceite e local. Nao comprova carga produtiva, navegadores diferentes do Chromium empacotado,
homologacao de provedores, caixa final de email ou funcionamento de scheduler produtivo.
Nao promete exactly-once no transporte: INCERTO fica bloqueado e exige investigacao operacional.
A CLI e a expiracao por acesso estao implementadas; nenhum scheduler foi instalado.
Anonimizacao cobre cadastro, mensagens e cache de resposta operacional, preservando IDs, valores,
documentos historicos e auditoria. Textos livres historicos, backups e exportacoes externas exigem
politica de retencao do operador; nao se declara anonimato irreversivel de todo o historico.

O [guia operacional](../../02-instalacao-e-ambiente/operacao-sprint-05.md) descreve permissoes,
estados, limites e procedimentos. O commit local sera informado ao encerrar, sem autoreferencia circular neste documento.
