import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
from wr import config


class ConfigTests(unittest.TestCase):
    def tearDown(self):
        for var in (config.ENV_SAVE_URL, config.ENV_CONNECT_URL,
                    config.ENV_HTTP_TIMEOUT):
            os.environ.pop(var, None)

    def test_defaults_are_public_urls(self):
        self.assertTrue(config.save_url().startswith("https://"))
        self.assertTrue(config.connect_url().startswith("https://"))

    def test_env_overrides(self):
        os.environ[config.ENV_SAVE_URL] = "http://127.0.0.1:9/x"
        self.assertEqual(config.save_url(), "http://127.0.0.1:9/x")

    def test_timeout_is_positive_float(self):
        os.environ[config.ENV_HTTP_TIMEOUT] = "not-a-number"
        self.assertEqual(config.http_timeout(), 20.0)
        os.environ[config.ENV_HTTP_TIMEOUT] = "-5"
        self.assertEqual(config.http_timeout(), 20.0)
        os.environ[config.ENV_HTTP_TIMEOUT] = "3.5"
        self.assertEqual(config.http_timeout(), 3.5)

    def test_client_settings_hold_no_secret(self):
        settings = config.client_settings()
        blob = repr(settings).lower()
        for banned in ("token", "secret", "password", "api_key", "bearer"):
            self.assertNotIn(banned, blob)
        self.assertIn("connectUrl", settings)

    def test_client_settings_have_no_enhanced_flag(self):
        # Enhanced recovery was removed in v0.3.0; the flag must be gone.
        self.assertNotIn("enhancedRecoveryAvailable", config.client_settings())


if __name__ == "__main__":
    unittest.main()
