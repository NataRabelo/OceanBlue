from flask import current_app, jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from app.extensions import db


def public_error(error):
    if isinstance(error, (ValueError, PermissionError)):
        return str(error)
    if isinstance(error, IntegrityError):
        if "saas_quota" in str(getattr(error.orig, "diag", "")) or "saas_quota" in str(error.orig):
            return "Limite do plano atingido."
        return "Dados invalidos ou vinculados a outro registro."
    current_app.logger.error("Falha interna: %s", type(error).__name__)
    return "Nao foi possivel concluir a operacao."


def register_errors(app):
    @app.errorhandler(Exception)
    def handle_error(error):
        db.session.rollback()
        if isinstance(error, HTTPException):
            return jsonify(success=False, message=error.name), error.code
        status = 403 if isinstance(error, PermissionError) else 400 if isinstance(error, (ValueError, IntegrityError)) else 500
        return jsonify(success=False, message=public_error(error)), status
