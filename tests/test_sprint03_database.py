import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from tests.test_sprint02_security import security_app
from tests.test_sprint03_transactions import transaction_app, stock_setup, sale_payload, scope
from app.services.pdv_service import PdvService


@pytest.mark.parametrize("table,column", [
    ("produtos_empresa", "valor_compra"), ("funcionarios", "salario"),
    ("vendas", "total"), ("pagamentos_venda", "valor"),
    ("itens_venda", "valor_unitario"), ("lancamentos_financeiros", "valor"),
    ("movimentos_estoque", "valor_unitario"),
])
def test_postgresql_rejects_nan_in_persisted_money(transaction_app, table, column):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        db.session.remove()
        with pytest.raises(IntegrityError):
            with db.engine.begin() as connection:
                connection.execute(text(f"UPDATE {table} SET {column} = 'NaN'::numeric"))


@pytest.mark.parametrize("table,column", [("produtos_empresa", "valor_compra"), ("vendas", "total")])
def test_finite_migration_refuses_inconsistent_legacy_without_data_loss(transaction_app, table, column):
    with transaction_app.app_context():
        _, product_id = stock_setup()
        PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        db.session.remove()
        downgrade(revision="5e6f7a8b9c0d")
        try:
            with db.engine.begin() as connection:
                original = connection.execute(text(f"SELECT {column} FROM {table} WHERE id=1")).scalar_one()
                connection.execute(text(f"UPDATE {table} SET {column}='NaN'::numeric WHERE id=1"))
            with pytest.raises(IntegrityError):
                upgrade()
            with db.engine.connect() as connection:
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "5e6f7a8b9c0d"
                assert connection.execute(text(f"SELECT {column}::text FROM {table} WHERE id=1")).scalar_one() == "NaN"
                assert connection.execute(text("SELECT count(*) FROM vendas")).scalar_one() == 1
                assert not any(check["name"].endswith("_finite") for check in inspect(connection).get_check_constraints("funcionarios"))
        finally:
            with db.engine.begin() as connection:
                connection.execute(text(f"UPDATE {table} SET {column}=:original WHERE id=1"), {"original": original})
            upgrade()


def test_all_numeric_columns_have_database_finite_guards(transaction_app):
    with transaction_app.app_context():
        inspector = inspect(db.engine)
        for table in db.metadata.tables.values():
            numeric = [column.name for column in table.c if isinstance(column.type, db.Numeric)]
            if numeric:
                guard = next(check for check in inspector.get_check_constraints(table.name)
                             if check["name"] == f"ck_{table.name}_finite")
                assert all(column in guard["sqltext"] for column in numeric)
