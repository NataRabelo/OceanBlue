from flask import Blueprint, current_app, jsonify
from pathlib import Path
from sqlalchemy import text

from app.extensions import db
from app.operations import storage_probe

health_bp = Blueprint("health", __name__)
RELEASE_VERSION = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()

@health_bp.route("/health", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "ok",
        "service": "OceanBlue API",
        "version": RELEASE_VERSION
    }), 200


@health_bp.route("/ready", methods=["GET"])
def readiness():
    try:
        db.session.execute(text("SELECT 1"))
        revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision != current_app.config["SCHEMA_REVISION"]:
            raise RuntimeError("Schema unavailable")
        db.session.commit()
        try:
            storage_probe()
        except OSError:
            return jsonify(status="error", database="ok", storage="error"), 503
        return jsonify({
            "status": "ok",
            "database": "ok",
            "storage": "ok",
            "service": "OceanBlue API",
        }), 200
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("Readiness check failed: %s", type(exc).__name__)
        return jsonify({
            "status": "error",
            "database": "error",
        }), 503
