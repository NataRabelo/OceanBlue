# Sprint 7 — auditoria dos modulos operacionais

Base informada e conferida: `7b0c97f`. Data: 2026-09-07. Workspace compartilhado.
Esta frente altera somente Python da aplicacao, testes focais, inventario de rotas e evidencias.
Nao realiza commit, deploy, chamada a provedor ou suite Docker integral.

## Metodo e alcance

Foram inventariados e receberam disposicao os **106 arquivos Python de `app`**: 95 da base
operacional compartilhada e 11 dos modulos locais dormentes de boleto/fiscal.
Controllers, servicos, repositorios, modelos, seguranca, inicializacao e CLIs foram cruzados com
os testes e os relatorios das Sprints 1–6. A revisao combina leitura de implementacoes,
buscas estruturais/AST de rotas e chamadas, constraints/triggers existentes e regressao focal.
O apendice relaciona cada arquivo em escopo com cobertura historica e imports diretos de testes.
Isso distingue rastreabilidade de cobertura de comportamento: import de modulo e percentual
de linhas nao comprovam todos os ramos, nem ausencia universal de defeitos.

Somente a **integracao real de emissao bancaria/fiscal** fica excluida: nao houve chamadas
a provedores, homologacao externa ou habilitacao produtiva/UI. Controllers, repositorios,
servicos, providers e auxiliares locais desses modulos foram revisados e inventariados abaixo;
seus testes existentes permanecem preservados. Teste local com mock nao comprova emissao real.
Referencias compartilhadas nos modelos, permissions, isolamento, CLI de criptografia e bootstrap
tambem foram inspecionadas sem habilitar integracoes.

## Defeitos confirmados e correcoes

| ID | Causa e efeito | Arquivos e prova nova |
|---|---|---|
| MOD07-01 | `int(value)` aceitava true como 1 e truncava IDs JSON fracionados. Criacao HTTP persistia produtos, funcionarios, roles, admins ou movimentos apontando para outro identificador. Nao e demonstracao de fuga entre tenants: as permissoes continuam exigidas. | `produto_service.py`, `funcionario_service.py`, `role_service.py`, `platform_service.py`, `estoque_service.py`: reutilizam `positive_integer`; produto existente tambem valida ID antes da query. `test_http_identifiers_never_select_a_different_record`: 14 ataques HTTP; rejeicao deve preservar snapshot de todas as tabelas. `test_string_identifiers_preserve_valid_employee_product_and_stock_flow`: controle positivo com IDs string. |
| MOD07-02 | Lancamentos eram filtrados pela data UTC, enquanto vendas/conciliacao usavam o dia brasileiro. Series diarias/mensais, custo e demanda tambem extraíam datas UTC. Uma venda apos 21h local podia desaparecer do caixa/relatorio ou cair no dia/mes seguinte. | `financeiro_repository.query_lancamentos`, `estoque_repository.listar_produtos_mais_vendidos`, `pdv_repository.contar_vendas_do_dia`, `FinanceiroService.obter_dashboard`: limites locais convertidos para UTC, fim exclusivo; agrupamentos convertem UTC → America/Sao_Paulo. `test_reports_cash_closure_and_series_use_same_brazil_day` cobre antes/no inicio/antes/no fim; `test_monthly_series_does_not_move_late_evening_to_next_month` cobre virada mensal. |
| MOD07-03 | Defaults de repositorio e importacao usavam `date.today()` do servidor. Cashback podia ter saldo ainda valido, mas nenhuma alocacao utilizavel; importacao recusava cupom que ainda estava no ultimo dia brasileiro. Indicador de estoque iniciava periodo no dia/mes errado. | `cliente_repository`, `pdv_repository`, `import_export_service._import_cupom`, `estoque_service.listar_produtos_mais_vendidos`: usam `TimeService.today_br()`. `test_cashback_remains_spendable_until_brazil_midnight` gasta credito as 23:59:59 e expira o restante a 00:00; `test_coupon_import_and_selection_share_brazil_expiry_date`; tres variantes de `test_stock_default_period_uses_brazil_today`. |
| MOD07-04 | Indicadores e rankings somavam quantidade e faturamento originais apesar de devolucoes parciais. Um item integralmente devolvido permanecia no ranking enquanto outro item mantinha a venda FINALIZADA. Faturamento/ticket/custo/demanda ficavam superestimados. | `financeiro_service` e `estoque_repository`: quantidade restante e custo correspondente; produtos sem saldo vendido excluidos; faturamento do dashboard desconta cancelamento e considera cashback restituido como na conciliacao existente. `test_partial_returns_reduce_rankings_revenue_cost_and_demand`, `test_returned_item_disappears_from_rankings_while_sale_remains_active`, `test_dashboard_partial_return_with_cashback_matches_reconciliation`. |
| MOD07-05 | A importacao desativava Pix ou categoria financeira padrao, mas carregar auxiliares chamava bootstrap que forçava `ativo=True` novamente. Uma leitura anulava a configuracao confirmada. | `tenant_bootstrap_service.garantir_cadastros_operacionais` conserva atividade dos registros existentes e continua criando defaults ausentes. Duas variantes de `test_operational_lookup_preserves_imported_deactivation` importam NAO, abrem financeiro/PDV e releem a atividade persistida. |
| S07-VERSION (parent) | Health anunciava 1.0.0 fixo, divergente da versao empacotada da candidata. | Parent altera `app/health.py` para ler `VERSION`; `tests/test_release_candidate.py::test_health_reports_packaged_release_version`. Esta frente inclui o teste no green, sem autoria sobre a correcao de release. |

