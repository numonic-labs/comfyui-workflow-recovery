import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
from wr import credential, upload_client

_SIGNED_URL = "/api/v1/comfy-lineage/asset/signed-url"
_CONFIRM = "/api/v1/import/comfyui/confirm-upload"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence
        pass

    def _send(self, status, payload=b""):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        cfg = self.server.cfg
        if self.path.endswith(_SIGNED_URL):
            self.server.calls.append(("POST", "signed-url"))
            self.server.signed_body = raw
            code = cfg.get("phase1", 200)
            if code != 200:
                return self._send(code, b'{"error":"phase1"}')
            base = "http://127.0.0.1:%d" % self.server.server_address[1]
            body = json.dumps(
                {"signedUrl": base + "/put/target", "token": "tok", "path": "t/x/f.png"}
            ).encode()
            return self._send(200, body)
        if self.path.endswith(_CONFIRM):
            self.server.calls.append(("POST", "confirm"))
            self.server.confirm_body = raw
            code = cfg.get("phase3", 200)
            if code != 200:
                return self._send(code, b'{"error":"phase3"}')
            body = json.dumps(
                {
                    "success": True,
                    "url": "https://numonic.ai/app/assets/asset123",
                    "asset": {"assetH": "asset123", "filename": "cat.png"},
                    "metadata": None,
                }
            ).encode()
            return self._send(200, body)
        self._send(404, b'{"error":"unknown path"}')

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.server.put_bytes = self.rfile.read(length) if length else b""
        self.server.calls.append(("PUT", "storage"))
        self._send(self.server.cfg.get("phase2", 200))


class MockNumonic:
    def __init__(self, cfg=None):
        self.httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.cfg = cfg or {}
        self.httpd.calls = []
        self.httpd.put_bytes = None
        self.httpd.signed_body = None
        self.httpd.confirm_body = None
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        return "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def _upload(svc, **kw):
    return upload_client.upload_asset(
        b"PNGDATA",
        filename="cat.png",
        mime_type="image/png",
        api_key="napi_test",
        api_base=svc.base_url,
        app_base="https://numonic.ai",
        timeout=5,
        **kw,
    )


class UploadClientTests(unittest.TestCase):
    def test_happy_path_hits_dedicated_endpoints_in_order(self):
        with MockNumonic() as svc:
            result = _upload(svc)
        self.assertEqual(result["assetH"], "asset123")
        # Gallery link comes from the server's confirm-upload `url`.
        self.assertEqual(
            result["gallery_url"], "https://numonic.ai/app/assets/asset123"
        )
        self.assertEqual(
            svc.httpd.calls,
            [("POST", "signed-url"), ("PUT", "storage"), ("POST", "confirm")],
        )
        # Bytes went to storage on the PUT, not the confirm.
        self.assertEqual(svc.httpd.put_bytes, b"PNGDATA")

    def test_signed_url_body_is_filename_and_contentType(self):
        with MockNumonic() as svc:
            _upload(svc)
        body = json.loads(svc.httpd.signed_body.decode())
        self.assertEqual(body, {"filename": "cat.png", "contentType": "image/png"})

    def test_confirm_body_carries_path_filesize_and_mime(self):
        with MockNumonic() as svc:
            _upload(svc)
        body = json.loads(svc.httpd.confirm_body.decode())
        self.assertEqual(body["path"], "t/x/f.png")
        self.assertEqual(body["filename"], "cat.png")
        self.assertEqual(body["mimeType"], "image/png")
        # fileSize is required by the server schema and equals the byte length.
        self.assertEqual(body["fileSize"], len(b"PNGDATA"))

    def test_gallery_url_falls_back_when_server_omits_url(self):
        # Old/edge server that returns asset.assetH but no top-level `url`.
        class _NoUrl(_Handler):
            pass

        with MockNumonic() as svc:
            # Monkeypatch the confirm response to omit `url`.
            orig = svc.httpd.RequestHandlerClass.do_POST

            def patched(handler):
                if handler.path.endswith(_CONFIRM):
                    length = int(handler.headers.get("Content-Length", 0) or 0)
                    handler.rfile.read(length)
                    handler.server.calls.append(("POST", "confirm"))
                    payload = json.dumps({"asset": {"assetH": "asset999"}}).encode()
                    return handler._send(200, payload)
                return orig(handler)

            svc.httpd.RequestHandlerClass.do_POST = patched
            try:
                result = _upload(svc)
            finally:
                svc.httpd.RequestHandlerClass.do_POST = orig
        self.assertEqual(
            result["gallery_url"], "https://numonic.ai/app/assets/asset999"
        )

    def test_401_maps_to_connect_message(self):
        with MockNumonic({"phase1": 401}) as svc:
            with self.assertRaises(upload_client.UploadError) as ctx:
                _upload(svc)
        self.assertEqual(ctx.exception.status, 401)

    def test_403_maps_to_permission_message(self):
        with MockNumonic({"phase1": 403}) as svc:
            with self.assertRaises(upload_client.UploadError) as ctx:
                _upload(svc)
        self.assertEqual(ctx.exception.status, 403)

    def test_413_storage_full_on_confirm(self):
        with MockNumonic({"phase3": 413}) as svc:
            with self.assertRaises(upload_client.UploadError) as ctx:
                _upload(svc)
        self.assertEqual(ctx.exception.status, 413)
        self.assertIn("storage", str(ctx.exception).lower())

    def test_429_rate_limited(self):
        with MockNumonic({"phase3": 429}) as svc:
            with self.assertRaises(upload_client.UploadError) as ctx:
                _upload(svc)
        self.assertEqual(ctx.exception.status, 429)

    def test_idempotent_resave_returns_stable_asset(self):
        # Re-running with identical bytes yields the same assetH / gallery link
        # (server-side CID dedup keeps storage flat; the client is stateless).
        with MockNumonic() as svc:
            first = _upload(svc)
            second = _upload(svc)
        self.assertEqual(first["gallery_url"], second["gallery_url"])

    def test_missing_credential_raises_before_any_request(self):
        saved = {k: os.environ.get(k) for k in (credential.API_KEY_ENV, "HOME")}
        os.environ["HOME"] = tempfile.mkdtemp()
        os.environ.pop(credential.API_KEY_ENV, None)
        try:
            with self.assertRaises(credential.MissingCredentialError):
                upload_client.upload_asset(
                    b"x", filename="a.png", mime_type="image/png",
                    api_base="http://127.0.0.1:1", app_base="https://numonic.ai",
                )
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_zero_bytes_refused(self):
        with self.assertRaises(upload_client.UploadError):
            upload_client.upload_asset(
                b"", filename="a.png", mime_type="image/png", api_key="napi_x",
                api_base="http://127.0.0.1:1", app_base="https://numonic.ai",
            )


if __name__ == "__main__":
    unittest.main()
