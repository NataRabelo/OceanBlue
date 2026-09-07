# Financeiro, vales, clientes e comunicacoes — Sprint 5

Esta especificacao complementa o inventario gerado de 160 rotas. Contratos, estados, limites,
retencao e comandos estao no [guia operacional](../02-instalacao-e-ambiente/operacao-sprint-05.md).
Resultados executados e decisao de aceite ficam no [relatorio de execucao](../evidencias/producao/sprint-05-execucao.md).

## Matriz requisito → rota → servico → teste

Prefixo dos testes abaixo: `tests/`. Servicos estao em `app/services/`. Os testes de servico usam
PostgreSQL real; o teste de navegador percorre HTTP real no Gunicorn. O vinculo estatico do inventario
nao substitui prova de cada combinacao de payload ou permissao.

| Requisito | Rota / entrada | Servico | Teste executavel |
|---|---|---|---|
| FIN05-01 Estorno formal, replay e preservacao | POST `/api/financeiro/lancamentos/<id>/estornar` | FinanceiroCicloService.estornar | test_sprint05_cycles.py::test_financial_reversal_and_audited_closure; test_ledger_rejects_destructive_changes |
| FIN05-02 Reabertura e ajuste por revisao | POST `/api/financeiro/fechamentos/<id>/ajustar` | FinanceiroCicloService.ajustar_fechamento | test_sprint05_cycles.py::test_financial_reversal_and_audited_closure |
| FIN05-03 Conciliacao PDV × financeiro com cashback | GET `/api/financeiro/conciliacao` | FinanceiroCicloService.conciliar | test_sprint05_cycles.py::test_cashback_spend_partial_full_cancel_reconciles |
| FIN05-04 Relatorio integral sem corte oculto | GET `/api/financeiro/relatorios/fluxo-caixa/impressao` | FinanceiroService.obter_relatorio_fluxo_caixa | test_sprint05_cycles.py::test_reports_do_not_silently_drop_records_above_1000 |
| ADV05-01 Criacao pendente sem efeitos | POST `/api/adiantamentos/solicitar` | AdiantamentoCicloService.solicitar | test_sprint05_cycles.py::test_advance_full_cycle_preserves_ledger_and_stock |
| ADV05-02 Autorizacao, baixa e reversao | POST `/api/adiantamentos/<id>/transicao` | AdiantamentoCicloService.transicionar | test_sprint05_cycles.py::test_advance_full_cycle_preserves_ledger_and_stock |
| ADV05-03 Cancelamento e autorizacao concorrente | POST `/api/adiantamentos/<id>/transicao` | AdiantamentoCicloService.transicionar | test_sprint05_cycles.py::test_advance_cancel_and_concurrent_approval |
| ADV05-04 Falha transacional de autorizacao | POST `/api/adiantamentos/<id>/transicao` | AdiantamentoCicloService.transicionar | test_sprint05_cycles.py::test_advance_failure_after_ledger_insert_rolls_back |
| ADV05-05 Resumo reconciliavel por competencia | GET `/api/adiantamentos/resumo` | AdiantamentoService.obter_resumo_folha | test_sprint05_cycles.py::test_advance_full_cycle_preserves_ledger_and_stock |
| CASH05-01 Idempotencia interna e payload | POST `/api/pdv/vendas` | ClienteService.processar_cashback_da_venda | test_sprint05_cycles.py::test_cashback_processing_is_idempotent_and_checks_payload |
| CASH05-02 Expiracao automatica concorrente | POST `/api/clientes/cashback/expirar`; CLI processar-ciclos; leituras de carteira | ClientePrivacidadeService.expirar; ClienteService._aplicar_expiracoes_cliente | test_sprint05_cycles.py::test_cashback_expiration_concurrency_and_consumption |
| CASH05-03 Consumo, cancelamento e credito vencido | Cancelamento integral/parcial do PDV | ClienteService.reverter_cashback_venda; restaurar_cashback_parcial_da_venda | test_sprint05_cycles.py::test_expired_unused_credit_does_not_prevent_sale_cancellation; test_cashback_spend_partial_full_cancel_reconciles |
| MSG05-01 Fila na transacao da venda | POST `/api/pdv/vendas` | ClienteService.enviar_email_venda_automatica; MensagemFilaService.enfileirar | test_sprint05_cycles.py::test_cashback_queue_and_sale_are_one_transaction |
| MSG05-02 Deduplicacao, estados e concorrencia | POST `/api/clientes/<id>/mensagens`; POST `/api/clientes/mensagens/processar` | MensagemFilaService.enfileirar; entregar | test_sprint05_cycles.py::test_queue_gateway_outcomes_concurrency_and_replay |
| MSG05-03 Gateway bloqueado, backoff e limite de tentativas | POST `/api/clientes/mensagens/processar`; CLI processar-ciclos | MensagemFilaService.processar; GatewayBloqueado | test_sprint05_cycles.py::test_queue_backoff_exhaustion_and_default_block |
| MSG05-04 Confirmacao perdida sem reenvio | Worker persistente | MensagemFilaService.entregar | test_sprint05_cycles.py::test_queue_lost_confirmation_never_retries_uncertain |
| MSG05-05 Campanha somente para opt-in | POST `/api/clientes/mensagens/disparo-coletivo` | ClienteService.enviar_mensagem_coletiva | test_fluxo_pdv_financeiro.py::FluxoPdvFinanceiroTestCase::test_disparo_coletivo_envia_apenas_para_clientes_elegiveis |
| PRIV05-01 Consentimento e descadastro | POST `/api/clientes/<id>/consentimento` | ClientePrivacidadeService.consentir | test_sprint05_cycles.py::test_consent_export_anonymization_preserves_obligations |
| PRIV05-02 Exportacao integral e auditoria | GET `/api/clientes/<id>/exportar` | ClientePrivacidadeService.exportar | test_sprint05_cycles.py::test_consent_export_anonymization_preserves_obligations |
| PRIV05-03 Anonimizacao e preservacao de referencias | POST `/api/clientes/<id>/anonimizar` | ClientePrivacidadeService.anonimizar | test_sprint05_cycles.py::test_anonymized_idempotent_sale_cannot_reveal_customer_again |
| SEC05-01 Tenant, permissoes e CSRF | Todas as novas escritas e exportacao | decorators; AcessoEmpresaService; triggers | test_sprint05_cycles.py::test_new_mutations_require_csrf; test_new_permissions_revalidated_in_existing_session; test_http_tenant_privacy_and_finance_isolation |
| SEC05-02 IDs e valores invalidos | Entradas financeiras e de vales | money_service.positive_integer; money | test_sprint05_cycles.py::test_strict_identifiers; test_advance_refuses_invalid_money_without_effects |
| UI05-01 Ciclo de dinheiro, caixa e privacidade | GET `/api/operacoes/view` | ciclos_controller; ciclos.js | test_sprint05_browser.py::test_browser_advance_reversal_closure_and_privacy |
| OPS05-01 Schema, regressao, imagens e outage | scripts/validate_sprint05.ps1 | runner existente da Sprint 4 | scripts/validate_migrations.py; suite integral; validate_smoke; validate_security_smoke |

