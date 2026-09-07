from functools import wraps
from inspect import signature

from flask import current_app

from app.extensions import db
from app.models.db import Tenant


def save():
    if db.session.info.get("atomic_operation"):
        db.session.flush()
    else:
        db.session.commit()


def after_commit(callback):
    operation = db.session.info.get("atomic_operation")
    if operation is None:
        return callback()
    operation["callbacks"].append(callback)


def atomic_operation(function):
    parameters = signature(function)

    @wraps(function)
    def execute(*args, **kwargs):
        arguments = parameters.bind(*args, **kwargs).arguments
        tenant_id = arguments["tenant_id"]
        existing = db.session.info.get("atomic_operation")
        if existing:
            if existing["tenant_id"] != tenant_id:
                raise PermissionError("Operacao deve pertencer a um unico tenant.")
            return function(*args, **kwargs)
        operation = {"tenant_id": tenant_id, "callbacks": []}
        try:
            with db.session.no_autoflush:
                db.session.execute(db.text("SELECT pg_advisory_xact_lock(7202, :tenant)"), {"tenant": tenant_id})
                tenant = db.session.execute(
                    db.select(Tenant).where(Tenant.id == tenant_id)
                ).scalar_one_or_none()
            if tenant is None:
                raise PermissionError("Tenant nao encontrado.")
            for record in list(db.session.identity_map.values()):
                if record not in db.session.dirty and record not in db.session.deleted:
                    db.session.expire(record)
            db.session.info["atomic_operation"] = operation
            result = function(*args, **kwargs)
            if arguments.get("persistir", True):
                db.session.commit()
            else:
                db.session.flush()
        except Exception:
            db.session.rollback()
            raise
        finally:
            db.session.info.pop("atomic_operation", None)
        if arguments.get("persistir", True):
            for callback in operation["callbacks"]:
                try:
                    callback()
                except Exception:
                    db.session.rollback()
                    current_app.logger.warning("Falha na notificacao posterior a operacao confirmada.")
        return result

    return execute
