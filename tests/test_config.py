import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
from wr import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop(config.ENV_HTTP_TIMEOUT, None)
        self.addCleanup(lambda: os.environ.pop(config.ENV_HTTP_TIMEOUT, None))

    def test_timeout_is_positive_float(self):
        self.assertEqual(config.http_timeout(), 20.0)
        os.environ[config.ENV_HTTP_TIMEOUT] = "not-a-number"
        self.assertEqual(config.http_timeout(), 20.0)
        os.environ[config.ENV_HTTP_TIMEOUT] = "-5"
        self.assertEqual(config.http_timeout(), 20.0)
        os.environ[config.ENV_HTTP_TIMEOUT] = "3.5"
        self.assertEqual(config.http_timeout(), 3.5)

    def test_module_exposes_no_secret(self):
        # Guard the "no secret in the package" constraint.
        for name in dir(config):
            if name.startswith("_"):
                continue
            value = getattr(config, name)
            if isinstance(value, str):
                lowered = value.lower()
                self.assertNotIn("napi_", lowered)
                self.assertNotIn("bearer ", lowered)


if __name__ == "__main__":
    unittest.main()
