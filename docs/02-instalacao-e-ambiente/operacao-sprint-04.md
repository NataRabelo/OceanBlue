# PDV, cupons e alertas — Sprint 4

## Precos, pagamentos e devolucoes

Identificadores de empresa, produto, cliente e forma de pagamento exigem inteiros positivos; booleanos e numeros fracionados sao recusados sem truncamento. O subtotal do carrinho e somado em centavos inteiros antes da comparacao com o minimo do cupom, inclusive para combinacoes como 0,10 + 0,70 = 0,80.

O servidor sempre consulta o preco cadastrado na empresa; `valor_unitario` enviado pelo navegador nao substitui a tabela. `VAREJO` usa varejo; `ATACADO` exige preco menor e quantidade minima; `AUTOMATICO` escolhe por produto. Linhas repetidas do mesmo produto somam quantidades para verificar o minimo de atacado, preservando os itens originais para devolucao. Quantidades sao inteiras positivas.

Dinheiro e persistido em NUMERIC/Decimal com dois decimais. Entradas do PDV e descontos percentuais de cupom usam ROUND_HALF_UP. A interface arredonda o cupom em centavos antes de calcular pagamentos. Rateios de devolucao mantem o algoritmo cumulativo validado na Sprint 3: cada centavo e conservado, inclusive pagamentos de um centavo, descontos quase totais e cashback consumido de varios creditos. Nenhum pagamento pode arredondar para zero; o somatorio precisa ser exatamente igual ao total. Venda com total zero exige lista de pagamentos vazia.

`aplicar_desconto` autoriza desconto manual ate 10% do subtotal; `autorizar_desconto` autoriza ate 100%, incluindo as dependencias da primeira permissao. Sem elas, desconto manual e zero. O limite e arredondado ao centavo e nunca permite que manual mais cupom exceda o subtotal. A migration concede as duas permissoes somente aos perfis administrador; administradores podem atribui-las explicitamente a outros perfis. A API reconsulta permissoes a cada requisicao. O campo do PDV fica desabilitado sem autorizacao.

POST `/api/pdv/vendas` e POST `/api/pdv/vendas/<venda>/itens/<item>/cancelar` exigem `idempotency_key`, preservada em falhas de rede. O navegador permite informar a quantidade a devolver. POST `/api/pdv/vendas/<venda>/cancelar` aceita chave; tambem e idempotente pelo estado final quando chamada sem chave. Apos uma devolucao parcial, o cancelamento integral devolve apenas os saldos restantes, na mesma transacao. As janelas de cancelamento configuradas continuam aplicadas, incluindo a janela por item para os saldos restantes. GET `/api/pdv/vendas/<venda>/comprovante` apenas le dados e informa desconto, cashback e valor cancelado; reimprimir nao cria vendas, pagamentos ou movimentos.

## Cupons

O cadastro e edicao HTTP/UI mantem `nome`, `codigo`, `data_validade`, `tipo_desconto`, `valor_desconto` e `ativo`, acrescentando:

| Campo | Regra |
|---|---|
| `data_inicio` | Opcional; inicio e validade inclusivos, calendario America/Sao_Paulo |
| `empresa_id` | Opcional: todas as empresas do tenant; quando presente, somente a empresa indicada. Imutavel apos criacao |
| `cliente_id` | Opcional: todos os clientes; quando presente, somente o cliente indicado |
| `limite_usos` | Inteiro positivo opcional; limite historico global por cupom |
| `limite_por_cliente` | Inteiro positivo opcional; exige cliente identificado na venda |
| `valor_minimo` | Subtotal minimo antes dos descontos; default zero |
| `desconto_maximo` | Teto monetario positivo opcional sobre o desconto do cupom |

Campos opcionais vazios removem a respectiva regra, salvo empresa imutavel. Campos novos omitidos em atualizacao preservam seu valor. Percentual deve estar entre zero exclusivo e 100 inclusivo; desconto fixo e limitado ao subtotal. Codigo e normalizado em maiusculas no cadastro e no PDV. A listagem distingue cupons agendados, expirados e inativos. O servidor valida novamente todas as regras ao finalizar, mesmo que a lista do navegador esteja antiga.

Criacao, alteracao e consumo usam o bloqueio transacional por tenant da Sprint 3. A ultima utilizacao concorrente tem uma unica vencedora. A contagem global usa SQL explicito com tenant/cupom para que o filtro de empresas do operador nao esconda usos em outras lojas. Falhas da venda nao consomem uso. Replays nao consomem novamente. Cancelamentos preservam o uso historico; cupons utilizados nao podem ser excluidos, apenas desativados. A migration recusa dados legados invalidos sem saneamento automatico.

## Alertas, historico e retentativa