Os rankings continuam expressando faturamento **bruto das mercadorias restantes**, antes do desconto
global/cashback, como o contrato anterior de `ItemVenda.valor_total`. Nao foi inventado rateio novo
de desconto entre produtos. O dashboard preserva a base financeira de `Venda.total`, agora reduzida
pelos estornos efetivos. Custo continua usando custo cadastral atual, como anteriormente; nao representa
custeio historico por lote. Nenhum registro financeiro historico e reescrito por essas correcoes.

## Matriz dos modulos, rotas e testes

Os caminhos desta tabela sao relativos a `app/`, salvo quando iniciados por `tests/`.
Os testes de sprints anteriores sao evidencia historica, nao execucoes novas desta frente.

| Modulo / entrada | Arquivos revisados e invariantes | Evidencia executavel |
|---|---|---|
| Login, logout, senha e reset | `controllers/auth_controller.py`, `services/auth_service.py`, `security/jwt.py`, `password.py`, `rate_limit.py`, `models/security.py`: credencial por tenant/platform, CSRF, revogacao/session_version, reset com lock/expiracao. | `test_sprint02_security.py` e `test_sprint02_adversarial.py::test_permission_and_company_revocation_apply_to_existing_cookie`, `test_modified_unsigned_claims_cannot_authenticate`, `test_database_failures_deny_auth_and_leave_session_recoverable`. |
| Autorizacao / todas as APIs | `security/decorators.py`, `permissions.py`, `isolation.py`, `services/acesso_empresa_service.py`: permissoes relidas, hierarquia, filtros tenant/empresa, parent IDs e writes. | `test_sprint02_adversarial.py::test_every_api_method_enforces_auth_scope_and_csrf`, `test_foreign_resource_ids_cannot_read_modify_or_delete`; `test_permission_hierarchy.py`. |
| Roles e permissions | Controllers, services e repositorys de role/permission: CRUD, duplicados, dependencias, substituicao atomica e exclusao com vinculos. IDs corrigidos em MOD07-01. | `test_sprint03_transactions.py::test_role_replacement_failure_preserves_permissions_and_name`; `test_permissions_security.py::test_bootstrap_nao_reaplica_permissoes_removidas_da_role_existente`; novos ataques HTTP. |
| Plataforma / tenants / empresas / planos | `controllers/platform_controller.py`, `services/platform_service.py`, `saas_plan_service.py`, `tenant_entitlement_service.py`, `repositorys/platform_repository.py`: trial/status, plano, limites, admin e sincronizacao. | `test_sprint02_security.py` (cotas/assinatura) e `test_sprint03_transactions.py::test_concurrent_import_last_quota_and_no_orphans`; MOD07-01 para ID de empresa do admin. |
| Produtos e vinculos | Controller/service/repository de produto: barcode, categoria, atacado, empresa imutavel, saldo por movimento, historico impeditivo de exclusao. | `test_produto_service.py`; `test_sprint03_transactions.py::test_product_multiple_companies_preserves_balances_and_quota`, `test_deactivation_is_local_to_product_company`, `test_concurrent_generated_and_duplicate_barcodes`; MOD07-01. |
| Categorias de produto | Controller/service/repository de categoria: nome/descricao, duplicados, tenant e exclusao com produtos. | `test_sprint03_transactions.py::test_category_validation_and_in_use_delete`, `test_all_six_layouts_preview_import_export_reimport`. |
| Funcionarios | Controller/service/repository de funcionario: CPF, senha, salario/meta, roles, sincronizacao multiempresa, protecao da autoria/historico. | `test_sprint03_transactions.py::test_employee_company_set_and_role_changes_are_atomic`, `test_parent_and_links_rollback_after_child_insert_failure`; `test_sprint03_adversarial.py` e novos IDs HTTP. |
| Cupons | Controller/service/repository de cupom e lookup PDV: codigo, calendario, segmento empresa/cliente, minimo/teto/limites de uso e historico. | `test_sprint04_operations.py::test_coupon_rounding_cap_customer_and_historical_usage`, `test_coupon_last_use_is_serialized_in_postgresql`, `test_global_coupon_usage_cannot_be_hidden_by_company_scope`; MOD07-03. |
| Importacao/exportacao | Controller/service/repository de import_export: seis layouts, preview/savepoints, lote atomico, formulas proibidas, escopo, estoque inicial e edicao cadastral. | `test_import_export.py`; `test_sprint03_transactions.py::test_all_six_layouts_preview_import_export_reimport`, `test_all_layouts_reject_entire_batch_when_last_row_invalid`, `test_import_invalid_values_rollback`; MOD07-03/MOD07-05. |
| PDV / comprovante / cancelamentos | Controller/service/repository de PDV: precificacao em centavos, pagamentos, cashback, idempotencia, saldo bloqueado, estorno parcial/integral e reimpressao. | `test_fluxo_pdv_financeiro.py`; `test_sprint04_operations.py::test_full_cancel_after_partial_is_atomic_idempotent_and_conserves_money`; `test_sprint03_adversarial.py::test_sale_rollback_at_each_persisted_stage`; MOD07-04. |
| Estoque / indicadores | Controller/service/repository de estoque: entradas/saidas manuais, baixa vinculada ao item, devolucao limitada, saldo, validade, indicadores e escopo. | `test_sprint03_transactions.py::test_concurrent_stock_exhaustion_has_one_winner`, `test_manual_cancellation_concurrent_replay`; MOD07-01/02/03/04. |
| Alertas / jobs | `services/alerta_service.py`, partes de estoque/comunicacao, `cli/alertas.py`: fila por destinatario, cooldown/resumo, claim duravel INCERTO, falha antes do aceite e retries. | `test_sprint04_operations.py::test_pending_alert_survives_worker_loss_and_cli_retries`, `test_simultaneous_retries_send_each_delivery_once`, `test_successful_delivery_ack_failure_does_not_duplicate`; `test_sprint04_adversarial.py`. Nenhum transporte real. |
| Financeiro / caixa / relatorios | Controller/service/repository de financeiro: lancamento e contrapartida, fechamento por operador/dia, totais e ranking. | `test_sprint05_cycles.py::test_reports_do_not_silently_drop_records_above_1000`, `test_financial_reversal_and_audited_closure`; MOD07-02/04; `test_empty_dashboard_http_is_valid_with_and_without_company`. |
| Ciclos financeiros | `controllers/ciclos_controller.py`, `services/financeiro_ciclo_service.py`: motivo, revisao, origem, reconciliacao, reabrir/fechar, estorno imutavel. | `test_sprint05_cycles.py`; `test_sprint05_adversarial.py`: concorrencia, falhas por fronteira, conciliacao >1000 e marcador SQL. |
| Vales e folha | Controller/service/repository de adiantamento, `adiantamento_ciclo_service.py`: PENDENTE/AUTORIZADO/BAIXADO/ESTORNADO/CANCELADO, revalidacao de vinculo, dinheiro/produto e efeitos atomicos. | `test_sprint05_cycles.py::test_advance_full_cycle_preserves_ledger_and_stock`, `test_advance_failure_after_ledger_insert_rolls_back`; `test_sprint05_adversarial.py::test_advance_approval_rechecks_employee_company_link`. |
| Clientes / carteira / cashback | Controller/service/repository de cliente: cadastro/consentimento, credito por venda, alocacao, expiracao e reversao sob lock. | `test_sprint05_cycles.py::test_cashback_spend_partial_full_cancel_reconciles`, `test_cashback_processing_is_idempotent_and_checks_payload`, `test_expired_unused_credit_does_not_prevent_sale_cancellation`; MOD07-03/04. |
| Privacidade | `cliente_privacidade_service.py` e rotas de ciclos: exportacao com escopo global, consentimento, anonimizacao e saneamento do replay. | `test_sprint05_cycles.py::test_anonymized_idempotent_sale_cannot_reveal_customer_again`; `test_sprint05_adversarial.py::test_privacy_committed_after_claim_prevents_transport`. |
| Mensagens / ciclos CLI | `mensagem_fila_service.py`, `comunicacao_service.py`, `cli/ciclos.py`: fila atomica, backoff/limite, claim, consentimento e permissoes relidos antes do transporte, estado incerto sem reenvio. | `test_sprint05_cycles.py::test_queue_backoff_exhaustion_and_default_block`, `test_queue_lost_confirmation_never_retries_uncertain`; `test_sprint05_adversarial.py::test_send_revalidates_permission_after_claim`. |
| Auditoria | `controllers/auditoria_controller.py`, `services/audit_service.py`, modelo AuditLog e actor SQL: cursor, filtros limitados, projecao privada, request ID e persistencia imutavel. | `test_sprint06_operations.py::test_audit_permission_scope_pagination_and_private_projection`, `test_company_restricted_audit_excludes_global_and_other_company`; `test_sprint06_data_adversarial.py`. |
| Runtime / health / storage / metricas | `__init__.py`, `config.py`, `extensions.py`, `routes.py`, `health.py`, `operations.py`: configuracao fail-closed, schema/storage, readiness e logs sem payload privado. | `test_startup.py`, `test_runtime.py`, `test_sprint06_operations.py`, `test_sprint06_security_adversarial.py`, `test_sprint06_data_adversarial.py`; S07-VERSION. |
| Segredos / headers / proxy / egress | `security/secrets.py`, `field_crypto.py`, `headers.py`, `proxy.py`, `outbound.py`, `integrations.py`, `errors.py`: chaves, TLS, redacao, destinos autorizados, bloqueio externo. | `test_security_headers.py`; Sprints 2/6 adversariais, incluindo rotacao, spoof de proxy, erros de banco e logs. |
| Modelos / transacoes / seed / utilitarios | `models/db.py`, `models/security.py`, `transaction_service.py`, `idempotency_service.py`, `money_service.py`, `time_service.py`, `tenant_bootstrap_service.py`, `seeds/seed.py`, `cli/security.py`, `utils/helpers.py`. | `test_schema.py`, `test_sprint03_database.py`, `test_sprint03_faults.py`, `test_sprint02_security.py`; MOD07-05. Helpers antigos de float/ID em `utils/helpers.py` nao tem callers encontrados em `app`; nao foram convertidos em achados ativos. |
| Rotas de navegacao | `controllers/main_controller.py` e context processors: redirecionamentos, permissoes de paginas, favicon/manifest locais. | `test_permissions_security.py`, testes HTTP Sprints 2/6. Browser, templates e JavaScript pertencem a outra frente; nenhuma alteracao desta auditoria nesses arquivos. |

