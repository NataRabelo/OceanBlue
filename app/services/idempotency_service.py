from functools import wraps
import hashlib
from inspect import signature
import json

from app.extensions import db
from app.models.db import OperacaoIdempotente
from app.services.acesso_empresa_service import AcessoEmpresaService


def idempotent(function):
    parameters = signature(function)

    @wraps(function)
    def execute(*args, **kwargs):
        arguments = parameters.bind(*args, **kwargs).arguments
        data = arguments["data"]
        key = data.get("idempotency_key")
        if key is None:
            return function(*args, **kwargs)
        if not isinstance(key, str) or not key.strip() or len(key) > 128:
            raise ValueError("Chave de idempotencia invalida.")
        operation = function.__name__
        for field in ("venda_id", "item_id", "lancamento_id", "fechamento_id", "adiantamento_id"):
            if field in arguments:
                operation += f":{arguments[field]}"
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        record = OperacaoIdempotente.query.filter_by(
            tenant_id=arguments["tenant_id"], funcionario_id=arguments["funcionario_id"],
            operacao=operation, chave=key,
        ).first()
        if record:
            AcessoEmpresaService.validar_empresa(record.empresa_id, arguments["escopo"])
            if record.payload_hash != digest:
                raise ValueError("Chave de idempotencia ja utilizada com outros dados.")
            return record.resposta
        result = function(*args, **kwargs)
        db.session.add(OperacaoIdempotente(
            tenant_id=arguments["tenant_id"], funcionario_id=arguments["funcionario_id"],
            empresa_id=result["empresa_id"], operacao=operation, chave=key,
            payload_hash=digest, resposta=result,
        ))
        return result

    return execute