Recusas de TLS e autorizacao do destino anteriores ao transporte sao identificadas explicitamente como falhas seguras (`FALHOU`). Depois de corrigir a configuracao, permitem retentativa; uma excecao generica de permissao durante o transporte continua incerta.

As entregas de estoque sao persistidas na tabela `entregas_alerta` na mesma transacao da venda ou movimento. Cada destinatario tem uma entrega independente, com chave unica por tenant/empresa/evento/destino. Estoque baixo e ruptura preservam cooldown de 12 horas e sao limitados a uma entrega por estado/produto/dia. Validade gera uma entrega por produto/data de validade/dia, incluindo produtos vencidos e proximos do vencimento. Repetir o processamento, inclusive em concorrencia, nao duplica registros ou envios confirmados.

O envio ocorre depois do commit. Antes de contactar SMTP, a entrega fica duravelmente `INCERTO`, impedindo que outro worker a envie simultaneamente. Sucesso confirmado muda para `ENVIADO`. Configuracao ausente, validacao recusada, conexao recusada ou destinatario rejeitado mudam para `FALHOU` e permitem retentativa. Timeout, perda de confirmacao ou crash apos a tentativa permanecem `INCERTO`; reenvio automatico e manual ficam bloqueados para evitar duplicacao. Uma entrega incerta exige conciliacao operacional com o provedor: SMTP nao oferece garantia de exactly-once. O sistema nao afirma que aceito pelo servidor SMTP equivale a leitura ou entrega na caixa final.

O historico persistido conserva assunto, destinatario, conteudo, estado, quantidade de tentativas, erro publico e datas. A tela mostra as 200 entregas mais recentes da empresa selecionada e botao de retentativa somente para pendentes/falhas. Registros mais antigos permanecem no banco. Falha de um destinatario nao reenvia mensagens confirmadas para os demais. Erros de transporte nao sao expostos integralmente no historico.

| Contrato HTTP | Uso |
|---|---|
| GET `/api/estoque/notificacoes/historico?empresa_id=...` | Historico da empresa autorizada |
| POST `/api/estoque/notificacoes/processar` com `empresa_id` | Verifica estoque/validade e enfileira resumo do dia quando habilitado |
| POST `/api/estoque/notificacoes/<id>/retentar` | Retenta somente entrega pendente ou falha segura |

Essas rotas exigem `gerenciar_alerta_estoque`, sessao operacional e CSRF nas escritas. A tela de alertas oferece os mesmos comandos. Configuracao SMTP continua exigindo TLS, hosts autorizados e protecoes contra destinos internos conforme Sprint 2.

Para processamento periodico, o operador executa, no ambiente da aplicacao:

```sh
flask --app wsgi processar-alertas --tenant-id 1
```

A rotina percorre empresas ativas do tenant, gera alertas e um resumo por empresa/dia quando `resumo_diario` esta habilitado, e recupera entregas pendentes/falhas. Pode ser chamada repetidamente por um scheduler externo. Nenhum scheduler produtivo e instalado nesta entrega; a execucao e reproduzivel tambem pelo botao da interface. O resumo inclui contagens completas, mesmo quando o painel visual limita a lista de produtos a 12 itens por categoria.

WhatsApp esta explicitamente desativado: controles de habilitacao/remetente/token foram removidos, o canal nao e oferecido para novas mensagens, tentativas HTTP de habilitacao e transporte direto sao recusadas. Dados historicos e preferencias de contato dos clientes sao preservados. Integracoes reais de boleto/Nota Fiscal continuam bloqueadas; os simuladores internos anteriores permanecem separados.

## Reproducao da verificacao

```powershell
pwsh -NoProfile -File scripts/validate_sprint04.ps1 -Project oceanblue-s04-repro
```

Exige Docker Linux e PowerShell 7; o nome do projeto deve estar livre. O runner constroi imagens sem mounts, valida dependencias, inventario, migrations individuais/ida-volta/schema, executa toda a suite e os E2E com Chromium contra Gunicorn e PostgreSQL reais dentro da rede interna, coleta JUnit/cobertura/traces/screenshots, compara hashes do codigo com a imagem, executa smoke e indisponibilidade real do banco e remove seus recursos em `finally`. Nao publica portas nem usa bancos existentes.

Playwright 1.55.0 e dependencias de teste sao fixados com hashes no lock; o Chromium correspondente e instalado apenas na imagem de testes. Pacotes de sistema exigidos pelo navegador sao resolvidos pelo repositorio Debian durante build. Os recursos visuais de Tailwind 3.4.17 e Lucide 0.468.0 ficam versionados localmente, com licencas: nenhuma dependencia de CDN durante uso ou E2E. Para regenera-los apos alteracoes de classes:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run build:ui
```

Artefatos de navegador usam dados sinteticos e contêm snapshots das paginas de teste. O aceite local nao substitui homologacao de provedores externos, carga produtiva nem validacao independente.
