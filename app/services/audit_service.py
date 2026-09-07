from flask import g, has_request_context, request

from app.extensions import db
from app.models.db import AuditLog
from app.services.time_service import TimeService


class AuditService:
    @staticmethod
    def registrar(
        action,
        *,
        tenant_id=None,
        empresa_id=None,
        actor_scope=None,
        actor_id=None,
        entity_type=None,
        entity_id=None,
        status="SUCCESS",
        details=None,
        commit=False,
    ):
        ip_address = None
        user_agent = None
        request_path = None
        request_method = None

        if has_request_context():
            ip_address = request.remote_addr
            if ip_address and "," in ip_address:
                ip_address = ip_address.split(",", 1)[0].strip()
            request_path = request.url_rule.rule if request.url_rule else "unmatched"
            request_method = request.method

        log = AuditLog(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            actor_scope=actor_scope,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            status=status,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            request_id=getattr(g, "request_id", None) if has_request_context() else None,
            criado_em=TimeService.now_utc_naive(),
        )
        db.session.add(log)
        if commit:
            db.session.commit()
        return log