## Boleto/fiscal local — revisao e disposicao dos 11 arquivos

Esta secao complementa o alcance inicial sem reabrir o freeze. A evidencia executavel citada
e **historica/preservada**, nao uma nova rodada desta frente. A disposicao de todos estes
arquivos e codigo local revisado, mantido dormente em producao; somente os caminhos indicados
pelos testes possuem prova de execucao isolada. Nao ha atestado de prontidao para habilitacao.

| Arquivo(s) | Revisao local e limite | Testes preservados / disposicao |
|---|---|---|
| `app/controllers/boleto_controller.py` | Entradas de banco, regras, parcelas, cadastro, baixa, retorno e recalculo; tenant/escopo originam-se da sessao. Webhook Asaas responde 403 incondicionalmente; em producao o guard do blueprint responde 404 antes do controller. | `tests/test_sprint06_operations.py::test_production_routes_block_even_authenticated`; matriz HTTP de `tests/test_sprint02_adversarial.py::test_every_api_method_enforces_auth_scope_and_csrf`. Controller local inventariado, nao habilitado. |
| `app/controllers/fiscal_controller.py` | Configuracao, prevalidacao, emissao local, consulta, cancelamento e downloads passam permissoes/escopo ao service; blueprint inteiro bloqueado fora de testing. | Mesmas provas HTTP de bloqueio/escopo; testes de fluxo fiscal abaixo preservados. Sem homologacao de emissao/download externo. |
| `app/repositorys/boleto_repository.py` | Queries de boleto/banco/regra filtram tenant, com empresa quando fornecida; parcelas usam join ao boleto. Helper de evento recebe boleto/parcela previamente selecionados: nao e uma API de autorizacao independente. Commit/rollback delegados a sessao. | Exercicios indiretos historicos; 36,8% de linhas, sem teste com import direto localizado. Cobertura parcial explicitamente nao equivale a validacao completa de baixa/concorrencia. |
| `app/repositorys/fiscal_repository.py` | Empresa, configuracao, venda, produto-empresa e nota limitados por tenant; venda/nota recebem conjunto de empresas. Carregamento de itens/pagamentos suporta serializacao local. | `tests/test_fluxo_pdv_financeiro.py`: prevalidacao e emissao local; 75,9% historico. Sem prova de protocolo externo. |
| `app/services/boleto_service.py` | Configuracao, criacao de parcelas explicitas, registro/retorno mock, baixa e eventos; rollback em falha. Calculo usado e `BoletoService.calcular_juros_multa`, nao a classe auxiliar homonima separada. | `tests/test_boleto_service.py::test_calcular_juros_multa_aplica_regra_basica`, `test_recalcular_juros_multa_nao_reaplica_total_de_forma_cumulativa`, `test_registrar_boleto_atualiza_status_bancario_e_preserva_status_interno`. Prova local parcial; nao libera cobranca real. |
| `app/services/fiscal_service.py` | Prevalidacao, configuracao, XML/chave/numero locais, resultado mock e eventos; factory bloqueia provider real. Geracao local de XML ocorre antes da factory: o guard HTTP e importante e nao deve ser substituido apenas pelo bloqueio de rede. | `tests/test_fluxo_pdv_financeiro.py::test_prevalidacao_fiscal_aponta_pendencias_sem_configuracao`, `test_prevalidacao_fiscal_fica_pronta_com_base_minima_preenchida`, `test_emissao_fiscal_gera_numero_chave_xml_e_incrementa_numeracao`; `tests/test_sprint02_adversarial.py::test_fiscal_mock_does_not_probe_server_files_or_environment`. Resultado mock nao e autorizacao fiscal real. |
| `app/services/boleto_provider.py` | Factory exige testing e flag booleana True; rejeita configuracao real ativa com chave. Asaas `_request` chama guard incondicional antes de segredo/rede; mock grava artefatos locais. | `tests/test_integracoes_sprint4.py::test_asaas_provider_cria_cliente_e_cobranca_boleto` substitui guard e transporte por fake exclusivamente no teste. Guards adversariais abaixo preservados; nenhuma chamada externa nova. |
| `app/services/fiscal_provider.py` | Factory exige testing/flag True e rejeita Focus; `_request` bloqueia antes de segredo/rede; `_salvar_url` nega download real incondicionalmente. | `tests/test_integracoes_sprint4.py::test_focus_provider_emite_nfce_com_ref_idempotente` usa guard/transporte substituidos; guards adversariais abaixo. Somente contrato de payload simulado. |
| `app/services/banco_emissor_service.py` | Criacao de banco, configuracao de parcelas e juros valida empresa/escopo e banco relacionado; enums, limites, serializacao e rollback lidos. | 13,6% historico; sem import direto de teste localizado. Revisado, nao plenamente testado; permanece inacessivel via blueprint produtivo. |
| `app/services/parcelamento_service.py` | Rateio em centavos com residuo na ultima parcela, minimo, intervalo e dia fixo lidos. Busca de referencias em `app`/`tests` encontra apenas autorreferencias: nao e o caminho usado por `_criar_parcelas`. | **0% historico**, nenhum caller/teste direto localizado. Codigo dormente revisado, nao testado; nao atribuir testes de BoletoService a esta classe. |
| `app/services/calculo_juros_multa_service.py` | Restante, carencia, juros diario/mensal, multa e teto lidos. Conversao decimal invalida retorna zero. Busca encontra apenas autorreferencias. | **0% historico**, nenhum caller/teste direto localizado. Codigo dormente revisado, nao testado; testes da outra implementacao nao cobrem esta classe. |

