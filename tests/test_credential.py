import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
from wr import credential

_ENV_VARS = (
    credential.API_KEY_ENV,
    credential.ENV_APP_URL,
    credential.ENV_API_URL,
)


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _ENV_VARS + ("HOME",)}
        # Point HOME at an empty temp dir so ~/.numonic/config.json is absent
        # unless a test writes one.
        self._home = tempfile.mkdtemp()
        os.environ["HOME"] = self._home
        for var in _ENV_VARS:
            os.environ.pop(var, None)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _write_config(self, payload):
        cfg_dir = os.path.join(self._home, ".numonic")
        os.makedirs(cfg_dir, exist_ok=True)
        path = os.path.join(cfg_dir, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        # Default creation mode is 0644, which trips the permission warning.
        # Write it private by default so only the tests that target the warning
        # loosen it; keeps unrelated tests silent.
        if os.name == "posix":
            os.chmod(path, 0o600)

    def test_key_from_env_wins(self):
        os.environ[credential.API_KEY_ENV] = "napi_env"
        self._write_config({"api_key": "napi_file"})
        self.assertEqual(credential.load_api_key(), "napi_env")

    def test_key_from_config_file(self):
        self._write_config({"api_key": "napi_file"})
        self.assertEqual(credential.load_api_key(), "napi_file")

    def test_key_from_config_file_written_with_a_utf8_bom(self):
        # PowerShell 5.1 (`Out-File -Encoding utf8`) and some Notepad versions
        # prepend a UTF-8 BOM. Reading such a file as plain utf-8 makes json
        # raise, which would look to the user like "no key configured".
        cfg_dir = os.path.join(self._home, ".numonic")
        os.makedirs(cfg_dir, exist_ok=True)
        path = os.path.join(cfg_dir, "config.json")
        with open(path, "wb") as fh:
            fh.write('{ "api_key": "napi_bom" }'.encode("utf-8-sig"))
        if os.name == "posix":
            os.chmod(path, 0o600)
        self.assertEqual(credential.load_api_key(), "napi_bom")

    def test_missing_key_returns_none(self):
        self.assertIsNone(credential.load_api_key())

    def test_require_api_key_raises_with_guidance(self):
        with self.assertRaises(credential.MissingCredentialError) as ctx:
            credential.require_api_key()
        # The message must tell the operator how to set the key.
        self.assertIn("NUMONIC_API_KEY", str(ctx.exception))

    def test_key_is_never_read_from_a_widget_arg(self):
        # Sanity: the loader takes NO argument — there is no widget path.
        import inspect

        sig = inspect.signature(credential.load_api_key)
        self.assertEqual(len(sig.parameters), 0)

    def test_app_url_default_and_override(self):
        self.assertEqual(credential.app_base_url(), "https://www.numonic.ai")
        os.environ[credential.ENV_APP_URL] = "http://localhost:3000/"
        self.assertEqual(credential.app_base_url(), "http://localhost:3000")

    def test_api_url_defaults_to_app_url(self):
        os.environ[credential.ENV_APP_URL] = "http://localhost:3000"
        self.assertEqual(credential.api_base_url(), "http://localhost:3000")
        os.environ[credential.ENV_API_URL] = "http://api.local:9000"
        self.assertEqual(credential.api_base_url(), "http://api.local:9000")

    def _capture_load(self):
        """Read the key, returning whatever was printed to stdout."""
        credential._permission_warned = False  # reset the once-per-process guard
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            credential.load_api_key()
        return buffer.getvalue()

    @unittest.skipUnless(os.name == "posix", "POSIX file modes only")
    def test_warns_when_config_is_readable_by_others(self):
        self._write_config({"api_key": "napi_file"})
        path = os.path.join(self._home, ".numonic", "config.json")
        os.chmod(path, 0o644)
        output = self._capture_load()
        self.assertIn("readable by other users", output)
        self.assertIn("chmod 600", output)

    @unittest.skipUnless(os.name == "posix", "POSIX file modes only")
    def test_no_warning_when_config_is_private(self):
        self._write_config({"api_key": "napi_file"})
        path = os.path.join(self._home, ".numonic", "config.json")
        os.chmod(path, 0o600)
        self.assertEqual(self._capture_load(), "")

    @unittest.skipUnless(os.name == "posix", "POSIX file modes only")
    def test_warning_is_emitted_only_once_per_process(self):
        self._write_config({"api_key": "napi_file"})
        os.chmod(os.path.join(self._home, ".numonic", "config.json"), 0o644)
        first = self._capture_load()
        # Second read must stay silent (the guard is not reset here).
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            credential.load_api_key()
        self.assertIn("readable by other users", first)
        self.assertEqual(buffer.getvalue(), "")

    def test_warning_never_fires_on_non_posix(self):
        # Windows secures files with ACLs; os.stat mode bits there would
        # false-positive, so the check must be skipped entirely.
        self._write_config({"api_key": "napi_file"})
        path = os.path.join(self._home, ".numonic", "config.json")
        if os.name == "posix":
            os.chmod(path, 0o644)
        credential._permission_warned = False
        buffer = io.StringIO()
        with mock.patch.object(credential.os, "name", "nt"):
            with contextlib.redirect_stdout(buffer):
                credential.load_api_key()
        self.assertEqual(buffer.getvalue(), "")

    def test_gallery_url_shape(self):
        os.environ[credential.ENV_APP_URL] = "https://numonic.ai"
        self.assertEqual(
            credential.gallery_url("abc123"),
            "https://numonic.ai/app/assets/abc123",
        )


if __name__ == "__main__":
    unittest.main()
