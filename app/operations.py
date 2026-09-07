import hmac
import json
import logging
import os
import re
import secrets
import shutil
import threading
import time
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

from flask import abort, current_app, g, has_request_context, request


class OperationalFormatter(logging.Formatter):
    def format(self, record):
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
            "event": "application", "error_type": None}
        if isinstance(record.msg, dict):
            payload.update({key: value for key, value in record.msg.items()
                if key in {"event", "request_id", "route", "method", "status", "duration_ms"}})
        else:
            payload["event"] = "application_diagnostic"
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
        elif isinstance(record.args, tuple) and len(record.args) == 1 and re.fullmatch(r"[A-Za-z]+Error", str(record.args[0])):
            payload["error_type"] = record.args[0]
        if has_request_context():
            payload["request_id"] = getattr(g, "request_id", None)
        return json.dumps(payload, ensure_ascii=True)


def storage_probe():
    root = Path(current_app.config["STORAGE_ROOT"])
    if not root.is_absolute() or root.resolve() != root or root.is_symlink() or not root.is_dir():
        raise OSError("Storage unavailable")
    path = root / (".probe-" + secrets.token_hex(16))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(descriptor, b"oceanblue-readiness")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
        path.unlink()


def register_operations(app):
    from alembic.script import ScriptDirectory
    app.config["SCHEMA_REVISION"] = ScriptDirectory(str(Path(app.root_path).parent / "migrations")).get_current_head()
    app.config["STORAGE_ROOT"] = os.getenv("STORAGE_ROOT", str(Path(app.instance_path) / "storage"))
    if not app.testing and not app.debug and Path(app.config["STORAGE_ROOT"]) != Path(app.instance_path) / "storage":
        raise RuntimeError("Storage produtivo deve estar no volume instance/storage coberto pelo backup.")
    app.config["FEATURE_BOLETO"] = app.testing
    app.config["FEATURE_FISCAL"] = app.testing
    app.config["FEATURE_EXTERNAL_PROVIDERS"] = False
    if app.testing or app.debug:
        Path(app.config["STORAGE_ROOT"]).mkdir(parents=True, exist_ok=True, mode=0o700)
    counters = Counter()
    started = time.monotonic()
    lock = threading.Lock()
    app.extensions["operational_metrics"] = (counters, lock)

    @app.before_request
    def begin_request():
        supplied = request.headers.get("X-Request-ID", "")
        g.request_id = supplied if re.fullmatch(r"[a-f0-9]{32}", supplied) else secrets.token_hex(16)
        g.request_started = time.monotonic()
        if not app.testing and request.blueprint in {"boleto", "fiscal"}:
            abort(404)
        if not app.testing and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                storage_probe()
            except OSError:
                abort(503)

    @app.after_request
    def finish_request(response):
        duration = time.monotonic() - getattr(g, "request_started", time.monotonic())
        response.headers["X-Request-ID"] = getattr(g, "request_id", secrets.token_hex(16))
        with lock:
            counters["requests_total"] += 1
            counters["errors_total"] += int(response.status_code >= 500)
            counters["slow_requests_total"] += int(duration > 1)
            counters["duration_seconds_total"] += duration
        app.logger.info({"event": "http_request", "request_id": response.headers["X-Request-ID"],
            "route": request.url_rule.rule if request.url_rule else "unmatched", "method": request.method,
            "status": response.status_code, "duration_ms": round(duration * 1000, 3)})
        return response

    @app.get("/metrics")
    def metrics():
        token = os.getenv("METRICS_TOKEN", "")
        if len(token) < 32 or not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer " + token):
            abort(404)
        with lock:
            values = dict(counters)
        values["uptime_seconds"] = time.monotonic() - started
        try:
            values["storage_free_bytes"] = shutil.disk_usage(app.config["STORAGE_ROOT"]).free
        except OSError:
            values["storage_free_bytes"] = 0
        return "".join(f"oceanblue_{name} {value}\n" for name, value in sorted(values.items())), 200, {"Content-Type": "text/plain; version=0.0.4", "Cache-Control": "no-store"}
