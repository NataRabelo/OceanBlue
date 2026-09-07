# Operacao local dos ciclos financeiros e relacionamento

## Instalacao e permissoes

A Sprint 5 sucede o GO independente da Sprint 4 em `3b0d55db90db815bd2e4d228615a87ffeafb30a0`.
Aplicar `flask --app wsgi db upgrade`. Head `8b9c0d1e2f3a`, 25 revisions, 47 tabelas.
Novas colunas em clientes, vendas, adiantamentos_funcionario, fechamentos_caixa e mensagens_cliente.
O trigger `preserve_ledger` impede DELETE e alteracao dos dados contabilizados de lancamentos_financeiros;
somente a marcacao de reversao e o timestamp de atualizacao podem mudar. Ajustes devem criar contrapartidas.

As permissoes `estornar_financeiro`, `reabrir_caixa`, `autorizar_adiantamento` e
`gerenciar_privacidade_cliente` sao concedidas aos administradores existentes e incluidos no bootstrap de novos tenants.
Outros perfis precisam de concessao explicita pelo administrador. Operacoes HTTP revalidam permissao,
tenant e empresa na sessao vigente e exigem CSRF nas escritas.
Privacidade exige tambem `visualizar_todas_empresas`, pois clientes e carteiras sao compartilhados no tenant.

Migrations retroativas nao reenviam mensagens: as ja confirmadas ficam ENVIADO; todas as demais anteriores
a esta Sprint ficam INCERTO, pois nao ha prova confiavel sobre o transporte anterior.
Adiantamentos anteriores ficam AUTORIZADO, conservando seus efeitos ja contabilizados.
Vendas anteriores ficam marcadas como cashback processado; tentativas de processar novamente sao recusadas.
Fechamentos anteriores conservam valores e recebem revisao 1; o snapshot de conciliacao nasce no proximo ajuste auditado.

Downgrade e reupgrade sao gates de teste em PostgreSQL descartavel. Downgrade remove as novas colunas,
portanto nao deve ser usado como rollback operacional de dados da Sprint 5. Antes de implantacao futura,
realizar backup e planejar restauracao integral em ambiente independente. Esta entrega nao executa deploy.

## Financeiro e caixa

O painel `/api/operacoes/view`, acessivel pelos modulos Financeiro, Clientes e Adiantamentos, permite
acompanhar registros, estornar lancamentos manuais, reabrir e ajustar fechamento, operar vales e privacidade.
Sua visao combinada requer as permissoes de leitura dos modulos consultados; perfis restritos continuam usando
as telas especificas e endpoints autorizados. Uma recusada por permissao e exibida no painel.

Estorno manual cria outro lancamento, de mesmo valor e forma de pagamento, com tipo contrario,
`lancamento_origem_id` e categoria Reversoes formais. O motivo e obrigatorio (5–500 caracteres).
Entradas/saidas de PDV, boleto ou vales precisam do cancelamento de sua origem; nao podem ser estornadas isoladamente.
Lancamento de estorno tambem nao pode ser estornado pelo endpoint manual. Isso evita recompor a origem indevidamente.
IDs, autor, data, valor e motivo ficam na auditoria; nenhuma exclusao e necessaria.

Fechamento segue FECHADO → REABERTO → FECHADO. O cliente deve enviar a revisao lida; revisao antiga
e recusada. Cada operacao incrementa revisao e registra antes/depois, ator, motivo, valores contados
e snapshot de caixa e conciliacao PDV. A diferenca de contagem e preservada, sem criar receita ficticia.
Uma divergencia entre PDV e financeiro impede fechar. Lancamentos posteriores nao reescrevem o snapshot
historico: a leitura mostra tambem a apuracao corrente, para permitir identificacao e ajuste auditado.
O caixa existente continua apurando dinheiro por empresa/dia; a chave de fechamento inclui operador,
mas nao se apresenta esse saldo empresarial como caixa segregado por operador.

A conciliacao seleciona vendas por empresa e periodo local brasileiro. Para cada venda, inclui os IDs
dos lancamentos, liquido PDV, financeiro assinado e diferenca. O liquido considera cancelamentos e a
restituicao proporcional de cashback; nao mistura carteira com dinheiro recebido. Relatorio de fluxo
lista todos os lancamentos no periodo, sem corte silencioso de 1.000 registros. A listagem de tela continua limitada.

