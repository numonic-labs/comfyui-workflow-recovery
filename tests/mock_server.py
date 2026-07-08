"""A tiny stdlib HTTP server for exercising the inspect/save clients."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    # Behaviour is injected via the server instance (see MockService).
    def log_message(self, *args):  # silence test output
        pass

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        self.server.last_path = self.path
        self.server.last_headers = dict(self.headers)
        self.server.last_body = raw
        handler = self.server.responder
        status, payload = handler(self.path, dict(self.headers), raw)
        self._send(status, payload)


class MockService:
    """Context-manager HTTP server. ``responder(path, headers, body)`` -> (status, dict)."""

    def __init__(self, responder):
        self.responder = responder
        self.httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.responder = responder
        self.httpd.last_path = None
        self.httpd.last_headers = None
        self.httpd.last_body = None
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address
        return "http://%s:%d" % (host, port)

    @property
    def last_body(self):
        return self.httpd.last_body

    @property
    def last_headers(self):
        return self.httpd.last_headers

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
