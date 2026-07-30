# Modelo de dados

## Banco

O sistema usa SQLAlchemy com migrations Alembic. O banco esperado e PostgreSQL via `DATABASE_URL`.

## Entidades principais

- Plataforma e SaaS: `Tenant`, `PlatformOwner`.
- Empresa e usuarios: `Empresa`, `Funcionario`, `FuncionarioEmpresa`.
- Autorizacao: `Role`, `Permission`, `RolePermission`.
- Auditoria: `AuditLog`.
- Clientes e relacionamento: `Cliente`, `CarteiraCliente`, `CreditoCashbackCliente`, `MovimentoCarteiraCliente`, `MensagemCliente`, `ConfiguracaoClienteEmpresa`.
- Produtos e estoque: `CategoriaProduto`, `Produto`, `ProdutoEmpresa`, `MovimentoEstoque`, `ConfiguracaoNotificacaoEstoque`.
- Vendas/PDV: `Venda`, `ItemVenda`, `PagamentoVenda`.
- Financeiro: `FormaPagamento`, `CategoriaFinanceira`, `TipoOperacao`, `LancamentoFinanceiro`, `FechamentoCaixa`.
- Cupons e vales: `Cupom`, `AdiantamentoFuncionario`.
- Boletos: `BancoEmissor`, `ConfiguracaoParcelamento`, `RegraJurosMulta`, `Boleto`, `ParcelaBoleto`, `EventoBoleto`.
- Fiscal: `ConfiguracaoFiscalEmpresa`, `NotaFiscalVenda`.

## Migrations relevantes

- `1150177c20ca_initial.py`: base inicial.
- `7f3c1a2b9d4e_add_roles_and_permissions.py`: roles/permissoes.
- `8f6e4c2a1b9d_add_pdv_financeiro_permissions_and_defaults.py`: permissoes e defaults de PDV/financeiro.
- `a4f1c8d2e7b9_add_wholesale_and_fiscal_foundation.py`: atacado e base fiscal.
- `f2b4c6d8e9f1_add_client_wallet_messaging_and_reversal_controls.py`: clientes, carteira, mensageria e controles de reversao.
- `f9d0e1a2b3c4_add_boleto_financeiro_models.py`: modelos financeiros de boleto.
- `ea3d60221646_merge_migration_heads.py`: merge de heads.

## Observacoes de consistencia

Ha forte uso de constraints por tenant e indices por tenant/empresa/status. Isso e adequado para SaaS, mas exige que qualquer nova funcionalidade preserve filtros por tenant e escopo de empresa.

## Pendencias de modelo para Sprint 2

- Validar se boleto precisa guardar payloads de integracao bancaria, remessa/retorno CNAB, agencia/conta com criptografia, webhook e logs de transmissao.
- Validar se fiscal precisa tabelas de eventos fiscais, inutilizacao, cancelamento, contingencia, assinatura, retorno SEFAZ e armazenamento de XML autorizado.
- Confirmar politica de arquivos persistentes fora do banco.
