# Integridade de cadastros, estoque e lotes

## Transacoes

Produtos, categorias, funcionarios, seus vinculos, perfis, vendas, cancelamentos e retiradas de produtos por adiantamento possuem uma fronteira transacional de servico. Os repositorios fazem flush enquanto essa fronteira estiver ativa; somente o servico externo confirma. Uma falha desfaz pais, filhos, saldos, financeiro e registros de idempotencia. Chamadas internas com `persistir=False` participam da transacao do chamador.

As escritas desses servicos usam o mesmo bloqueio transacional PostgreSQL por tenant empregado pelas cotas (`pg_advisory_xact_lock(7202, tenant_id)`). Isso serializa operacoes do mesmo tenant, inclusive produtos apresentados em ordens diferentes, sem bloquear tenants distintos. A atualizacao de saldo tambem recarrega e bloqueia exclusivamente a linha de `produtos_empresa` com `FOR UPDATE OF produtos_empresa`; consultas com relacionamentos opcionais nao ampliam o bloqueio aos joins.

Essa escolha prioriza integridade. Um lote grande pode atrasar outras escritas do mesmo tenant ate terminar. O limite continua em 5.000 linhas. Nao ha alegacao de capacidade de carga produtiva. Novos escritores de estoque devem passar pelo servico; SQL arbitrario nao obtem automaticamente o bloqueio da aplicacao.

Alertas e email automatico da venda sao processados depois do commit. Falha de notificacao nao transforma uma venda confirmada em falha transacional. O envio nao constitui uma fila duravel: uma queda de processo depois do commit pode impedir a notificacao. Repetir uma operacao idempotente nao envia novamente.

## Multiempresa

- O produto e um cadastro compartilhado no tenant; preco, atacado, validade, estoque e atividade pertencem ao vinculo com a empresa.
- O botao **Vincular** abre o cadastro de um novo vinculo, com saldo zero. A API existente `POST /api/produtos/` aceita `produto_id`, `empresa_id` e os valores do novo vinculo. Vincular um produto existente nao consome outra vaga da cota de produtos.
- A empresa de um vinculo de produto e imutavel. Para outra empresa, crie um vinculo. Edicao de cadastro nao transfere saldo.
- Desativar um vinculo nao desativa os demais. Excluir vinculo com saldo, movimentacao ou venda e recusado; nesse caso use desativacao. Ao excluir o ultimo vinculo sem historico, o cadastro pai e removido na mesma transacao.
- Funcionarios aceitam `empresa_ids` no POST/PUT existente. A lista substitui o conjunto de vinculos de forma atomica, deve conter pelo menos uma empresa ativa do tenant e incluir `empresa_id`. A interface permite selecao multipla. O ID retornado continua sendo de um vinculo valido, mesmo quando o vinculo anterior foi removido.
- O campo legado `empresa_id` continua aceito sozinho. Na alteracao para outra empresa ele e convertido em substituicao de vinculo, respeitando o escopo imutavel imposto pela Sprint 2.
- Autorizacao e isolamento permanecem os da Sprint 2. Perfil e identidade do funcionario continuam compartilhados no tenant; campos gerais do produto tambem sao compartilhados.

## Validacoes

Categorias exigem nome de 1 a 100 caracteres, descricao de ate 255 e nome unico no tenant. Categoria em uso nao pode ser removida. Produtos exigem nome de ate 150 caracteres e categoria ativa quando informada. O NCM informado deve conter oito digitos, com pontos de formatacao opcionais; nao se realiza consulta fiscal externa.

Valores monetarios devem ser finitos, nao negativos e caber no campo decimal. Atacado nao pode exceder varejo; quantidade minima e positiva. Quantidades fracionarias nao sao convertidas silenciosamente em inteiros. Codigo de barras informado deve conter ate 60 digitos ASCII; a ausencia gera EAN-13. A unicidade no tenant e mantida no banco e as geracoes concorrentes sao serializadas.

## Idempotencia de venda e cancelamento

`criar_venda`, `cancelar_venda` e `cancelar_item_venda` aceitam `idempotency_key` no JSON, com 1 a 128 caracteres. Reutilize exatamente a mesma chave e payload em tentativas da mesma operacao. A identidade persistida combina tenant, funcionario, operacao, IDs de venda/item e chave. A resposta de negocio e armazenada na mesma transacao dos efeitos. Chave repetida com payload diferente e recusada. O acesso a empresa e novamente verificado no replay.

O PDV gera UUID ao preparar a confirmacao da venda e mantem a chave na repeticao da confirmacao. Cancelamentos parciais preservam payload e chave enquanto o resultado esta pendente. As APIs HTTP de criacao de venda e cancelamento parcial exigem a chave; clientes externos devem envia-la. Chamadas internas legadas de servico ainda podem omiti-la, sem promessa de deduplicacao de novas vendas nesse caso. Cancelamento integral e repeticao de reversao manual tambem sao naturalmente idempotentes pelo estado persistido, mesmo sem chave.

Nas respostas com chave, `email_venda.status = PENDENTE` descreve o processamento posterior ao commit e permanece estavel no replay; nao e comprovacao de envio. As consultas e registros de comunicacao conservam o resultado do envio.