## Politicas de compatibilidade

As quatro provas antigas afetadas pela troca de envio sincrono para fila foram atualizadas para testar
o novo contrato: nenhuma chamada ao transporte durante a venda, PENDENTE apos commit, processamento
deterministico posterior e falha sem reverter venda ja confirmada. Os casos continuam habilitados,
com novas verificacoes de fila e adaptador; nao foram removidos nem transformados em skip/xfail.

Valores sao Decimal no servidor, enviados em strings; identificadores inteiros positivos nao aceitam
booleanos, numeros fracionados ou truncamento. Dinheiro utiliza arredondamento HALF_UP para centavos.
O bloqueio transacional serializa operacoes por tenant, preservando o desenho estabelecido na Sprint 3;
isso garante integridade, mas nao constitui benchmark de throughput por empresa.

As interfaces apresentam os registros mais recentes; os relatorios de fluxo, folha e exportacao de
cliente nao compartilham esses cortes. O relatorio existente de produtos vendidos e um ranking
operacional por produto, nao o livro financeiro; use fluxo e conciliacao para apuracao monetaria.

WhatsApp, SMTP externo, SMS externo, boleto real e emissao fiscal real nao fazem parte desta homologacao.
Adaptadores e simuladores nao demonstram entrega final, leitura, autorizacao bancaria ou fiscal.
