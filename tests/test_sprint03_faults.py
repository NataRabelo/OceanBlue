from decimal import Decimal

import pytest
from sqlalchemy import event, text

from app.extensions import db
from app.models.db import (
    CategoriaProduto, CategoriaFinanceira, Cupom, FormaPagamento, Funcionario,
    FuncionarioEmpresa, Produto, ProdutoEmpresa, Tenant, MovimentoEstoque,
    LancamentoFinanceiro, TipoFinanceiro, Venda,
)
from app.services.funcionario_service import FuncionarioService
from app.services.pdv_service import PdvService
from app.services.produto_service import ProdutoService
from tests.test_sprint02_security import security_app
from tests.test_sprint03_transactions import (
    transaction_app, product, employee, scope, parallel, import_rows, sale_payload, LAYOUT_ROWS,
)
from tests.test_sprint03_adversarial import snapshot


@pytest.mark.parametrize("entity,model", [
    ("categorias", CategoriaProduto), ("produtos", ProdutoEmpresa),
    ("funcionarios", FuncionarioEmpresa), ("cupons", Cupom),
    ("formas_pagamento", FormaPagamento), ("categorias_financeiras", CategoriaFinanceira),
])
def test_each_import_layout_rollback_after_actual_insert(transaction_app, entity, model):
    with transaction_app.app_context():
        before = snapshot()

        def fail(*arguments):
            raise RuntimeError("injected import persistence")

        event.listen(model, "after_insert", fail)
        try:
            result = import_rows(entity, [LAYOUT_ROWS[entity]])
            assert result["falhas"] == 1 and not result["confirmado"]
        finally:
            event.remove(model, "after_insert", fail)
        assert snapshot() == before
        assert import_rows(entity, [LAYOUT_ROWS[entity]])["confirmado"]


@pytest.mark.parametrize("model", [Produto, Funcionario])
def test_registration_parent_insert_failure_preserves_all_tables(transaction_app, model):
    with transaction_app.app_context():
        before = snapshot()

        def fail(*arguments):
            raise RuntimeError("injected parent")

        event.listen(model, "after_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                if model is Produto:
                    product()
                else:
                    FuncionarioService.criar(employee(), 1)
        finally:
            event.remove(model, "after_insert", fail)
        assert snapshot() == before


def test_last_quota_between_registration_and_batch(transaction_app):
    with transaction_app.app_context():
        db.session.get(Tenant, 1).limite_produtos = 1
        db.session.commit()

    def create(number):
        if number:
            return import_rows("produtos", [{**LAYOUT_ROWS["produtos"], "categoria": "Only if committed"}])["confirmado"]
        product("Manual")
        return True

    results = parallel(transaction_app, create)
    assert sum(result is True for result in results) == 1
    with transaction_app.app_context():
        assert Produto.query.count() == ProdutoEmpresa.query.count() == 1
        if Produto.query.one().nome == "Manual":
            assert CategoriaProduto.query.count() == 0


def test_concurrent_barcode_updates_preserve_loser(transaction_app):
    with transaction_app.app_context():
        records = [(product(f"Product {number}", codigo_barras=f"{100 + number}").id, f"Product {number}")
                   for number in range(2)]

    def update(number):
        record_id, name = records[number]
        return ProdutoService.atualizar(record_id, {"nome": name, "empresa_id": 1, "codigo_barras": "999"}, 1, scope()).id

    results = parallel(transaction_app, update)
    assert sum(isinstance(result, int) for result in results) == 1
    with transaction_app.app_context():
        codes = [record.codigo_barras for record in Produto.query.order_by(Produto.id).all()]
        assert codes in (["999", "101"], ["100", "999"])


def test_postgresql_orphan_and_ledger_audit_after_mixed_operations(transaction_app):
    with transaction_app.app_context():
        assert import_rows("produtos", [LAYOUT_ROWS["produtos"]])["confirmado"]
        product_id = Produto.query.one().id
        sale = PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        PdvService.cancelar_venda(sale["id"], {"idempotency_key": "audit-cancel"}, 1, scope(), 1)
        PdvService.cancelar_venda(sale["id"], {"idempotency_key": "audit-cancel"}, 1, scope(), 1)
        for table in db.metadata.tables.values():
            for foreign in table.foreign_keys:
                child = foreign.parent
                parent = foreign.column.table.alias()
                target = parent.c[foreign.column.name]
                missing = db.select(child).select_from(table.outerjoin(parent, child == target)).where(
                    child.is_not(None), target.is_(None)
                )
                assert db.session.execute(missing.limit(1)).first() is None, str(foreign)
        stock = ProdutoEmpresa.query.one()
        assert stock.estoque_atual == sum(record.quantidade if record.tipo_movimento.value == "ENTRADA"
            else -record.quantidade for record in MovimentoEstoque.query.all()) == 3
        assert sum((record.valor if record.tipo == TipoFinanceiro.ENTRADA else -record.valor
            for record in LancamentoFinanceiro.query.all()), Decimal(0)) == 0
        assert Venda.query.one().status.value == "CANCELADA"
        print("POSTGRESQL AUDIT: all foreign keys without orphans; stock=3; net finance=0; one cancelled sale")
