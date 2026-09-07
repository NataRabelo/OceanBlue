from app.security.errors import public_error
from io import BytesIO

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.extensions import db
from app.security.jwt import get_auth_scope
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.import_export_service import ImportExportService
from app.services.tenant_bootstrap_service import TenantBootstrapService
from app.services.tenant_entitlement_service import TenantEntitlementService

import_export_bp = Blueprint("import_export", __name__)


def _resolver_contexto(required_permission="visualizar_importacao_exportacao"):
    if get_auth_scope() != "tenant":
        raise PermissionError("Esse recurso pertence ao ambiente operacional do tenant.")

    tenant_id = get_jwt().get("tenant_id")
    funcionario_id = int(get_jwt_identity())

    TenantEntitlementService.validar_assinatura(tenant_id)

    escopo = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
    if required_permission and not AcessoEmpresaService.possui_permissao(escopo, required_permission):
        raise PermissionError("Voce nao tem permissao para acessar este modulo.")

    return tenant_id, funcionario_id, escopo


@import_export_bp.route("/view", methods=["GET"])
@jwt_required()
def pagina():
    try:
        _resolver_contexto()
        return render_template("modulos/import_export/import_export.html")
    except PermissionError as exc:
        flash(public_error(exc), "warning")
        return redirect(url_for("main.home"))
    except Exception as exc:
        flash(public_error(exc), "warning")
        return redirect(url_for("main.home"))


@import_export_bp.route("/contexto", methods=["GET"])
@jwt_required()
def contexto():
    try:
        tenant_id, _, escopo = _resolver_contexto()
        dados = ImportExportService.obter_contexto_painel(tenant_id, escopo)
        return jsonify({"success": True, "data": dados})
    except PermissionError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 403
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 400


@import_export_bp.route("/template", methods=["GET"])
@jwt_required()
def baixar_template():
    try:
        tenant_id, _, escopo = _resolver_contexto()
        entidade = request.args.get("entidade", type=str) or ""
        arquivo = ImportExportService.gerar_template(entidade, tenant_id, escopo)

        return send_file(
            BytesIO(arquivo["content"]),
            as_attachment=True,
            download_name=arquivo["filename"],
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except PermissionError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 403
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 400


@import_export_bp.route("/exportar", methods=["GET"])
@jwt_required()
def exportar():
    try:
        tenant_id, _, escopo = _resolver_contexto()
        entidade = request.args.get("entidade", type=str) or ""
        empresa_id = request.args.get("empresa_id", type=int)
        arquivo = ImportExportService.exportar_entidade(entidade, tenant_id, escopo, empresa_id=empresa_id)

        return send_file(
            BytesIO(arquivo["content"]),
            as_attachment=True,
            download_name=arquivo["filename"],
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except PermissionError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 403
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 400


@import_export_bp.route("/importar", methods=["POST"])
@jwt_required()
def importar():
    try:
        tenant_id, funcionario_id, escopo = _resolver_contexto()
        entidade = request.form.get("entidade", type=str) or ""
        arquivo = request.files.get("arquivo")
        resultado = ImportExportService.importar_entidade(
            entidade,
            arquivo,
            tenant_id,
            escopo,
            funcionario_id,
        )

        return jsonify({
            "success": True,
            "message": "Importacao processada com sucesso.",
            "data": resultado,
        })
    except PermissionError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 403
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": public_error(exc)}), 400
