# Sprint 4 — execucao de PDV, cupons e alertas

Data: 2026-09-07, America/Sao_Paulo. Execucao local concluida; pronta para validacao independente. Este relatorio nao constitui GO independente nem autorizacao de deploy.

## Base, escopo e isolamento

Worktree inicialmente limpo e destacado em `352a77c`. Antes da implementacao, sincronizado exclusivamente com a main local `0195d314feb7b82eb0522baa63c13b914e597007`, que permaneceu inalterada. Lidos os relatorios de execucao e validacao das Sprints 1, 2 e 3; confirmado o GO em `sprint-03-validacao.md`, com 291 testes aprovados. O CI anterior `34077141538` foi informado pela coordenacao; nao foi consultado ou reexecutado remotamente nesta entrega.

Nenhum fetch, push, merge, deploy, emissao real de boleto ou Nota Fiscal. Testes em PostgreSQL 16.12 real, tmpfs, redes Compose internas e dados sinteticos; sem portas publicadas ou mounts do codigo. Projetos utilizados: `oceanblue-s04-dev` e `oceanblue-s04-final`. Seus containers e redes foram removidos; containers preexistentes foram preservados, inclusive servicos anteriormente parados ou reiniciando.

## Gates finais

| Gate | Resultado observado |
|---|---|
| Dependencias e inventario | `pip check` aprovado nas imagens de teste e producao; 149 rotas conferidas |
| Migrations | 24 revisions, head `7a8b9c0d1e2f`; upgrade individual, downgrade ate base, reupgrade e sentinelas aprovados |
| Schema | 47 tabelas; tipos, indices e chaves estrangeiras compativeis com os modelos |
| Regressao completa | **365 testes aprovados**, zero falhas, erros ou skips; JUnit: 499,474 segundos |
| Casos novos | 71 casos operacionais/adversariais e 3 E2E reais; os 291 anteriores permanecem habilitados |
| Cobertura | 8.057/10.958 linhas e 1.369/2.472 ramos; combinado 9.426/13.430 = **70,19%**; gate de 50% preservado |
| Navegador | Chromium 140.0.7339.16, Playwright 1.55.0, Gunicorn com dois workers e PostgreSQL real; zero erros JavaScript e requisicoes externas nos tres E2E |
| Imagem de producao | Usuario UID 1000, default production, quatro variaveis obrigatorias recusadas individualmente antes da conexao ao banco |
| Smoke HTTP | Entrypoint/migrations/Gunicorn aprovados; health e readiness 200; proxy forjado recusado com 403 |
| Indisponibilidade real | Banco parado pelo runner: health 200, readiness 503, login falha fechado e nao emite sessao |
| Correspondencia de codigo | **257 arquivos identicos byte a byte** entre checkout e imagem testada, incluindo fontes, testes, migrations, scripts e locks |
| Limpeza | Recursos dos dois projetos removidos; nenhum recurso preexistente removido |

Imagem de teste: `sha256:470875ac42e52644fa7b7310ff6993a3a80c0a253b7c6fd658d3c82f96776b4e`.

Imagem de producao: `sha256:d39a5309ec258357b4e0e549c19b7be756bf66646fc04d6de332a0617383b42c`.

## Entrega e provas por requisito

