import hmac
import json
import logging
import math
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
            event = record.msg.get("event")
            payload["event"] = event if isinstance(event, str) and event in {"application", "application_diagnostic", "http_request"} else "application_diagnostic"
            request_id = record.msg.get("request_id")
            if isinstance(request_id, str) and re.fullmatch(r"[a-f0-9]{32}", request_id):
                payload["request_id"] = request_id
            if "route" in record.msg:
                payload["route"] = request.url_rule.rule if has_request_context() and request.url_rule else "unmatched"
            if "method" in record.msg:
                method = request.method if has_request_context() else record.msg["method"]
                payload["method"] = method if isinstance(method, str) and method in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"} else "OTHER"
            status = record.msg.get("status")
            if type(status) is int and 100 <= status <= 599:
                payload["status"] = status
            duration = record.msg.get("duration_ms")
            if type(duration) in {int, float} and 0 <= duration <= 86400000 and math.isfinite(duration):
                payload["duration_ms"] = duration
        else:
            payload["event"] = "application_diagnostic"
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
        elif isinstance(record.args, tuple) and len(record.args) == 1 and re.fullmatch(r"[A-Za-z]+Error", str(record.args[0])):
            payload["error_type"] = record.args[0]
        if has_request_context():
            request_id = getattr(g, "request_id", None)
            payload["request_id"] = request_id if isinstance(request_id, str) and re.fullmatch(r"[a-f0-9]{32}", request_id) else None
        return json.dumps(payload, ensure_ascii=True)


def storage_probe():
    root = Path(current_app.config["STORAGE_ROOT"])
    if not root.is_absolute() or root.resolve() != root or root.is_symlink() or not root.is_dir():
        raise OSError("Storage unavailable")
    restore_marker = root.parent / ".oceanblue-restore-incomplete"
    if restore_marker.exists() or restore_marker.is_symlink():
        raise OSError("Storage restore incomplete")
    path = root / (".probe-" + secrets.token_hex(16))
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        sentinel = b"oceanblue-readiness"
        if os.write(descriptor, sentinel) != len(sentinel):
            raise OSError("Storage write incomplete")
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.read(descriptor, len(sentinel) + 1) != sentinel:
            raise OSError("Storage readback mismatch")
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
    counters = Counter(requests_total=0, errors_total=0, slow_requests_total=0, duration_seconds_total=0)
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
        finished = time.monotonic()
        duration = max(0, finished - getattr(g, "request_started", finished))
        if not getattr(g, "request_id", None):
            g.request_id = secrets.token_hex(16)
        response.headers["X-Request-ID"] = g.request_id
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
        authorization = request.headers.get("Authorization", "")
        if len(token) < 32 or not token.isascii() or not authorization.isascii() or not hmac.compare_digest(authorization, "Bearer " + token):
            abort(404)
        with lock:
            values = dict(counters)
        values["uptime_seconds"] = time.monotonic() - started
        try:
            values["storage_free_bytes"] = shutil.disk_usage(app.config["STORAGE_ROOT"]).free
        except OSError:
            values["storage_free_bytes"] = 0
        return "".join(f"oceanblue_{name} {value}\n" for name, value in sorted(values.items())), 200, {"Content-Type": "text/plain; version=0.0.4", "Cache-Control": "no-store"}