Callbacks de estoque de venda exigem o item persistido, com produto e empresa compativeis. Uma baixa por item possui indice unico parcial no banco. Repeticoes nao descontam novamente. Devolucoes exigem baixa original e cancelamento registrado, respeitando a quantidade acumulada cancelada. Uma venda ainda finalizada e sem cancelamento de item nao pode devolver estoque.

## Seis layouts de importacao/exportacao

Os seis formatos do sistema sao layouts XLSX de **categorias, produtos, funcionarios, cupons, formas de pagamento e categorias financeiras**. Nao sao seis extensoes de arquivo. A compatibilidade existente com arquivos XLSM permanece; macros nao sao executadas.

O botao inicialmente pre-valida o arquivo. Um lote sem erros libera a confirmacao; a confirmacao executa novamente as validacoes sob bloqueio, porque os dados podem ter mudado entre as duas etapas. Na API, envie `pre_validar=true` no formulario multipart de `/api/importacao-exportacao/importar` para simular sem gravar.

A pre-validacao usa transacoes aninhadas no banco para exercer as mesmas FKs, cotas e regras da gravacao. Nenhuma linha fica visivel como confirmada. Sequencias de IDs podem avancar mesmo em rollback. Linhas vazias sao ignoradas; cabecalhos repetidos e formulas sao recusados. O leitor limita a quantidade de linhas carregadas. A exportacao grava textos como literais, evitando formulas originadas de nomes cadastrados.

Um erro em qualquer linha desfaz **todo o lote**, inclusive alteracoes de registros existentes, novas categorias automaticas, funcionarios, vinculos e saldo inicial. O relatorio distingue `confirmado`, `pre_validacao`, linhas validas, erros com numero de linha e contagens efetivamente gravadas. `criadas`, `atualizadas` e `sucesso` sao zero quando nao houve gravacao; as acoes simuladas aparecem em `linhas`.

Produtos incluem `valor_varejo`, `valor_atacado` e `quantidade_minima_atacado`; `valor_venda` continua aceito como fallback de varejo. Novos vinculos com saldo inicial geram movimentacao de ajuste. Estoque existente nao pode ser sobrescrito por importacao: omita `estoque_atual` ou informe o saldo atual; divergencia exige movimentacao de estoque. Isso protege vendas ocorridas depois de uma exportacao antiga. Campos cadastrais/precos continuam sendo atualizados pelo lote.

Funcionarios existentes preservam a senha quando a coluna esta vazia. Novos funcionarios exigem senha valida. Exportacoes nunca incluem senha ou hash. CPF e normalizado para evitar duplicacao pela pontuacao; empresa e perfil devem pertencer ao tenant.

## Migration e reproducao

A validacao independente acrescenta a revision `6f7a8b9c0d1e`: CHECKs de finitude para as 47 colunas NUMERIC das 19 tabelas monetarias/configuracoes. `NaN` e infinitos sao recusados inclusive por SQL direto. A migration valida o legado e falha transacionalmente se houver valores invalidos; preserve os registros, investigue a origem e reconcilie-os antes de repetir o upgrade. Ela nao substitui valores invalidos nem apaga historico. Os testes demonstram que o head anterior e os dados permanecem intactos na falha.

O uso de cashback exige cliente identificado. Cancelamentos parciais calculam o valor acumulado proporcionalmente ao bruto devolvido, descontando o valor ja cancelado: o ultimo centavo e compensado ao longo das devolucoes, inclusive quando a mesma mercadoria ocupa varias linhas. Estornos financeiros e restituicoes de cashback respeitam o saldo restante de cada pagamento/credito original. O cashback gerado tambem e reduzido proporcionalmente ao saldo da venda, chegando a zero no cancelamento integral por itens.

A exclusao ou retirada de vinculo de funcionario com historico e recusada; desative o cadastro para preservar autoria e referencias. Atualizar um produto sem enviar `codigo_barras` preserva o codigo existente; o envio explicitamente vazio continua solicitando geracao automatica.

A revision `5e6f7a8b9c0d` cria `operacoes_idempotentes`, com indice, unicidade e trigger de isolamento, e o indice unico de baixa por item. Ela depende da Sprint 2. Duplicidades historicas de baixas impedem a criacao do indice; devem ser investigadas e reconciliadas antes da migracao, sem apagar evidencias. Downgrade remove a memoria de idempotencia: nao repetir requisicoes antigas depois de um downgrade.

Em Docker Linux e PowerShell 7, execute na raiz do checkout:

```powershell
pwsh -NoProfile -File scripts/validate_sprint03.ps1 -Project oceanblue-s03-repro
```

Use um nome de projeto novo. O runner constroi imagens com locks, valida inventario e todas as migrations, executa a suite completa com cobertura minima de 50%, exige JUnit sem falhas/erros/skips, realiza smoke produtivo e banco indisponivel e remove os seus containers em `finally`. As evidencias sao geradas em `docs/evidencias/producao/sprint-03/`. Nao acessa banco produtivo nem integra boleto/Nota Fiscal reais.

Para reproduzir o aceite independente, incluindo os gates negativos da imagem e os testes destrutivos adicionais, execute `pwsh -NoProfile -File scripts/validate_sprint03_adversarial.ps1 -Project oceanblue-s03-validation-repro`. Os artefatos ficam em `docs/evidencias/producao/sprint-03-validacao/`; execucoes posteriores substituem os arquivos de aceite nessa pasta. Os seis formatos referem-se aos seis layouts XLSX descritos acima. Nenhuma integracao real e habilitada pelo runner.
