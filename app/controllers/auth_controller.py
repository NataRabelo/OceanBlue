import hmac
import secrets
from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_jwt_extended import get_jwt, jwt_required, set_access_cookies, unset_jwt_cookies
from sqlalchemy.dialects.postgresql import insert

from app.extensions import db
from app.models.db import Funcionario
from app.models.security import RevokedToken
from app.security.decorators import permission_required
from app.security.errors import public_error
from app.security.jwt import gerar_token
from app.security.rate_limit import LoginRateLimiter
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService


auth_bp = Blueprint("auth", __name__)


def _rate_limit():
    identity = "|".join(str(request.form.get(field) or ("tenant" if field == "scope" else "")).strip().lower() for field in ("scope", "tenant", "usuario"))
    limits = [
        (f"ip:{request.remote_addr}", current_app.config["LOGIN_RATE_LIMIT_ATTEMPTS"] * 10),
        (f"account:{identity}", current_app.config["LOGIN_RATE_LIMIT_ATTEMPTS"]),
    ]
    for key, maximum in limits:
        allowed, retry = LoginRateLimiter.hit(key, maximum, current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"])
        if not allowed:
            return retry
    return 0


def _audit(action, status, auth_data=None):
    user = (auth_data or {}).get("user")
    AuditService.registrar(action, tenant_id=getattr(user, "tenant_id", None),
                           actor_scope=(auth_data or {}).get("scope"), actor_id=getattr(user, "id", None),
                           entity_type="auth", status=status, commit=True)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        session.setdefault("login_csrf", secrets.token_urlsafe(32))
        return render_template("pages/login.html")
    csrf = request.form.get("login_csrf") or ""
    if not csrf or not hmac.compare_digest(csrf, session.get("login_csrf", "")):
        return jsonify(success=False, message="Formulario expirado. Recarregue a pagina."), 400
    retry = _rate_limit()
    if retry:
        _audit("auth.login_rate_limited", "BLOCKED")
        flash("Muitas tentativas de login. Aguarde e tente novamente.", "warning")
        return render_template("pages/login.html"), 429, {"Retry-After": str(retry)}
    try:
        auth_data = AuthService.logar(request.form)
        token = gerar_token(auth_data["user"], auth_data["scope"])
        _audit("auth.login", "SUCCESS", auth_data)
        session.pop("login_csrf", None)
        response = redirect(url_for("platform.home" if auth_data["scope"] == "platform" else "main.home"))
        set_access_cookies(response, token)
        return response
    except ValueError:
        db.session.rollback()
        _audit("auth.login", "FAILURE")
        flash("Credenciais invalidas", "warning")
        return render_template("pages/login.html"), 401


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    claims = get_jwt()
    db.session.execute(insert(RevokedToken).values(
        jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc),
    ).on_conflict_do_nothing())
    _audit("auth.logout", "SUCCESS", {"user": g.auth_user, "scope": claims["auth_scope"]})
    response = redirect(url_for("auth.login"))
    unset_jwt_cookies(response)
    return response


@auth_bp.route("/senha", methods=["GET", "POST"])
@jwt_required()
def alterar_senha():
    if request.method == "GET":
        return render_template("pages/password.html", reset=False)
    data = request.get_json(silent=True) or request.form
    try:
        AuthService.alterar_senha(g.auth_user, data.get("senha_atual"), data.get("nova_senha"))
    except ValueError as error:
        db.session.rollback()
        if request.is_json:
            raise
        flash(public_error(error), "warning")
        return render_template("pages/password.html", reset=False), 400
    response = _password_success("Senha alterada. Entre novamente.")
    unset_jwt_cookies(response)
    return response


@auth_bp.route("/api/auth/funcionarios/<int:funcionario_id>/redefinicao", methods=["POST"])
@permission_required("editar_funcionario")
def emitir_redefinicao(funcionario_id):
    user = Funcionario.query.filter_by(id=funcionario_id, tenant_id=get_jwt()["tenant_id"]).first()
    if not user:
        raise ValueError("Funcionario nao encontrado.")
    token = AuthService.emitir_redefinicao(user, "tenant", actor_id=g.auth_user.id)
    return jsonify(success=True, token=token, expires_in=900)


@auth_bp.route("/redefinir-senha", methods=["GET", "POST"])
def redefinir_senha():
    if request.method == "GET":
        session.setdefault("login_csrf", secrets.token_urlsafe(32))
        return render_template("pages/password.html", reset=True)
    data = request.get_json(silent=True) or request.form
    allowed, retry = LoginRateLimiter.hit(f"reset:{request.remote_addr}", 10, 300)
    if not allowed:
        return jsonify(success=False, message="Aguarde para tentar novamente."), 429, {"Retry-After": str(retry)}
    if not hmac.compare_digest(str(data.get("login_csrf") or ""), session.get("login_csrf", "missing")):
        return jsonify(success=False, message="Formulario expirado."), 400
    try:
        AuthService.redefinir_senha(data.get("token"), data.get("nova_senha"))
    except ValueError as error:
        db.session.rollback()
        if request.is_json:
            raise
        flash(public_error(error), "warning")
        return render_template("pages/password.html", reset=True), 400
    response = _password_success("Senha redefinida. Entre novamente.")
    unset_jwt_cookies(response)
    return response


def _password_success(message):
    if request.is_json:
        return jsonify(success=True, message=message)
    flash(message, "success")
    return redirect(url_for("auth.login"))
