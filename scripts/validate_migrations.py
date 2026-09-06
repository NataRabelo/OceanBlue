import json

from scripts.test_environment import configure_test_environment


def main():
    configure_test_environment()
    from alembic.script import ScriptDirectory
    from flask_migrate import downgrade, upgrade
    from sqlalchemy import inspect, text

    from app import create_app
    from app.extensions import db

    app = create_app()
    with app.app_context():
        if inspect(db.engine).get_table_names():
            raise RuntimeError("Validacao exige oceanblue_test vazio; recrie o servico db-test.")
        config = app.extensions["migrate"].migrate.get_config("migrations")
        script = ScriptDirectory.from_config(config)
        revisions = list(reversed(list(script.walk_revisions())))
        assert len(script.get_heads()) == 1, "Historico deve ter um unico head."
        for revision in revisions:
            upgrade(revision=revision.revision)
            if revision.down_revision is None:
                db.session.execute(text("INSERT INTO tenants (nome, criado_em, atualizado_em) VALUES ('Migration sentinel', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
                db.session.commit()
            print(f"UPGRADE OK {revision.revision}", flush=True)
        upgrade()
        assert db.session.execute(text("SELECT count(*) FROM tenants WHERE nome = 'Migration sentinel'")).scalar_one() == 1
        assert db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == script.get_current_head()
        db.session.remove()
        downgrade(revision="base")
        assert set(inspect(db.engine).get_table_names()) <= {"alembic_version"}
        assert not inspect(db.engine).get_enums(), "Downgrade deixou tipos ENUM orfaos."
        print("DOWNGRADE BASE OK", flush=True)
        upgrade()
        db.session.remove()
        actual_tables = set(inspect(db.engine).get_table_names()) - {"alembic_version"}
        assert actual_tables == set(db.metadata.tables), actual_tables.symmetric_difference(db.metadata.tables)
        for table in db.metadata.tables.values():
            actual_columns = {column["name"] for column in inspect(db.engine).get_columns(table.name)}
            assert actual_columns == set(table.columns.keys()), table.name
        print(json.dumps({"head": script.get_current_head(), "revisions": [revision.revision for revision in revisions], "tables": len(actual_tables), "upgrade_downgrade_upgrade": "OK"}), flush=True)


if __name__ == "__main__":
    main()