Limites locais registrados, sem mudar fontes no freeze: ainda existem coercoes `int(value)`
nos cadastros bancarios/parcelamento e conversoes permissivas nos calculos dormentes; estes
nao receberam a correcao MOD07-01 nem prova red/green nesta frente. Precisam de validacao de
entradas e testes proprios antes de qualquer futura ativacao. As duas classes sem callers e
0% de cobertura sao lacunas de evidencia local, nao funcionalidades produtivas liberadas.
Nao foi demonstrado bypass dos bloqueios, nem se declara ausencia de defeitos em todos os ramos.

Protecoes fail-closed revisadas e preservadas:
- `app/config.py::ProductionConfig.validate_runtime` rejeita flags de integracao habilitadas
  ou nao canonicas; `app/operations.py::register_operations` fixa provedores externos False,
  habilita mocks somente em testing e retorna 404 para os dois blueprints fora de testing.
- `app/security/integrations.py::require_real_integration` sempre lanca PermissionError;
  factories nao permitem selecionar provedores reais, mesmo em testing.
- `tests/test_sprint06_operations.py::test_production_flags_fail_closed`,
  `test_production_ui_and_payment_lookup_hide_blocked_modules` e
  `test_production_routes_block_even_authenticated` preservam bloqueio de flags, UI e HTTP.
