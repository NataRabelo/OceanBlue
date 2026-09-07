import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.db import Funcionario, PlatformOwner, Tenant
from app.models.security import PasswordReset
from app.security.password import hash_password, validate_password, verify_password
from app.services.audit_service import AuditService


DUMMY_HASH = hash_password("dummy-credential-value")


class AuthService:
    @staticmethod
    def logar(data):
        usuario = str(data.get("usuario") or "").strip()
        senha = data.get("senha") or ""
        if not isinstance(senha, str) or len(senha) > 1024 or len(usuario) > 80:
            raise ValueError("Credenciais invalidas")
        scope = data.get("scope") or "tenant"
        tenant_name = str(data.get("tenant") or "").strip()
        user = None
        if scope == "platform":
            user = PlatformOwner.query.filter_by(usuario=usuario).first()
        elif scope == "tenant" and tenant_name:
            user = Funcionario.query.join(Tenant).filter(Tenant.nome == tenant_name, Funcionario.usuario == usuario).first()
        if not user:
            verify_password(senha, DUMMY_HASH)
            raise ValueError("Credenciais invalidas")
        if not verify_password(senha, user.senha_hash) or not user.ativo:
            raise ValueError("Credenciais invalidas")
        if scope == "tenant" and (not user.role or not user.role.ativo or user.role.tenant_id != user.tenant_id):
            raise ValueError("Credenciais invalidas")
        return {"scope": scope, "user": user}

    @staticmethod
    def alterar_senha(user, senha_atual, nova_senha):
        validate_password(nova_senha)
        db.session.refresh(user, with_for_update=True)
        if not verify_password(senha_atual or "", user.senha_hash):
            raise ValueError("Credenciais invalidas")
        user.senha_hash = hash_password(nova_senha)
        AuditService.registrar("auth.password_changed", tenant_id=getattr(user, "tenant_id", None),
                               actor_scope="platform" if isinstance(user, PlatformOwner) else "tenant",
                               actor_id=user.id, entity_type="auth", entity_id=user.id)
        db.session.commit()

    @staticmethod
    def emitir_redefinicao(user, scope, actor_id=None):
        db.session.refresh(user, with_for_update=True)
        token = secrets.token_urlsafe(32)
        db.session.add(PasswordReset(
            token_hash=hashlib.sha256(token.encode()).hexdigest(), scope=scope, user_id=user.id,
            tenant_id=getattr(user, "tenant_id", None), session_version=user.session_version,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        ))
        AuditService.registrar("auth.password_reset_issued", tenant_id=getattr(user, "tenant_id", None),
                               actor_scope=scope if actor_id else "system", actor_id=actor_id, entity_type="auth", entity_id=user.id)
        db.session.commit()
        return token

    @staticmethod
    def redefinir_senha(token, nova_senha):
        validate_password(nova_senha)
        record = PasswordReset.query.filter_by(token_hash=hashlib.sha256(str(token).encode()).hexdigest()).with_for_update().first()
        now = datetime.now(timezone.utc)
        if not record or record.used_at or record.expires_at <= now:
            raise ValueError("Redefinicao invalida ou expirada.")
        model = PlatformOwner if record.scope == "platform" else Funcionario
        user = db.session.execute(db.select(model).where(model.id == record.user_id).with_for_update()).scalar_one_or_none()
        if not user or not user.ativo or user.session_version != record.session_version or getattr(user, "tenant_id", None) != record.tenant_id:
            raise ValueError("Redefinicao invalida ou expirada.")
        user.senha_hash = hash_password(nova_senha)
        record.used_at = now
        AuditService.registrar("auth.password_reset", tenant_id=record.tenant_id, actor_scope=record.scope,
                               actor_id=user.id, entity_type="auth", entity_id=user.id)
        db.session.commit()
