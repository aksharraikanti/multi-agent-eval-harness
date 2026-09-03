"""A tiny local HTTP server with deterministic, pre-scripted responses —
a stand-in for one fake external API (Jira, GitHub, whatever), so a
scenario can exercise a real HTTP call without needing network access or
a live third-party account.

Same idea as CannedAgent, one layer down: a lookup table from request to
canned response, instead of from agent input to canned AgentResult.
Standard library only (http.server) — no reason to add a dependency for
something this small.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# (method, path) -> (status_code, json_body)
Script = dict[tuple[str, str], tuple[int, dict]]


class MockToolServer:
    """script maps (method, path) -> (status_code, json_body). A request
    for an unscripted (method, path) gets a 404 with a JSON error body —
    the HTTP equivalent of CannedAgent's KeyError for an unscripted
    input.

    Use as a context manager (`with MockToolServer(script) as server:`)
    or call start()/stop() directly. `.url` is the base URL once started.
    """

    def __init__(self, script: Script):
        self._script = script
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self, host: str = "127.0.0.1", port: int = 0) -> None:
        script = self._script

        class Handler(BaseHTTPRequestHandler):
            def _respond(self, method: str) -> None:
                key = (method, self.path)
                if key not in script:
                    status, body = 404, {"error": f"no scripted response for {method} {self.path}"}
                else:
                    status, body = script[key]

                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:
                self._respond("GET")

            def do_POST(self) -> None:
                self._respond("POST")

            def log_message(self, format: str, *args) -> None:
                pass  # silence default request logging to stderr

        self._server = HTTPServer((host, port), Handler)
        # serve_forever's default poll_interval is 0.5s, which means
        # stop() would block up to half a second waiting for the loop to
        # notice shutdown() was called. A tighter interval keeps
        # start/stop cheap enough to use freely across many tests.
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        self._thread.start()

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("MockToolServer is not started")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> "MockToolServer":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()
