from flask import current_app, g, jsonify
from flask_jwt_extended import create_access_token, get_jwt

from app.extensions import db, jwt
from app.models.db import Funcionario, PlatformOwner
from app.models.security import RevokedToken


def gerar_token(usuario, scope=None):
    auth_scope = scope or ("platform" if isinstance(usuario, PlatformOwner) else "tenant")

    if auth_scope == "platform":
        return create_access_token(
            identity=str(usuario.id),
            additional_headers={"kid": current_app.config["JWT_SIGNING_KEY_ID"]},
            additional_claims={
                "auth_scope": "platform",
                "session_version": usuario.session_version,
                "tenant_id": None,
                "usuario": usuario.usuario,
                "role_codigo": "platform_owner",
                "role_nome": "Dono da Plataforma",
                "nome": usuario.nome,
            }
        )

    role = usuario.role

    return create_access_token(
        identity=str(usuario.id),
        additional_headers={"kid": current_app.config["JWT_SIGNING_KEY_ID"]},
        additional_claims={
            "auth_scope": "tenant",
            "session_version": usuario.session_version,
            "tenant_id": usuario.tenant_id,
            "usuario": usuario.usuario,
            "role_codigo": role.codigo if role else None,
            "role_nome": role.nome if role else None,
            "nome": usuario.nome,
        }
    )


def get_auth_scope():
    claims = get_jwt()
    return claims.get("auth_scope") or "tenant"


def get_tenant_id(required=True):
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")

    if required and not tenant_id:
        raise Exception("Tenant nao encontrado no token")

    return tenant_id


@jwt.token_in_blocklist_loader
def token_revoked(header, claims):
    if header.get("kid") != current_app.config["JWT_SIGNING_KEY_ID"]:
        return True
    scope = claims.get("auth_scope")
    if scope not in {"platform", "tenant"}:
        return True
    try:
        identity = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        return True
    model = PlatformOwner if scope == "platform" else Funcionario
    user = db.session.get(model, identity, populate_existing=True)
    if not user or not user.ativo or claims.get("session_version") != user.session_version:
        return True
    if scope == "tenant" and (user.tenant_id != claims.get("tenant_id") or not user.role or not user.role.ativo or user.role.tenant_id != user.tenant_id):
        return True
    if db.session.get(RevokedToken, claims.get("jti")):
        return True
    g.auth_user = user
    if scope == "tenant":
        from app.services.acesso_empresa_service import AcessoEmpresaService
        access = AcessoEmpresaService.obter_escopo(user.id, user.tenant_id)
        g.tenant_scope = {
            "tenant_id": user.tenant_id,
            "empresa_ids": access["empresa_ids"],
            "all_companies": AcessoEmpresaService.filtrar_empresa_ids(access) is None,
        }
    db.session.execute(db.text("SELECT set_config('ocean.actor_id', :actor, true), set_config('ocean.actor_scope', :scope, true)"),
                       {"actor": str(user.id), "scope": scope})
    return False


@jwt.revoked_token_loader
def revoked_response(header, claims):
    return jsonify(success=False, message="Sessao invalida ou expirada."), 401
