import json
import os
import sys
import tempfile
import unittest

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
        with open(os.path.join(cfg_dir, "config.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_key_from_env_wins(self):
        os.environ[credential.API_KEY_ENV] = "napi_env"
        self._write_config({"api_key": "napi_file"})
        self.assertEqual(credential.load_api_key(), "napi_env")

    def test_key_from_config_file(self):
        self._write_config({"api_key": "napi_file"})
        self.assertEqual(credential.load_api_key(), "napi_file")

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

    def test_gallery_url_shape(self):
        os.environ[credential.ENV_APP_URL] = "https://numonic.ai"
        self.assertEqual(
            credential.gallery_url("abc123"),
            "https://numonic.ai/app/assets/abc123",
        )


if __name__ == "__main__":
    unittest.main()
