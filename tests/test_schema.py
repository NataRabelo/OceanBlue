from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DataError

from app import create_app
from app.extensions import db
from app.models.db import AmbienteBoleto, BancoEmissor, Empresa, LayoutArquivoBoleto, Tenant, TipoEmpresa
from tests.database import reset_test_database


def test_migrated_schema_matches_model_types_indexes_and_foreign_keys():
    with create_app().app_context():
        with db.engine.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), db.metadata)
        assert differences == []


@pytest.mark.parametrize("invalid_legacy_value", [False, True])
def test_schema_upgrade_preserves_rows_and_rolls_back_invalid_legacy_data(invalid_legacy_value):
    with create_app().app_context():
        reset_test_database()
        tenant = Tenant(nome="Schema validation")
        db.session.add(tenant)
        db.session.flush()
        empresa = Empresa(
            tenant_id=tenant.id, cnpj="12.345.678/0001-99", razao_social="Schema validation",
            nome_fantasia="Schema validation", tipo_empresa=TipoEmpresa.MATRIZ,
        )
        db.session.add(empresa)
        db.session.flush()
        for layout in LayoutArquivoBoleto:
            for ambiente in AmbienteBoleto:
                db.session.add(BancoEmissor(
                    tenant_id=tenant.id, empresa_id=empresa.id, banco_codigo="000",
                    banco_nome="Isolated validation", carteira="1", agencia="1", conta="1",
                    codigo_cedente="1", layout_arquivo=layout, ambiente=ambiente,
                ))
        db.session.commit()

        def snapshot():
            with db.engine.connect() as connection:
                return connection.execute(text(
                    "SELECT id, tenant_id, empresa_id, layout_arquivo::text, ambiente::text "
                    "FROM bancos_emissores ORDER BY id"
                )).all()

        expected = snapshot()
        db.session.remove()
        try:
            downgrade(revision="2b3c4d5e6f7a")
            assert snapshot() == expected
            if invalid_legacy_value:
                with db.engine.begin() as connection:
                    connection.execute(text("UPDATE bancos_emissores SET layout_arquivo = 'INVALID' WHERE id = 1"))
                with pytest.raises(DataError):
                    upgrade()
                with db.engine.connect() as connection:
                    assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "2b3c4d5e6f7a"
                assert "layoutarquivoboleto" not in {enum["name"] for enum in inspect(db.engine).get_enums()}
                with db.engine.begin() as connection:
                    connection.execute(text(
                        "UPDATE bancos_emissores SET layout_arquivo = :layout WHERE id = 1"
                    ), {"layout": expected[0][3]})
            upgrade()
            upgrade()
            assert snapshot() == expected
            with db.engine.connect() as connection:
                assert compare_metadata(MigrationContext.configure(connection), db.metadata) == []
        finally:
            db.session.remove()
            upgrade()
            reset_test_database()
