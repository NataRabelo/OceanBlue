from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
import time

from sqlalchemy import event, text
import pytest

from app.extensions import db
from app.models.db import LancamentoFinanceiro, ProdutoEmpresa, Venda
from app.services.pdv_service import PdvService
from tests.test_sprint02_security import security_app, login
from tests.test_sprint03_transactions import transaction_app, parallel, sale_payload, scope, stock_setup


def record_measurement(name, values):
    destination = Path('/tmp/load-s06.json')
    report = json.loads(destination.read_text()) if destination.exists() else {}
    report[name] = values
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')


def test_concurrent_audit_reads_bounded_and_tenant_safe(security_app):
    with security_app.app_context():
        db.session.execute(text("INSERT INTO audit_logs (tenant_id, empresa_id, action, criado_em) "
            "SELECT 1, 1, 'LOAD', now() FROM generate_series(1, 10000)"))
        db.session.execute(text("INSERT INTO audit_logs (tenant_id, empresa_id, action, criado_em) "
            "SELECT 2, 3, 'OTHER_TENANT', now() FROM generate_series(1, 10000)"))
        db.session.commit()
    session_client = security_app.test_client()
    assert login(session_client).status_code == 302
    token = session_client.get_cookie('access_token_cookie').value
    barrier = Barrier(8)

    def read_pages(worker):
        client = security_app.test_client()
        client.set_cookie('access_token_cookie', token)
        barrier.wait(timeout=20)
        durations = []
        seen = set()
        cursor = ''
        for number in range(15):
            started = time.monotonic()
            response = client.get('/api/auditoria/?empresa_id=1&limit=50' + cursor)
            durations.append(time.monotonic() - started)
            assert response.status_code == 200
            rows = response.json['data']
            assert len(rows) == 50 and all(row['action'] == 'LOAD' and row['empresa_id'] == 1 for row in rows)
            identifiers = {row['id'] for row in rows}
            assert not seen.intersection(identifiers)
            seen.update(identifiers)
            cursor = f"&before={response.json['next_cursor']}"
        return durations

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=8) as executor:
        durations = sorted(duration for result in executor.map(read_pages, range(8)) for duration in result)
    elapsed = time.monotonic() - started
    record_measurement('audit_wsgi', {'concurrency': 8, 'requests': len(durations), 'rows': 20000,
        'elapsed_seconds': elapsed, 'requests_per_second': len(durations) / elapsed,
        'p50_seconds': durations[math.ceil(len(durations) * .50) - 1],
        'p95_seconds': durations[math.ceil(len(durations) * .95) - 1], 'max_seconds': max(durations),
        'errors': 0, 'transport': 'Flask test client; real PostgreSQL'})
    assert max(durations) < 15


def test_sixteen_writers_cannot_oversell_twelve_units(transaction_app):
    with transaction_app.app_context():
        record_id, product_id = stock_setup(12)
        payloads = [sale_payload(product_id, key=f'load-sale-{number}') for number in range(16)]
    started = time.monotonic()
    results = parallel(transaction_app,
        lambda number: PdvService.criar_venda(payloads[number], 1, scope(), 1), count=16)
    elapsed = time.monotonic() - started
    accepted = [result for result in results if isinstance(result, dict)]
    rejected = [result for result in results if isinstance(result, str)]
    assert len(accepted) == 12 and len(rejected) == 4, results
    with transaction_app.app_context():
        assert db.session.get(ProdutoEmpresa, record_id).estoque_atual == 0
        assert Venda.query.count() == 12
        assert sum(entry.valor for entry in LancamentoFinanceiro.query.all()) == Decimal('120.00')
    record_measurement('sale_contention', {'concurrency': 16, 'stock': 12, 'accepted': 12,
        'rejected_without_stock': 4, 'elapsed_seconds': elapsed, 'ledger': '120.00'})


def test_critical_list_query_count_does_not_grow_per_sale(transaction_app):
    with transaction_app.app_context():
        record_id, product_id = stock_setup(30)
        for number in range(25):
            PdvService.criar_venda(sale_payload(product_id, key=f'query-sale-{number}'), 1, scope(), 1)
    client = transaction_app.test_client()
    assert login(client).status_code == 302
    measurements = {}
    for route in ('/api/pdv/vendas', '/api/financeiro/lancamentos', '/api/estoque/movimentos'):
        counts = []
        for limit in (1, 25):
            statements = []

            def count_query(connection, cursor, statement, parameters, context, many):
                statements.append(statement)

            with transaction_app.app_context():
                event.listen(db.engine, 'before_cursor_execute', count_query)
                try:
                    response = client.get(f'{route}?empresa_id=1&limite={limit}')
                finally:
                    event.remove(db.engine, 'before_cursor_execute', count_query)
            assert response.status_code == 200, response.json
            assert len(response.json['data']) == limit
            counts.append(len(statements))
        measurements[route] = dict(zip(('one_row', 'twenty_five_rows'), counts))
        assert counts[1] <= counts[0] + 2, measurements
        assert counts[1] < 40, measurements
    record_measurement('critical_queries', measurements)


@pytest.mark.parametrize('direction', ['upgrade', 'downgrade'])
def test_migration_lock_failure_preserves_revision_and_sales(transaction_app, direction):
    from flask_migrate import downgrade, upgrade
    with transaction_app.app_context():
        record_id, product_id = stock_setup(10)
        PdvService.criar_venda(sale_payload(product_id), 1, scope(), 1)
        db.session.remove()
        if direction == 'upgrade':
            downgrade(revision='9c0d1e2f3a4b')
        expected = db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        before = db.session.execute(text('SELECT count(*), sum(total) FROM vendas')).one()
        db.session.remove()
        try:
            with db.engine.connect() as blocker:
                blocker.execute(text('LOCK TABLE audit_logs IN ACCESS EXCLUSIVE MODE'))
                result = subprocess.run([sys.executable, '-m', 'flask', '--app', 'wsgi', 'db', direction,
                    *(['9c0d1e2f3a4b'] if direction == 'downgrade' else [])],
                    env={**os.environ, 'PGOPTIONS': '-c lock_timeout=500ms'},
                    capture_output=True, text=True, timeout=20)
                assert result.returncode != 0
                assert 'lock timeout' in result.stderr.lower(), result.stderr
                blocker.rollback()
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == expected
            assert db.session.execute(text('SELECT count(*), sum(total) FROM vendas')).one() == before
            db.session.remove()
        finally:
            upgrade()
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'a0d1e2f3a4b5'