| Area | Implementacao e prova reproduzivel |
|---|---|
| Precos | Varejo, atacado e automatico calculados pelo servidor; quantidade minima considera linhas repetidas do mesmo produto. Testes de modalidades, precos adulterados e quantidades invalidas; alternancia real na UI |
| Centavos e pagamentos | Entradas e desconto percentual usam ROUND_HALF_UP; recusa NaN, infinito, quantidades fracionadas, pagamento que arredonda a zero e somas divergentes. Venda total zero exige pagamentos vazios. Dinheiro mais Pix conciliados no E2E |
| Desconto autorizado | Sem permissao: zero manual; `aplicar_desconto`: ate 10%; `autorizar_desconto`: ate 100%. API valida os limites, UI informa/desabilita, migration concede somente aos administradores existentes |
| Cupons | Inicio/validade inclusivos no calendario brasileiro; empresa, cliente, limite global e por cliente, subtotal minimo e teto de desconto. Cadastro real pela UI, validacao HTTP/servico e constraints PostgreSQL |
| Concorrencia de cupom | Quatro vendas disputam ultimo uso: uma vencedora. Tres vendas disputam limite por cliente. Contagem global nao pode ser reduzida pelo filtro de empresas do operador. Rollback nao consome uso; replay nao duplica |
| Idempotencia | E2E deixa o servidor concluir a venda e descarta a primeira resposta HTTP; segunda tentativa usa exatamente o mesmo payload/chave e encontra uma unica venda. Regressao anterior de concorrencia e chaves preservada |
| Cancelamento | Devolucao parcial por quantidade e integral dos saldos restantes, atomicas e idempotentes. Falha injetada no estorno integral apos parcial nao deixa efeitos; retry/replay preservam centavos e estoque |
| Reimpressao | Tres leituras do comprovante comparadas por snapshots de banco sem efeitos de negocio; popup real no E2E. Comprovante inclui cashback usado/gerado e valor cancelado |
| Estoque e validade | Fila persistente na mesma transacao do movimento/venda; baixo estoque, ruptura e validade. Fronteiras ontem/hoje/+30/+31 dias e concorrencia de tres workers; unicidade por evento/empresa/destinatario |
| Resumo diario | Uma entrega por empresa/dia/destinatario quando habilitado, com contagens completas. Botao de processamento e comando CLI; chamadas repetidas nao duplicam |
| Historico e retentativa | Estados PENDENTE/ENVIADO/FALHOU/INCERTO, tentativas, destinatario, conteudo e erro publico persistidos. Falha de um destinatario nao reenvia aos demais; quatro retries concorrentes enviam uma vez |
| Falhas da fila/transporte | Insert da fila falha junto com a venda; perda do callback apos commit conserva pendencia recuperavel pela CLI. Timeout e falha de commit da confirmacao preservam INCERTO, bloqueando duplicacao |
| Isolamento | Historico/processamento/retry exigem permissao e empresa autorizada; escritas exigem CSRF. Constraints recusam escopo inconsistente e valores invalidos. Migration recusa legado invalido sem perda de dados |
| WhatsApp | Explicitamente desativado na UI, configuracao HTTP e dispatcher; nao ha promessas de envio. Dados historicos de contato preservados |

Os testes novos estao em `tests/test_sprint04_operations.py` e `tests/test_sprint04_browser.py`. O inventario de requisito/rota/servico/teste foi regenerado e validado, sem remover gates anteriores.

### Conciliacao observada no navegador

Nos dois cenarios (sem e com cashback), tres unidades somam R$ 30,00 no varejo ou R$ 24,00 no atacado/automatico. Cupom de 10% resulta em R$ 21,60, pagos com R$ 5,00 em dinheiro e R$ 16,60 em Pix. A resposta perdida nao cria segunda venda ou segunda baixa: estoque inicial 6 passa a 3.

A devolucao de uma unidade estorna R$ 7,20 e retorna o estoque a 4. O cancelamento dos saldos restantes deixa a venda CANCELADA, estoque 6 e soma assinada dos lancamentos financeiros igual a zero. Com cashback ativo, o credito inicial de R$ 2,16 e o saldo da carteira terminam zerados. A regressao das Sprints anteriores continua verificando rateios extremos, cashback consumido e concorrencia transacional.

O terceiro E2E cadastra cupom com regras na interface, executa alertas/resumo, visualiza falhas por SMTP propositalmente nao configurado, retenta uma entrega, confirma incremento de tentativas e verifica que repetir a rotina nao duplica a fila. Nenhum provedor externo foi contactado; sucesso, rejeicao e ambiguidade SMTP sao simulados nos testes de servico, enquanto HTTP, navegador, transacoes e banco sao reais.

## Correcoes descobertas durante a execucao

- A criacao de cupom era adicionada a sessao antes de validar/atribuir a empresa; um autoflush inseria escopo nulo e a atualizacao posterior violava o trigger de imutabilidade. Regras agora sao aplicadas antes de adicionar o modelo, dentro da transacao.
- O modal generico apagava valores iniciais depois do hook de abertura, removendo a validade sugerida do cupom. A limpeza agora antecede o hook; cadastro real pelo navegador passou.
- A contagem ORM de usos de cupom global podia ocultar vendas de outras empresas nao visiveis ao operador. Contagem explicita por tenant/cupom preserva o limite global, comprovado por HTTP.
- A entrega concorrente precisava atualizar o objeto ja presente na sessao ao adquirir o bloqueio. `populate_existing()` impede retries com estado antigo de reenviar a mensagem.
- Recursos de CDN impediam uma UI funcional na rede isolada. Tailwind e Lucide foram fixados, compilados e versionados localmente com licencas; os E2E recusam qualquer requisicao externa.

