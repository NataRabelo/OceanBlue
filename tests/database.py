from sqlalchemy import text

from app.extensions import db


def reset_test_database():
    if db.engine.url.database != "oceanblue_test":
        raise RuntimeError("Reset permitido somente em oceanblue_test.")
    db.session.remove()
    tables = ", ".join(db.engine.dialect.identifier_preparer.quote(table) for table in db.metadata.tables)
    db.session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    db.session.commit()
