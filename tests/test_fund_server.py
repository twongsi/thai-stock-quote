"""HTTP regressions: client errors, source errors and static path containment."""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fund_dashboard'))
import server
from demo_data import DemoClient
from sec_api import SecApiError


@pytest.fixture
def http_server(monkeypatch, tmp_path):
    static = tmp_path / 'static'
    static.mkdir()
    (static / 'index.html').write_text('dashboard')
    sibling = tmp_path / 'static-private'
    sibling.mkdir()
    (sibling / 'hidden.txt').write_text('must not be served')
    monkeypatch.setattr(server, 'STATIC_DIR', static)
    monkeypatch.setattr(server, '_state', {'client': DemoClient(), 'demo': True})
    httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}'
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def request(base, path):
    try:
        response = urllib.request.urlopen(base + path, timeout=5)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, response.read()


@pytest.mark.parametrize('path', [
    '/api/search?q=SCB&limit=bad', '/api/funds?limit=-1',
    '/api/fund?code=SCBNDQ&years=abc', '/api/compare?codes=SCBNDQ&years=21',
    '/api/quote?asset_type=fund&symbol=SCBNDQ&years=abc',
])
def test_invalid_numbers_are_client_errors(http_server, path):
    status, body = request(http_server, path)
    assert status == 400
    assert json.loads(body)['error']


@pytest.mark.parametrize('query', ['symbol=DOES-NOT-EXIST', 'symbol=SCBNDQ&class=WRONG'])
def test_unknown_fund_or_class_is_not_upstream_failure(http_server, query):
    status, body = request(http_server, '/api/quote?asset_type=fund&' + query)
    assert status == 404
    assert json.loads(body)['error']


def test_upstream_failure_remains_bad_gateway(http_server, monkeypatch):
    def failed():
        raise SecApiError('SEC unavailable', 503)
    monkeypatch.setattr(server, 'get_client', failed)
    assert request(http_server, '/api/quote?asset_type=fund&symbol=SCBNDQ')[0] == 502


def test_static_sibling_cannot_be_read(http_server):
    assert request(http_server, '/')[0] == 200
    status, body = request(http_server, '/../static-private/hidden.txt')
    assert status == 404
    assert b'must not be served' not in body


def test_unexpected_error_does_not_expose_details(http_server, monkeypatch):
    def failed():
        raise RuntimeError('private internal detail')
    monkeypatch.setattr(server, 'get_client', failed)
    status, body = request(http_server, '/api/quote?asset_type=fund&symbol=SCBNDQ')
    assert status == 500
    assert b'private internal detail' not in body
