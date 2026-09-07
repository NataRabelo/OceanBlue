from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "ok",
        "service": "OceanBlue API",
        "version": "1.0.0"
    }), 200


@health_bp.route("/ready", methods=["GET"])
def readiness():
    try:
        db.session.execute(text("SELECT 1"))
        db.session.commit()
        return jsonify({
            "status": "ok",
            "database": "ok",
            "service": "OceanBlue API",
        }), 200
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("Readiness check failed: %s", type(exc).__name__)
        return jsonify({
            "status": "error",
            "database": "error",
        }), 503