## Vales e adiantamentos

Solicitacao PENDENTE nao movimenta caixa nem estoque. AUTORIZAR valida funcionario, estoque e pagamento,
gera a saida e eventual movimento de produto em uma transacao. BAIXAR registra o desconto em folha,
sem uma segunda saida financeira. REVERTER_BAIXA desfaz esse estado; depois ESTORNAR restitui o financeiro
e o produto, com contrapartidas vinculadas. CANCELAR e permitido enquanto PENDENTE.
O estado BAIXADO precisa voltar a AUTORIZADO antes do estorno, para nao deixar desconto de folha residual.

O cadastro usual da tela agora solicita autorizacao; autorizacao/baixa/estorno ficam no painel de ciclos.
A API legada `POST /api/adiantamentos/` conserva a criacao imediatamente autorizada, mas exige as duas
permissoes `criar_adiantamento` e `autorizar_adiantamento`. Ela e uma compatibilidade interna, nao o novo
fluxo recomendado. Servicos internos legados continuam disponiveis para os testes existentes.
O resumo de folha inclui apenas AUTORIZADO e BAIXADO, por competencia e empresas permitidas, sem truncamento.
Salario e uma base cadastral de previsao; nao ha integracao real com folha externa.

## Cashback

Carteira e creditos permanecem no tenant, inclusive quando o cliente compra em mais de uma empresa.
Venda e fila, estoque, financeiro, carteira, credito e idempotencia compartilham a mesma transacao.
O bloqueio transacional por tenant serializa alteracoes concorrentes. O credito por venda tem unicidade
no PostgreSQL; um marcador e hash de payload na venda evitam debito/credito repetido mesmo na chamada direta do servico.
Repeticao identica retorna o resultado; payload diferente e recusado.

Expiracao usa calendario de Sao Paulo: credito vence depois da data de validade (a data e inclusiva).
Cada saldo vencido e zerado com movimento EXPIRACAO, sob o mesmo bloqueio das vendas. Repeticao/concorrencia
nao expira duas vezes. Leituras de carteira e PDV aplicam expiracao; a rotina abaixo permite processar sem acesso de cliente.
Restituicao de credito ja vencido e imediatamente expirada, sem reabrir poder de compra indevido.
Cancelar venda com credito vencido e sem consumo pendente e permitido; credito consumido ainda exige recomposicao antes do cancelamento.

## Fila de comunicacoes e falhas

Toda mensagem recebe `idempotency_key` explicita, unica por tenant/empresa/cliente. Mesmo payload/chave
retorna o registro anterior; divergencia e recusada. Mensagens automaticas usam `venda:ID` e sao enfileiradas
antes do commit da venda. Se INSERT ou commit falhar, nenhum dos efeitos da venda permanece.
A tela conserva a chave em retentativas de uma mesma submissao.

Limites: 1.000 mensagens criadas por empresa em janela de 24 horas, 100 registros por lote do worker,
5 tentativas por mensagem; atrasos de 60, 120, 240, 480 e 960 segundos. FALHOU so entra no lote depois
da proxima tentativa, sem bloquear pendencias posteriores. Conteudo limitado a 10.000 caracteres e assunto a 160.

| Estado | Interpretacao e acao |
|---|---|
| PENDENTE | Persistida, ainda sem tentativa |
| FALHOU | Adaptador recusou antes do aceite; pode tentar novamente depois do backoff |
| ESGOTADO | Atingiu cinco recusas; nenhuma retentativa automatica |
| INCERTO | Claim persistido antes do transporte ou confirmacao perdida; nao reenviar |
| ENVIADO | Adaptador confirmou aceite; nao equivale a leitura pelo destinatario |
| CANCELADO | Consentimento/contato indisponivel, descadastro ou anonimizacao antes do envio |