- `tests/test_sprint06_data_adversarial.py::test_production_feature_flags_reject_noncanonical_values`,
  `test_disabled_production_provider_factory_fails_closed`, `test_mock_provider_requires_explicit_testing_flag`,
  `test_real_provider_request_denied_before_network_or_secret` e
  `test_real_provider_selection_and_download_denied` preservam negacao antes de segredo/rede/download.

## Evidencias anteriores e hipoteses descartadas

- [Sprint 1 — validacao](../sprint-01-validacao.md): 85 casos em duas rodadas; baseline de inicializacao, schema e PostgreSQL obrigatorio.
- [Sprint 2 — validacao](../sprint-02-validacao.md): 166 casos; escopo, sessao, cotas em SQL, CSRF e falha fechada.
- [Sprint 3 — validacao](../sprint-03-validacao.md): rollback, centavos, historico e concorrencia; seis layouts com savepoints. A ausencia de chamada de cota em alguns services **nao** foi tratada como bypass: `migrations/versions/4d5e6f7a8b9c_sprint02_security.py::ocean_quota` protege INSERTs e serializa por tenant.
- [Sprint 4 — validacao](../sprint-04-validacao.md): 413 casos em duas rodadas; cupons, descontos, alertas/claims e IDs de venda ja corrigidos. MOD07-01 localiza a mesma classe de problema em outros cadastros, sem declarar regressao do PDV.
- [Sprint 5 — validacao](../sprint-05-validacao.md): 547 casos em duas rodadas; ciclos, ledger, privacidade, backoff e revalidacao. Conserva limites operacionais: sem scheduler instalado e sem promessa de exactly-once no transporte.
- [Sprint 6 — validacao](../sprint-06-validacao.md): 758 casos em duas rodadas; auditoria, logs, storage, snapshot, carga e indices. Sua cobertura historica serve de mapa, nao de prova dos arquivos alterados nesta Sprint 7.

Listas com limite visual, custo cadastral atual e fornecedores deliberadamente bloqueados nao foram
automaticamente classificados como features faltantes. O estado INCERTO apos perda de confirmacao e
proteção existente contra duplicacao. Nenhum teste foi removido, pulado ou convertido em xfail.
Nenhum gate de cobertura integral foi alterado: `-o addopts=` e usado somente na selecao focal,
que nao e apresentada como regressao integral ou cobertura da release.

## Execucao focal e freeze

**Freeze de codigo/testes desta frente liberado ao parent.** Inventario regenerado por
`scripts.inventory.render_inventory`: 165 rotas preservadas e 15 linhas com novos vinculos de testes.
Gravacao do CSV por apply_patch. O parent pode executar a regressao integral sobre os arquivos congelados.

| Rodada | Resultado | Tempo JUnit | Evidencia |
|---|---|---:|---|
| Red definitivo, app exportado de 7b0c97f | 26 falhas reais / 1 aprovado, 0 erros/skips; 27 IDs unicos | 256,085 s | [red.xml](module-audit/red.xml), [red.txt](module-audit/red.txt) |
| Green final, fontes atuais e testes de release | 35/35 aprovados, 0 falhas/erros/skips; 35 IDs unicos | 187,803 s | [green.xml](module-audit/green.xml), [green.txt](module-audit/green.txt) |
| Green suplementar, dashboard vazio HTTP | 2/2 aprovados, 0 falhas/erros/skips; 27 outros casos deselecionados apenas nessa selecao | 28,011 s | [green-empty.xml](module-audit/green-empty.xml), [green-empty.txt](module-audit/green-empty.txt) |

