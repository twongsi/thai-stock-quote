import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fund_dashboard"))
import sec_api
from sec_api import ENDPOINTS, SecApiError, SecClient


@pytest.fixture(params=["python", "sec-go"])
def transport(request, monkeypatch, tmp_path):
    bridge = Path(__file__).resolve().parents[1] / "bin/sec-bridge"
    if request.param == "sec-go" and not bridge.exists():
        pytest.skip("Go bridge tested by the sec-bridge CI job")
    monkeypatch.setenv("SEC_GO_BINARY", str(bridge))
    monkeypatch.setattr(sec_api, "HTTP_CACHE_DIR", tmp_path)
    state = {"responses": [], "calls": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            state["calls"].append(self.path)
            assert self.headers["Ocp-Apim-Subscription-Key"] == "fixture-secret"
            status, content_type, body = state["responses"].pop(0)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = SecClient(api_key="fixture-secret", base_url=f"http://127.0.0.1:{server.server_port}",
                       backend=request.param, use_cache=False, min_interval=0)
    try:
        yield client, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def page(items, cursor=""):
    return 200, "application/json", json.dumps({"items": items, "next_cursor": cursor}).encode()


def test_pagination_and_empty_middle_page(transport):
    client, state = transport
    state["responses"] = [page([{"last_val": 1}], "a+b=/"), page([], "next"), page([{"last_val": 2}])]
    assert client.fetch_all(ENDPOINTS["nav"]) == [{"last_val": 1}, {"last_val": 2}]
    from urllib.parse import parse_qs, urlparse
    assert parse_qs(urlparse(state["calls"][1]).query)["next_cursor"] == ["a+b=/"]


def test_204_is_empty_without_json_parse_or_retry(transport):
    client, state = transport
    state["responses"] = [(204, "", b"")]
    assert client.fetch_all(ENDPOINTS["nav"]) == []
    assert len(state["calls"]) == 1


@pytest.mark.parametrize("status,ctype,body", [
    (200, "text/html", b"<html>fixture-secret</html>"),
    (200, "application/json", b""),
    (200, "application/json", b"not-json fixture-secret"),
    (200, "application/json", b'{"message":"fixture-secret"}'),
    (200, "application/json", b'{"items":{}}'),
    (401, "application/json", b"fixture-secret"),
    (403, "text/html", b"fixture-secret"),
    (400, "application/json", b"fixture-secret"),
])
def test_invalid_responses_are_actionable_and_do_not_leak(transport, status, ctype, body):
    client, state = transport
    state["responses"] = [(status, ctype, body)]
    with pytest.raises(SecApiError) as exc:
        client.fetch_all(ENDPOINTS["nav"])
    assert "fixture-secret" not in str(exc.value)
    assert not exc.value.body
    assert len(state["calls"]) == 1


def test_retry_transient(transport, monkeypatch):
    client, state = transport
    state["responses"] = [(429, "application/json", b""), (503, "text/html", b""), page([{"ok": True}])]
    monkeypatch.setattr(sec_api.time, "sleep", lambda _: None)
    assert client.fetch_all(ENDPOINTS["nav"]) == [{"ok": True}]
    assert len(state["calls"]) == 3


def test_repeated_cursor_is_not_silent_truncation(transport):
    client, state = transport
    state["responses"] = [page([{}], "same"), page([{}], "same")]
    with pytest.raises(SecApiError, match="cursor"):
        client.fetch_all(ENDPOINTS["nav"])


def test_page_limit_is_not_silent_truncation(transport):
    client, state = transport
    state["responses"] = [page([{}], "more")]
    with pytest.raises(SecApiError, match="max_pages"):
        client.fetch_all(ENDPOINTS["nav"], max_pages=1)


def test_cache_reuses_valid_page(transport):
    client, state = transport
    client.use_cache = True
    state["responses"] = [page([{"last_val": 2}])]
    assert client.get(ENDPOINTS["nav"]) == client.get(ENDPOINTS["nav"])
    assert len(state["calls"]) == 1


def test_pinned_dependency_matches_lock():
    root = Path(__file__).resolve().parents[1] / "tools/sec-bridge"
    lock = json.loads((root / "sec-go.lock.json").read_text())
    assert f'replace {lock["upstream_module"]} => {lock["module"]} {lock["version"]}' in (root / "go.mod").read_text()
    assert lock["version"].endswith(lock["commit"][:12])


def test_reject_wrong_binary_revision(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(sec_api.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout='{"module":"wrong","version":"latest"}'))
    with pytest.raises(SecApiError, match="ไม่ตรง"):
        SecClient(api_key="fixture-secret", backend="sec-go")


def test_go_network_failure_is_retried_without_exposing_error(monkeypatch):
    from types import SimpleNamespace
    lock = json.loads((Path(__file__).resolve().parents[1] / "tools/sec-bridge/sec-go.lock.json").read_text())
    responses = [
        {"status": 0, "transport_error": True},
        {"status": 200, "content_type": "application/json", "body": '{"items":[],"next_cursor":""}'},
    ]
    def run(args, **kwargs):
        data = lock if "--version" in args else responses.pop(0)
        return SimpleNamespace(stdout=json.dumps(data))
    monkeypatch.setattr(sec_api.subprocess, "run", run)
    monkeypatch.setattr(sec_api.time, "sleep", lambda _: None)
    client = SecClient(api_key="fixture-secret", backend="sec-go", use_cache=False, min_interval=0)
    assert client.fetch_all(ENDPOINTS["nav"]) == []
    assert not responses
