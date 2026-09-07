from flask import Blueprint, abort, jsonify, render_template, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from app.models.db import AuditLog
from app.security.decorators import permission_required
from app.services.acesso_empresa_service import AcessoEmpresaService


auditoria_bp = Blueprint("auditoria", __name__)


def _positive_integer_argument(name, default=None, maximum=2147483647):
    values = request.args.getlist(name)
    if not values:
        return default
    if len(values) != 1:
        abort(400)
    value = values[0]
    if not value or len(value) > 10 or not value.isascii() or not value.isdecimal():
        abort(400)
    number = int(value)
    if not 1 <= number <= maximum:
        abort(400)
    return number


@auditoria_bp.get("/view")
@permission_required("visualizar_auditoria")
def pagina():
    return render_template("modulos/auditoria.html")


@auditoria_bp.get("/")
@permission_required("visualizar_auditoria")
def listar():
    limit = _positive_integer_argument("limit", default=50, maximum=100)
    before = _positive_integer_argument("before")
    company = _positive_integer_argument("empresa_id")
    tenant = get_jwt()["tenant_id"]
    scope = AcessoEmpresaService.obter_escopo(int(get_jwt_identity()), tenant)
    query = AuditLog.query.filter(AuditLog.tenant_id == tenant)
    if before is not None:
        query = query.filter(AuditLog.id < before)
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
