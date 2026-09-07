from flask import g, has_request_context
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, with_loader_criteria

from app.extensions import db
from app.models.db import Boleto, Cupom, Empresa, NotaFiscalVenda, Tenant, Venda


def current_scope():
    return getattr(g, "tenant_scope", None) if has_request_context() else None


def criteria(model, scope):
    tenant_id = scope["tenant_id"]
    expressions = []
    if hasattr(model, "tenant_id"):
        expressions.append(model.tenant_id == tenant_id)
    if model is Tenant:
        expressions.append(model.id == tenant_id)
    company_ids = scope["empresa_ids"]
    if not scope["all_companies"]:
        if model is Empresa:
            expressions.append(model.id.in_(company_ids))
        elif hasattr(model, "empresa_id"):
            expressions.append(db.or_(model.empresa_id.is_(None), model.empresa_id.in_(company_ids)) if model is Cupom else model.empresa_id.in_(company_ids))
    for field, parent in (("boleto_id", Boleto), ("venda_id", Venda), ("nota_id", NotaFiscalVenda)):
        if hasattr(model, field):
            parent_query = db.select(parent.id).where(parent.tenant_id == tenant_id)
            if not scope["all_companies"]:
                parent_query = parent_query.where(parent.empresa_id.in_(company_ids))
            column = getattr(model, field)
            expressions.append(db.or_(column.is_(None), column.in_(parent_query)))
    return expressions


@event.listens_for(Session, "do_orm_execute")
def restrict_queries(state):
    scope = current_scope()
    if not scope or not state.is_orm_statement:
        return
    for mapper in db.Model.registry.mappers:
        model = mapper.class_
        for expression in criteria(model, scope):
            state.statement = state.statement.options(with_loader_criteria(model, expression, include_aliases=True))


@event.listens_for(Session, "before_flush")
def restrict_writes(session, context, instances):
    scope = current_scope()
    if not scope:
        return
    for record in session.new | session.dirty | session.deleted:
        tenant_id = getattr(record, "tenant_id", None)
        if tenant_id is not None and tenant_id != scope["tenant_id"]:
            raise PermissionError("Registro indisponivel neste tenant.")
        company_id = getattr(record, "empresa_id", None)
        if company_id is not None and not scope["all_companies"] and company_id not in scope["empresa_ids"]:
            raise PermissionError("Registro indisponivel nesta empresa.")
        for field, parent in (("boleto_id", Boleto), ("venda_id", Venda), ("nota_id", NotaFiscalVenda)):
            parent_id = getattr(record, field, None)
            if parent_id is not None:
                statement = db.select(parent.id).where(parent.id == parent_id, *criteria(parent, scope))
                if session.execute(statement).scalar_one_or_none() is None:
                    raise PermissionError("Vinculo indisponivel neste escopo.")


@event.listens_for(Session, "after_begin")
def identify_audit_actor(session, transaction, connection):
    user = getattr(g, "auth_user", None) if has_request_context() else None
    connection.execute(db.text("SELECT set_config('ocean.actor_id', :actor, true), set_config('ocean.actor_scope', :scope, true)"),
                       {"actor": str(inspect(user).identity[0]) if user else "", "scope": ("tenant" if hasattr(type(user), "tenant_id") else "platform") if user else ""})