O green de 35 casos compreende 27 testes de auditoria e oito testes de release do parent.
Com os dois controles HTTP acrescentados a pedido do parent, o arquivo final de auditoria tem
29 casos parametrizados e o conjunto focal tem **37 aprovacoes distintas**, sem dupla contagem.
Nao foi executada suite integral nem foi aplicado filtro para mascarar uma falha conhecida.
Estas 37 aprovacoes antecedem a instrumentacao HTTP autouse adicionada depois pelo parent
em `tests/conftest.py`; nao se atribui a estas rodadas `/tmp/http-route-coverage.json` da nova
instrumentacao. A regressao do parent deve usar o conftest final e os locks novos.
Os 26 reds agrupam cinco causas operacionais; nao sao 26 vulnerabilidades independentes.

[proof.json](module-audit/proof.json) conserva resumos extraidos dos JUnits, falha exata por caso,
SHA-256 dos 106 fontes Python da app no freeze, dos dois arquivos de teste, VERSION, CSV e logs/JUnits.
Imagem de dependencias usada: `sha256:c94607d630bae0f8b22c5cdfc6e98b1dcd200a42cf1ec3019deb1f91f2661147`.
As dependencias sao as da imagem de teste anterior; estes resultados nao substituem a regressao
do parent com os novos locks. Os dois bancos estavam em tmpfs, rede Docker interna exclusiva,
sem portas publicadas, nome oceanblue_test e credenciais sinteticas. Red e green definitivos
usaram bancos separados e parcialmente concorreram pelos recursos do host.
Os oito containers e a rede exclusivos desta frente foram removidos apos a coleta;
nenhum recurso de outra frente foi removido. A remocao inicial do export temporario foi recusada
pela revisao automatica. O parent depois resolveu o caminho absoluto, conferiu ausencia de links
e comparou seus 197 arquivos com o Git da base (iguais apos normalizacao CRLF). A limpeza nativa
restrita a esse diretorio criado pela tarefa foi concluida: [registro](module-audit/export-cleanup.json).

Comando focal entregue ao parent (ambiente de teste PostgreSQL isolado ja configurado):

```text
python -m pytest tests/test_sprint07_audit.py tests/test_release_candidate.py -o addopts= -o cache_dir=/tmp/pytest-cache -q --tb=short --junitxml=/tmp/sprint07-audit.xml
python -m scripts.inventory --check
```

Para reproduzir o green com a imagem anterior, montar o checkout somente leitura em `/app`,
definir `STORAGE_ROOT=/tmp/oceanblue-storage` e `TEST_DATABASE_URL` apontando exclusivamente
para o PostgreSQL descartavel oceanblue_test. Para o red, montar `app` exportado por
`git archive 7b0c97f app` e os testes atuais, mantendo separados os bancos de cada runner.
Nunca reutilizar o banco de outra frente: fixtures truncam todas as tabelas desse banco de teste.

Fixtures exigem PostgreSQL real `oceanblue_test`; nao ha fallback SQLite.
O teste historico inicial usou imagem anterior com sete arquivos Python diferentes da base;
o red definitivo monta `app` exportado exatamente de `7b0c97f`, preservando o checkout compartilhado.
O green monta fontes atuais somente leitura, com storage e cache em /tmp.

Iteracoes nao aceitas:
- Red inicial: 23 falhas / 1 aprovado. Vinte falhas de produto; duas fixtures tentavam inserir
  vendas fora do mes aceito pela trigger e uma desligava cashback enquanto esperava usa-lo.
  Fixtures corrigidas usam dia 2 do mes corrente, preservam todos os guards e deixam uso habilitado.
- Primeiro green: 32 erros de setup porque storage apontava para /app/instance no mount read-only;
  corrigido somente o runner via STORAGE_ROOT=/tmp/oceanblue-storage.
- Green intermediario: 28 aprovados / 4 falhas na query de custo. A nova expressao composta
  alterou a inferencia do FROM pelo SQLAlchemy; `select_from(ItemVenda)` torna a origem explicita.
  Este erro da iteracao nao e contado como defeito adicional da base.
- O teste de dashboard vazio valida tambem o caso visto pela frente browser. Processos ja iniciados
  conservam modulos Python carregados e precisam reiniciar apos a correcao.

## Apendice — disposicao dos 106 arquivos Python

Disposicao: os 11 arquivos listados na secao boleto/fiscal sao **locais dormentes revisados**,
com limites de teste explicitados individualmente; os outros 95 sao **base operacional revisada**,
rastreada na matriz de modulos. Todos permanecem preservados. Apenas os arquivos associados
a MOD07-01–05 e S07-VERSION recebem as correcoes/testes focais descritos, nao uma certificacao
nova de todos os arquivos. As linhas abaixo incluem ambos os grupos, sem exclusoes de arquivos.

Cobertura abaixo: percentual de **linhas historico** extraido de
[verify1/coverage.xml](../sprint-06-validacao/verify1/coverage.xml), nao recalculado nesta frente.
Imports de testes foram localizados por AST. Ate tres suites sao mostradas por arquivo;
“indireto/sem import direto” nao significa defeito nem ausencia total de teste.