As primeiras execucoes tambem expuseram expectativas incorretas dos testes: separador decimal do comprovante, nome da configuracao de cashback, tipo de excecao PostgreSQL por overflow e contagem de resumos incluindo a segunda empresa. As fixtures/assertions foram corrigidas, sem suprimir casos. Logs das falhas e retestes estao preservados. Retestes intermediarios: 81 casos anteriores e depois 68 casos novos aprovados; seis casos adicionais completaram os 74 novos da regressao final.

## Politicas e limites operacionais

- Cancelamentos preservam o uso historico do cupom; cupom utilizado nao pode ser excluido. Alteracao de empresa do cupom nao e permitida. Regras opcionais omitidas em edicao sao preservadas.
- Alertas de estoque respeitam cooldown de 12 horas e limite por estado/produto/dia; validade usa produto/data de validade/dia. A fila registra cada destinatario separadamente.
- Antes de contactar SMTP, a entrega e gravada como INCERTO. Ambiguidade, crash ou perda de confirmacao exigem conciliacao com o provedor; nao se afirma exactly-once nem entrega na caixa final. Reenvio automatico/manual de INCERTO fica bloqueado.
- A tela mostra os 200 registros mais recentes; os demais continuam persistidos. Resumos usam contagens completas, nao o limite visual de produtos do painel.
- A rotina diaria e executavel pelo botao ou CLI. Nenhum scheduler produtivo foi instalado. Homologacao SMTP externa, carga produtiva e validacao independente ficam fora deste aceite local.
- WhatsApp permanece desativado; integracoes reais de boleto e Nota Fiscal continuam bloqueadas. Simuladores anteriores nao foram convertidos em integracoes reais.
- Playwright e dependencias Python possuem versoes/hashes fixados. Dependencias de sistema do Chromium sao resolvidas pelo repositorio Debian no build; nao se promete reproducibilidade binaria desses pacotes.

Contratos e operacao detalhados: [operacao-sprint-04.md](../../02-instalacao-e-ambiente/operacao-sprint-04.md).

## Reproducao e artefatos

Em checkout desta entrega, com Docker Linux e PowerShell 7, usando nome de projeto ainda livre:

```powershell
pwsh -NoProfile -File scripts/validate_sprint04.ps1 -Project oceanblue-s04-repro
```

O runner constroi imagens, executa todos os gates, coleta artefatos, compara fontes e remove seus recursos em `finally`. Para executar a rotina de alertas no ambiente configurado:

```sh
flask --app wsgi processar-alertas --tenant-id 1
```

Evidencias em [sprint-04-execucao/](sprint-04-execucao/):

- [pipeline.txt](sprint-04-execucao/pipeline.txt), [junit.xml](sprint-04-execucao/junit.xml) e [coverage.xml](sprint-04-execucao/coverage.xml): migrations, inventario e regressao final. Erros SQL esperados dos testes destrutivos constam no log; o resultado JUnit e zero falhas.
- [e2e/](sprint-04-execucao/e2e/): por cenario, `trace.zip`, `screen.png`, `page.html`, `browser.json` e `server.log`. Screenshots finais de PDV e configuracao de alertas inspecionados visualmente; versao, erros e requisicoes externas registrados.
- [source-image.json](sprint-04-execucao/source-image.json), [source-check.txt](sprint-04-execucao/source-check.txt), [images.txt](sprint-04-execucao/images.txt) e `build.txt`: identidade das imagens e fontes efetivamente executadas.
- [smoke.txt](sprint-04-execucao/smoke.txt), [security-smoke.txt](sprint-04-execucao/security-smoke.txt), [database-outage.txt](sprint-04-execucao/database-outage.txt), `smoke-startup.txt` e arquivos `image*.txt`: gates produtivos locais.
- `iteration-services.txt`, `iteration-browser.txt`, `iteration-retest.txt`, `retest-68.txt` e `retest-81.txt`: falhas intermediarias e retestes, nao confundidos com a execucao final verde.
- [cleanup.txt](sprint-04-execucao/cleanup.txt), [cleanup-dev.txt](sprint-04-execucao/cleanup-dev.txt) e [cleanup-check.txt](sprint-04-execucao/cleanup-check.txt): limpeza dos recursos isolados.
- [sha256sums.txt](sprint-04-execucao/sha256sums.txt): hashes dos artefatos, inclusive traces e screenshots. Dados e credenciais presentes nos artefatos sao exclusivamente sinteticos de teste.

A entrega fica registrada em commit local descendente direto de `0195d31`; o hash final e informado no encerramento da tarefa, sem auto-referencia circular neste documento.
