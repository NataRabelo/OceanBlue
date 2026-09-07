# Inventario requisito → rota → servico → teste

O [CSV completo](inventario-requisito-rota-servico-teste.csv) é regenerado para o código atual
(165 regras na base da Sprint 6), exceto arquivos estáticos: método HTTP, endpoint, requisito,
chamadas diretas de serviço e testes que chamam o mesmo método. Gere com `python -m scripts.inventory`;
`--check` detecta desatualização no CI. A tabela abaixo preserva o diagnóstico da Sprint 1;
o fechamento está na [Sprint 7](../evidencias/producao/sprint-07-execucao.md).

Os IDs agrupam o `mapa-de-funcionalidades.md`, sem criar nova especificacao de aceite. O vinculo e extraido por AST, sem inferir cobertura HTTP: decorators, helpers e chamadas indiretas nao sao rastreados. `LACUNA` significa ausencia de teste direto localizado, nao funcionalidade quebrada. Teste de servico nao homologa automaticamente a rota.

| Requisito | Rotas de referencia | Servico | Evidencia / lacuna |
|---|---|---|---|
| OPS-01 | /api/health; /api/ready | app.health / banco | test_runtime: banco migrado e falha 503 |
| AUTH-01 | /login | AuthService, AuditService | test_permissions_security: login, auditoria, rate limit |
| AUTH-02/03 | /api/roles/; /api/permissions/ | RoleService, PermissionService, AcessoEmpresaService | hierarquia/negacao cobertas; CRUD HTTP parcial |
| UI-01 | /home; /financeiro/home; /configuracoes/home | AcessoEmpresaService | ocultacao de menu e bloqueio direto |
| SAAS-01 | /platform/ | PlatformService, TenantEntitlementService | trial expirado; ciclo administrativo ainda sem aceite completo |
| CAD-01 | /api/produtos/ | ProdutoService | test_produto_service; CSRF HTTP em test_permissions_security |
| CAD-02/03 | /api/categorias/; /api/funcionarios/ | CategoriaService, FuncionarioService | modelos em fixtures; lacunas CRUD |
| CAD-04 | /api/cupons/ | CupomService | desconto pelo PDV; lacunas CRUD |
| CAD-05 | /api/importacao-exportacao/ | ImportExportService | test_import_export: modelos, importacao e validacao |
| PDV-01 | /api/pdv/ | PdvService | venda, atacado, pagamentos, cancelamentos e saldos |
| EST-01 | /api/estoque/ | EstoqueService | movimentos, reversao e alertas/cooldown simulados |
| FIN-01 | /api/adiantamentos/ | AdiantamentoService | produto/dinheiro e reflexos financeiros |
| FIN-02 | /api/financeiro/ | FinanceiroService | venda, caixa, reversoes; lacunas relatorios/CRUD |
| REL-01 | /api/clientes/ | ClienteService, ComunicacaoService | carteira, cashback, configuracao criptografada e mensagens simuladas |
| FORA-01/02 | /api/financeiro/boletos/; /api/fiscal/ | BoletoService, FiscalService, providers | testes legados preservados; nenhuma homologacao externa |

Os testes de infraestrutura verificam banco incorreto, segredos obrigatorios, bloqueio de rede, CSRF e saude. Migrations sao um gate anterior ao pytest; a cobertura da aplicacao nao inclui migrations/scripts. Testes completos de servicos em `test_fluxo_pdv_financeiro.py` nao equivalem a uma homologacao ponta a ponta pelo navegador.