Antes de cada tentativa o worker relê consentimento, atividade e contato. INCERTO e gravado antes de
chamar o adaptador. Crash antes do envio ou depois do aceite mantem INCERTO: privilegia nao duplicar
em detrimento de entrega automatica. Investigacao operacional deve preservar os registros; a Sprint
nao oferece transicao de INCERTO de volta a PENDENTE e nao promete exactly-once fora do banco.

Depois do claim persistido, o worker readquire o bloqueio transacional do tenant e relê cadastro,
contato, permissao atual do operador e acesso a empresa. Descadastro ou anonimizacao confirmados
nesse intervalo cancelam a entrega sem transporte. Permissao revogada interrompe a tentativa,
conservando INCERTO para investigacao. O bloqueio permanece ate o resultado do transporte: um
descadastro concorrente espera uma tentativa ja iniciada terminar antes de confirmar sua alteracao.
Essa serializacao favorece integridade e pode aumentar latencia por tenant; o adaptador continua bloqueado.

A migration de validacao `9c0d1e2f3a4b` exige contrapartida integral ao confirmar o marcador de
estorno e impede desfaze-lo diretamente. O teste e diferido ate o commit para permitir a gravacao
atomica da origem e sua contrapartida. Vales pendentes revalidam o vinculo ativo do beneficiario
com a empresa na autorizacao. Valores que arredondam para fora de Numeric(12,2) sao recusados.

O adaptador padrao e bloqueado. Simuladores deterministas de sucesso, recusa e timeout so podem ser
injetados em ambiente de testes. O transporte anterior tambem recusa chamadas fora de testing.
Nenhuma configuracao SMTP, WhatsApp, SMS, boleto ou Nota Fiscal habilita provedores reais nesta entrega.

Para uma rodada autenticada local de manutencao:

```sh
flask --app wsgi processar-ciclos --tenant-id 1 --funcionario-id 1
```

Exige funcionario ativo com acesso global, gerenciar_configuracao_cliente e enviar_mensagem_cliente.
A rotina expira cashback e processa pendencias; pode ser acionada pelo scheduler do operador, por exemplo
a cada minuto. Nenhum scheduler produtivo foi instalado, e dados de tenant/funcionario do exemplo devem
ser substituidos por IDs autorizados. Sem scheduler, expiracao por acesso continua ativa e a fila conserva pendencias.

## Privacidade

Exportacao JSON autenticada inclui cadastro, vendas, creditos, movimentos, mensagens e consentimentos
do cliente, sem limitar aos ultimos itens da tela. Resposta autenticada e no-store e o acesso fica auditado.
Descadastro exige booleanos explicitos e motivo, registra antes/depois e cancela pendencias do canal.
Cadastro/edicao geral tambem registram alteracoes de consentimento; o padrao de novos clientes nao presume WhatsApp.

Anonimizacao remove nome original, documento, email, telefones, aniversario, observacao cadastral,
destinatario/conteudo/respostas das mensagens e dados identificadores no cache de respostas de vendas.
O cadastro fica inativo e nao pode ser reativado/editado. IDs, referencias, valores, credito e movimentos
sao preservados; tambem permanecem documentos fiscais historicos e auditoria de operacoes. Esses registros
retidos nao constituem anonimizacao irreversivel de todo o historico; sao retencao operacional vinculada a ID.
Motivos livres e documentos historicos podem conter informacoes informadas pelo operador: o procedimento
nao varre texto livre de toda a contabilidade nem altera documentos sujeitos a obrigacoes de retencao.
Nao inclua novos dados pessoais em motivos. Backups, exportacoes ja baixadas e copias fora do sistema
exigem a politica de retencao do operador, sem exclusao automatica nesta Sprint.

## Reproducao dos gates

```powershell
pwsh -NoProfile -File scripts/validate_sprint05.ps1 -Project oceanblue-s05-repro -EvidenceDirectory docs/evidencias/producao/sprint-05-repro
```

Use projeto novo. O runner constroi imagens, verifica dependencias, inventario, todas as migrations,
schema, testes/cobertura, Chromium real, fontes/imagens, smoke e banco interrompido; remove seus recursos
em finally. PostgreSQL e real, descartavel, em tmpfs, rede interna, sem portas publicadas. Nao aponte testes para dados reais.