| Arquivo | Linhas historicas | Suites com import direto |
|---|---:|---|
| `app/controllers/boleto_controller.py` | 34.5% | indireto/sem import direto |
| `app/controllers/fiscal_controller.py` | 50.7% | indireto/sem import direto |
| `app/repositorys/boleto_repository.py` | 36.8% | indireto/sem import direto |
| `app/repositorys/fiscal_repository.py` | 75.9% | indireto/sem import direto |
| `app/services/banco_emissor_service.py` | 13.6% | indireto/sem import direto |
| `app/services/boleto_provider.py` | 62.5% | `tests/test_boleto_service.py`; `tests/test_integracoes_sprint4.py`; `tests/test_sprint02_security.py` |
| `app/services/boleto_service.py` | 38.3% | `tests/test_boleto_service.py` |
| `app/services/calculo_juros_multa_service.py` | 0.0% | indireto/sem import direto |
| `app/services/fiscal_provider.py` | 81.9% | `tests/test_integracoes_sprint4.py`; `tests/test_sprint02_security.py`; `tests/test_sprint06_data_adversarial.py` |
| `app/services/fiscal_service.py` | 76.1% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint02_adversarial.py` |
| `app/services/parcelamento_service.py` | 0.0% | indireto/sem import direto |
| `app/__init__.py` | 96.9% | indireto/sem import direto |
| `app/audit/__init__.py` | 100.0% | indireto/sem import direto |
| `app/cli/__init__.py` | 100.0% | indireto/sem import direto |
| `app/cli/alertas.py` | 100.0% | indireto/sem import direto |
| `app/cli/ciclos.py` | 62.5% | indireto/sem import direto |
| `app/cli/security.py` | 77.8% | indireto/sem import direto |
| `app/config.py` | 79.4% | `tests/test_runtime.py`; `tests/test_sprint06_data_adversarial.py` |
| `app/controllers/adiantamento_controller.py` | 62.5% | indireto/sem import direto |
| `app/controllers/auditoria_controller.py` | 100.0% | indireto/sem import direto |
| `app/controllers/auth_controller.py` | 93.3% | indireto/sem import direto |
| `app/controllers/categoria_controller.py` | 80.8% | indireto/sem import direto |
| `app/controllers/ciclos_controller.py` | 82.7% | indireto/sem import direto |
| `app/controllers/cliente_controller.py` | 69.9% | indireto/sem import direto |
| `app/controllers/cupom_controller.py` | 65.3% | indireto/sem import direto |
| `app/controllers/estoque_controller.py` | 74.0% | indireto/sem import direto |
| `app/controllers/financeiro_controller.py` | 57.0% | indireto/sem import direto |
| `app/controllers/funcionario_controller.py` | 71.6% | indireto/sem import direto |
| `app/controllers/import_export_controller.py` | 71.1% | indireto/sem import direto |
| `app/controllers/main_controller.py` | 48.6% | indireto/sem import direto |
| `app/controllers/pdv_controller.py` | 84.4% | indireto/sem import direto |
| `app/controllers/permission_controller.py` | 75.5% | indireto/sem import direto |
| `app/controllers/platform_controller.py` | 40.3% | indireto/sem import direto |
| `app/controllers/produto_controller.py` | 78.6% | indireto/sem import direto |
| `app/controllers/role_controller.py` | 73.9% | indireto/sem import direto |
| `app/errors/__init__.py` | 100.0% | indireto/sem import direto |
| `app/extensions.py` | 100.0% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_import_export.py`; `tests/test_permissions_security.py` |
| `app/health.py` | 100.0% | `tests/test_sprint06_security_adversarial.py` |
| `app/models/__init__.py` | 100.0% | indireto/sem import direto |
| `app/models/db.py` | 99.9% | `tests/test_boleto_service.py`; `tests/test_fluxo_pdv_financeiro.py`; `tests/test_import_export.py` |
| `app/models/security.py` | 100.0% | `tests/test_sprint02_security.py` |
| `app/operations.py` | 97.4% | `tests/test_sprint06_data_adversarial.py`; `tests/test_sprint06_operations.py`; `tests/test_sprint06_security_adversarial.py` |
| `app/repositorys/__init__.py` | 100.0% | indireto/sem import direto |
| `app/repositorys/adiantamento_repository.py` | 88.8% | indireto/sem import direto |
| `app/repositorys/categoria_repository.py` | 86.4% | indireto/sem import direto |
| `app/repositorys/cliente_repository.py` | 77.1% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint07_audit.py` |
| `app/repositorys/cupom_repository.py` | 93.1% | indireto/sem import direto |
| `app/repositorys/estoque_repository.py` | 79.2% | indireto/sem import direto |
| `app/repositorys/financeiro_repository.py` | 94.0% | indireto/sem import direto |
| `app/repositorys/funcionario_repository.py` | 87.3% | indireto/sem import direto |
| `app/repositorys/import_export_repository.py` | 87.2% | indireto/sem import direto |
| `app/repositorys/pdv_repository.py` | 86.8% | `tests/test_sprint06_operations.py`; `tests/test_sprint07_audit.py` |
| `app/repositorys/permission_repository.py` | 73.3% | indireto/sem import direto |
| `app/repositorys/platform_repository.py` | 67.7% | indireto/sem import direto |
| `app/repositorys/produto_repository.py` | 88.6% | indireto/sem import direto |
| `app/repositorys/role_repository.py` | 95.3% | `tests/test_sprint02_security.py` |
| `app/routes.py` | 100.0% | indireto/sem import direto |
| `app/security/__init__.py` | 100.0% | indireto/sem import direto |
| `app/security/decorators.py` | 88.9% | indireto/sem import direto |
| `app/security/errors.py` | 95.2% | indireto/sem import direto |
| `app/security/field_crypto.py` | 93.3% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint02_security.py` |
| `app/security/headers.py` | 100.0% | `tests/test_security_headers.py`; `tests/test_sprint06_security_adversarial.py` |
| `app/security/integrations.py` | 100.0% | indireto/sem import direto |
| `app/security/isolation.py` | 94.9% | indireto/sem import direto |
| `app/security/jwt.py` | 81.6% | indireto/sem import direto |
| `app/security/outbound.py` | 96.4% | `tests/test_sprint02_security.py` |
| `app/security/password.py` | 90.0% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_import_export.py`; `tests/test_permissions_security.py` |
| `app/security/permissions.py` | 93.4% | indireto/sem import direto |
| `app/security/proxy.py` | 100.0% | `tests/test_sprint06_operations.py`; `tests/test_sprint06_security_adversarial.py` |
| `app/security/rate_limit.py` | 87.5% | `tests/test_sprint02_adversarial.py`; `tests/test_sprint02_security.py` |
| `app/security/secrets.py` | 75.0% | indireto/sem import direto |
| `app/security/validators.py` | 100.0% | indireto/sem import direto |
| `app/seeds/__init__.py` | 100.0% | indireto/sem import direto |
| `app/seeds/seed.py` | 35.2% | indireto/sem import direto |
| `app/services/__init__.py` | 100.0% | indireto/sem import direto |
| `app/services/acesso_empresa_service.py` | 95.5% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_import_export.py`; `tests/test_permissions_security.py` |
| `app/services/adiantamento_ciclo_service.py` | 96.6% | `tests/test_sprint05_adversarial.py`; `tests/test_sprint05_cycles.py` |
| `app/services/adiantamento_service.py` | 89.3% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint05_cycles.py` |
| `app/services/alerta_service.py` | 95.9% | `tests/test_sprint04_adversarial.py`; `tests/test_sprint04_operations.py` |
| `app/services/audit_service.py` | 95.5% | `tests/test_sprint06_data_adversarial.py`; `tests/test_sprint06_operations.py` |
| `app/services/auth_service.py` | 95.2% | `tests/test_sprint02_security.py` |
| `app/services/categoria_service.py` | 85.1% | `tests/test_sprint02_security.py`; `tests/test_sprint03_transactions.py`; `tests/test_sprint07_audit.py` |
| `app/services/cliente_privacidade_service.py` | 96.1% | `tests/test_sprint05_adversarial.py`; `tests/test_sprint05_cycles.py` |
| `app/services/cliente_service.py` | 81.1% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint03_adversarial.py`; `tests/test_sprint05_adversarial.py` |
| `app/services/comunicacao_service.py` | 57.1% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint02_adversarial.py`; `tests/test_sprint02_security.py` |
| `app/services/cupom_service.py` | 75.9% | `tests/test_sprint04_operations.py`; `tests/test_sprint07_audit.py` |
| `app/services/estoque_service.py` | 78.9% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint03_adversarial.py`; `tests/test_sprint03_transactions.py` |
| `app/services/financeiro_ciclo_service.py` | 92.6% | `tests/test_sprint05_adversarial.py`; `tests/test_sprint05_cycles.py`; `tests/test_sprint07_audit.py` |
| `app/services/financeiro_service.py` | 84.7% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint03_adversarial.py`; `tests/test_sprint03_transactions.py` |
| `app/services/funcionario_service.py` | 82.4% | `tests/test_sprint03_adversarial.py`; `tests/test_sprint03_faults.py`; `tests/test_sprint03_transactions.py` |
| `app/services/idempotency_service.py` | 97.0% | indireto/sem import direto |
| `app/services/import_export_service.py` | 91.6% | `tests/test_import_export.py`; `tests/test_sprint02_security.py`; `tests/test_sprint03_transactions.py` |
| `app/services/mensagem_fila_service.py` | 90.0% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint03_transactions.py`; `tests/test_sprint05_adversarial.py` |
| `app/services/money_service.py` | 97.1% | `tests/test_sprint05_adversarial.py`; `tests/test_sprint05_cycles.py` |
| `app/services/pdv_service.py` | 89.7% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_sprint03_adversarial.py`; `tests/test_sprint03_database.py` |
| `app/services/permission_service.py` | 40.8% | indireto/sem import direto |
| `app/services/platform_service.py` | 29.1% | `tests/test_sprint02_security.py` |
| `app/services/produto_service.py` | 86.5% | `tests/test_produto_service.py`; `tests/test_sprint03_adversarial.py`; `tests/test_sprint03_faults.py` |
| `app/services/role_service.py` | 82.9% | `tests/test_sprint02_security.py`; `tests/test_sprint03_transactions.py` |
| `app/services/saas_plan_service.py` | 84.4% | `tests/test_sprint02_security.py` |
| `app/services/tenant_bootstrap_service.py` | 100.0% | `tests/test_fluxo_pdv_financeiro.py`; `tests/test_import_export.py`; `tests/test_permissions_security.py` |
| `app/services/tenant_entitlement_service.py` | 90.2% | `tests/test_sprint02_security.py` |
| `app/services/time_service.py` | 93.0% | `tests/test_permissions_security.py`; `tests/test_sprint02_security.py`; `tests/test_sprint04_adversarial.py` |
| `app/services/transaction_service.py` | 92.5% | indireto/sem import direto |
| `app/utils/__init__.py` | 100.0% | indireto/sem import direto |
| `app/utils/helpers.py` | 0.0% | indireto/sem import direto |
