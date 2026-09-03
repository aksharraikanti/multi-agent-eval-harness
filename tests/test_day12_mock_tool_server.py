"""Day 12: mock tool server v1 — a small local HTTP server with
deterministic, pre-scripted responses.

Uses real HTTP requests (stdlib urllib) against a real local socket, not
mocked internals — the point of this component is that something can
make an actual HTTP call and get a real response back.
"""

import json
import urllib.error
import urllib.request

import pytest

from harness.mock_tool_server import MockToolServer

SCRIPT = {
    ("GET", "/projects"): (200, {"projects": ["DEMO", "TEST"]}),
    ("POST", "/tickets"): (201, {"id": "DEMO-42", "status": "created"}),
}


def _get(url: str, path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url + path) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url: str, path: str) -> tuple[int, dict]:
    request = urllib.request.Request(url + path, data=b"{}", method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_url_raises_before_start():
    server = MockToolServer(SCRIPT)

    with pytest.raises(RuntimeError):
        _ = server.url


def test_scripted_get_returns_the_canned_response():
    with MockToolServer(SCRIPT) as server:
        status, body = _get(server.url, "/projects")

    assert status == 200
    assert body == {"projects": ["DEMO", "TEST"]}


def test_scripted_post_returns_the_canned_response():
    with MockToolServer(SCRIPT) as server:
        status, body = _post(server.url, "/tickets")

    assert status == 201
    assert body == {"id": "DEMO-42", "status": "created"}


def test_unscripted_request_returns_404_with_a_json_error_body():
    with MockToolServer(SCRIPT) as server:
        status, body = _get(server.url, "/nonexistent")

    assert status == 404
    assert "error" in body
    assert "/nonexistent" in body["error"]


def test_wrong_method_for_a_scripted_path_is_unscripted():
    # /projects is only scripted for GET — a POST to it should 404, not
    # accidentally match.
    with MockToolServer(SCRIPT) as server:
        status, _ = _post(server.url, "/projects")

    assert status == 404


def test_server_handles_multiple_requests_in_one_session():
    with MockToolServer(SCRIPT) as server:
        first = _get(server.url, "/projects")
        second = _post(server.url, "/tickets")
        third = _get(server.url, "/projects")

    assert first == (200, {"projects": ["DEMO", "TEST"]})
    assert second == (201, {"id": "DEMO-42", "status": "created"})
    assert third == first


def test_url_is_unusable_after_stop():
    server = MockToolServer(SCRIPT)
    server.start()
    url = server.url
    server.stop()

    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(url + "/projects", timeout=1)


def test_stop_is_safe_to_call_twice():
    server = MockToolServer(SCRIPT)
    server.start()
    server.stop()
    server.stop()  # must not raise


def test_url_raises_again_after_stop():
    server = MockToolServer(SCRIPT)
    server.start()
    server.stop()

    with pytest.raises(RuntimeError):
        _ = server.url
