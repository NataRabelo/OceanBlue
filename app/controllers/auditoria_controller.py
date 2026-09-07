from flask import Blueprint, abort, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from app.models.db import AuditLog
from app.security.decorators import permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService


auditoria_bp = Blueprint("auditoria", __name__)


@auditoria_bp.get("/view")
@permission_required("visualizar_auditoria")
def pagina():
    return render_template("modulos/auditoria.html")


@auditoria_bp.get("/")
@permission_required("visualizar_auditoria")
def listar():
    try:
        limit = int(request.args.get("limit", "50"))
        before = int(request.args.get("before", "2147483647"))
        company = int(request.args["empresa_id"]) if request.args.get("empresa_id") else None
        if not 1 <= limit <= 100 or not 1 <= before <= 2147483647:
            raise ValueError()
    except ValueError:
        abort(400)
    tenant = get_jwt()["tenant_id"]
    scope = AcessoEmpresaService.obter_escopo(int(get_jwt_identity()), tenant)
    query = AuditLog.query.filter(AuditLog.tenant_id == tenant, AuditLog.id < before)
    companies = AcessoEmpresaService.filtrar_empresa_ids(scope)
    if companies is not None:
        query = query.filter(AuditLog.empresa_id.in_(companies))
    if company is not None:
        AcessoEmpresaService.validar_empresa(company, scope)
        query = query.filter(AuditLog.empresa_id == company)
    records = query.order_by(AuditLog.id.desc()).limit(limit + 1).all()
    rows = [{"id": record.id, "empresa_id": record.empresa_id, "action": record.action,
        "status": record.status, "actor_id": record.actor_id, "request_id": record.request_id,
        "criado_em": record.criado_em.isoformat()} for record in records[:limit]]
    return jsonify(data=rows, next_cursor=rows[-1]["id"] if len(records) > limit else None)
