import errno
import json
import os
from pathlib import Path
import signal
import sys
import time

from scripts.validate_security_smoke import request_status


def wait_ready():
    started = time.monotonic()
    while time.monotonic() - started < 25:
        try:
            if request_status('/readiness')[0] == 200:
                return time.monotonic() - started
        except OSError:
            pass
        time.sleep(.1)
    raise AssertionError('Readiness did not recover')


def main():
    mode = sys.argv[1]
    assert os.geteuid() == 1000
    if mode == 'worker':
        wait_ready()
        children = Path('/proc/1/task/1/children').read_text().split()
        assert len(children) == 1, children
        previous = int(children[0])
        started = time.monotonic()
        os.kill(previous, signal.SIGKILL)
        while time.monotonic() - started < 10:
            current = Path('/proc/1/task/1/children').read_text().split()
            if current and str(previous) not in current:
                break
            time.sleep(.1)
        assert current and str(previous) not in current
        wait_ready()
        print(json.dumps({'fault': 'SIGKILL Gunicorn worker', 'recovery_seconds': time.monotonic() - started,
            'previous_pid': previous, 'replacement_pids': current}))
    elif mode == 'restore-marker':
        marker = Path('/app/instance/.oceanblue-restore-incomplete')
        assert not marker.exists()
        wait_ready()
        try:
            marker.write_text('Synthetic interrupted restore; do not serve writes', encoding='utf-8')
            assert request_status('/health')[0] == 200
            status, body = request_status('/readiness')
            assert status == 503 and json.loads(body)['storage'] == 'error'
            from app import create_app
            response = create_app().test_client().post('/login', base_url='https://localhost')
            assert response.status_code == 503
        finally:
            marker.unlink()
        recovered = wait_ready()
        print(json.dumps({'fault': 'incomplete restore marker', 'health': 200, 'readiness': 503,
            'writes': 503, 'recovery_seconds': recovered}))
    elif mode == 'full-storage':
        root = Path('/app/instance/storage')
        capacity = os.statvfs(root).f_blocks * os.statvfs(root).f_frsize
        assert 0 < capacity <= 2 * 1024 * 1024, 'Only a bounded disposable tmpfs may be filled'
        wait_ready()
        sentinel = root / 'synthetic-full-probe'
        try:
            with sentinel.open('wb', buffering=0) as stream:
                try:
                    for number in range(4096):
                        stream.write(b'x' * 4096)
                    raise AssertionError('Expected ENOSPC')
                except OSError as error:
                    assert error.errno == errno.ENOSPC
            assert request_status('/health')[0] == 200
            status, body = request_status('/readiness')
            assert status == 503 and json.loads(body)['storage'] == 'error'
            from app import create_app
            response = create_app().test_client().post('/login', base_url='https://localhost')
            assert response.status_code == 503
        finally:
            sentinel.unlink(missing_ok=True)
        recovered = wait_ready()
        print(json.dumps({'fault': 'real ENOSPC', 'capacity_bytes': capacity, 'health': 200,
            'readiness': 503, 'writes': 503, 'recovery_seconds': recovered}))
    else:
        raise ValueError('Unknown fault')


if __name__ == '__main__':
    main()
