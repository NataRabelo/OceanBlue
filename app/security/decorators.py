from functools import wraps

from flask import flash, jsonify, redirect, request, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException

from app.security.jwt import get_auth_scope
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.tenant_entitlement_service import TenantEntitlementService


def permission_required(permissao_codigo):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
                if get_auth_scope() != "tenant":
                    return jsonify({
                        "success": False,
                        "message": "Esse recurso pertence ao painel operacional do tenant."
                    }), 403

                tenant_id = get_jwt().get("tenant_id")
                TenantEntitlementService.validar_assinatura(tenant_id)
                funcionario_id = int(get_jwt_identity())
                escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)

                if permissao_codigo.startswith(("criar_", "editar_", "excluir_")) and permissao_codigo.rsplit("_", 1)[-1] in {"role", "permission", "funcionario"} and (
                    not AcessoEmpresaService.eh_admin(escopo) or AcessoEmpresaService.filtrar_empresa_ids(escopo) is not None
                ):
                    raise PermissionError("Administracao de acessos restrita ao administrador do tenant.")

                if not AcessoEmpresaService.possui_permissao(escopo, permissao_codigo):
                    return jsonify({
                        "success": False,
                        "message": "Voce nao tem permissao para executar esta acao."
                    }), 403

                return fn(*args, **kwargs)
            except PermissionError as e:
                return jsonify({
                    "success": False,
                    "message": str(e)
                }), 403
            except JWTExtendedException:
                return jsonify({
                    "success": False,
                    "message": "Sessao invalida ou expirada."
                }), 401

        return wrapper

    return decorator


def ui_permission_required(permissao_codigo, redirect_endpoint="main.home"):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
                auth_scope = get_auth_scope()
                if auth_scope != "tenant":
                    if auth_scope == "platform":
                        flash("Esse recurso pertence ao painel operacional do tenant.", "warning")
                        return redirect(url_for("platform.home"))

                    flash("Esse recurso pertence ao painel operacional do tenant.", "warning")
                    return redirect(url_for("auth.login"))

                tenant_id = get_jwt().get("tenant_id")
                TenantEntitlementService.validar_assinatura(tenant_id)
                funcionario_id = int(get_jwt_identity())
                escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)

                if not AcessoEmpresaService.possui_permissao(escopo, permissao_codigo):
                    flash("Voce nao tem permissao para acessar essa area.", "warning")
                    return redirect(url_for(redirect_endpoint))

                request.current_user_scope = escopo
                return fn(*args, **kwargs)
            except PermissionError as e:
                flash(str(e), "warning")
                return redirect(url_for(redirect_endpoint))
            except JWTExtendedException:
                flash("Sua sessao expirou. Faca login novamente.", "warning")
                return redirect(url_for("auth.login"))

        return wrapper

    return decorator


def platform_owner_required(api=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
                if get_auth_scope() != "platform":
                    raise PermissionError("Acesso restrito ao dono da plataforma.")

                return fn(*args, **kwargs)
            except PermissionError as e:
                if api:
                    return jsonify({"success": False, "message": str(e)}), 403

                flash(str(e), "warning")
                return redirect(url_for("auth.login"))
            except JWTExtendedException:
                if api:
                    return jsonify({
                        "success": False,
                        "message": "Sessao invalida ou expirada."
                    }), 401

                flash("Sua sessao expirou. Faca login novamente.", "warning")
                return redirect(url_for("auth.login"))

        return wrapper

    return decorator
