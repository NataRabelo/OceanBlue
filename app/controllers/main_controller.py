from app.security.errors import public_error
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, send_from_directory, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.security.decorators import ui_permission_required
from app.security.jwt import get_auth_scope
from app.services.acesso_empresa_service import AcessoEmpresaService

main_bp = Blueprint("main", __name__)


def _obter_diretorio_favicon():
    return Path(current_app.static_folder) / "favicon"


def _servir_arquivo_favicon(nome_arquivo, fallback=None):
    diretorio = _obter_diretorio_favicon()
    arquivo = diretorio / nome_arquivo
    if arquivo.exists():
        return send_from_directory(diretorio, nome_arquivo)

    if fallback:
        arquivo_fallback = diretorio / fallback
        if arquivo_fallback.exists():
            return send_from_directory(diretorio, fallback)

    return "", 204


def _redirecionar_platform_owner():
    if get_auth_scope() == "platform":
        flash("Esse ambiente pertence ao tenant. Use o painel da plataforma.", "warning")
        return redirect(url_for("platform.home"))
    return None


def _obter_escopo_tenant():
    tenant_id = get_jwt().get("tenant_id")
    funcionario_id = int(get_jwt_identity())
    return AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)


@main_bp.route("/", methods=["GET"])
def index():
    try:
        return redirect(url_for("auth.login"))
    except Exception as e:
        flash("Erro ao redirecionar para a tela de login: " + public_error(e), "warning")
        return 404


@main_bp.route("/favicon.ico", methods=["GET"])
def favicon():
    return _servir_arquivo_favicon("favicon.ico", fallback="favicon.svg")


@main_bp.route("/site.webmanifest", methods=["GET"])
def site_webmanifest():
    return _servir_arquivo_favicon("site.webmanifest")


@main_bp.route("/browserconfig.xml", methods=["GET"])
def browserconfig():
    return _servir_arquivo_favicon("browserconfig.xml")


@main_bp.route("/home", methods=["GET"])
@jwt_required()
def home():
    try:
        if get_auth_scope() == "platform":
            return redirect(url_for("platform.home"))

        return render_template("pages/home.html")

    except Exception as e:
        flash("Erro ao redirecionar para a home: " + public_error(e), "warning")
        return redirect(url_for("auth.login"))


@main_bp.route("/configuracoes/home", methods=["GET"])
@jwt_required()
def settings_home():
    try:
        redirect_response = _redirecionar_platform_owner()
        if redirect_response:
            return redirect_response

        escopo = _obter_escopo_tenant()
        if not AcessoEmpresaService.possui_acesso_configuracoes(escopo):
            flash("Voce nao tem permissao para acessar as configuracoes do sistema.", "warning")
            return redirect(url_for("main.home"))

        return render_template("pages/home_configuracoes.html")

    except PermissionError as e:
        flash(public_error(e), "warning")
        return redirect(url_for("main.home"))
    except Exception as e:
        flash("Erro ao redirecionar para as configuracoes: " + public_error(e), "warning")
        return redirect(url_for("main.home"))


@main_bp.route("/pdv/home", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_pdv")
def pdv_home():
    try:
        redirect_response = _redirecionar_platform_owner()
        if redirect_response:
            return redirect_response

        return render_template("pages/home_pdv.html")

    except Exception as e:
        flash("Erro ao redirecionar para o pdv: " + public_error(e), "warning")
        return redirect(url_for("main.home"))


@main_bp.route("/estoque/home", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_produto")
def estoque_home():
    try:
        redirect_response = _redirecionar_platform_owner()
        if redirect_response:
            return redirect_response

        return render_template("pages/home_estoque.html")

    except Exception as e:
        flash("Erro ao redirecionar para o estoque: " + public_error(e), "warning")
        return redirect(url_for("main.home"))


@main_bp.route("/financeiro/home", methods=["GET"])
@jwt_required()
@ui_permission_required("visualizar_financeiro")
def financeiro_home():
    try:
        redirect_response = _redirecionar_platform_owner()
        if redirect_response:
            return redirect_response

        return render_template("pages/home_financeiro.html")

    except Exception as e:
        flash("Erro ao redirecionar para o financeiro: " + public_error(e), "warning")
        return redirect(url_for("main.home"))
