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

    def test_confirm_timeout_defaults_to_120_and_never_below_http_timeout(self):
        os.environ.pop(config.ENV_CONFIRM_TIMEOUT, None)
        self.addCleanup(lambda: os.environ.pop(config.ENV_CONFIRM_TIMEOUT, None))
        self.assertEqual(config.confirm_timeout(), 120.0)
        # A user who raised the shared timeout above the default keeps it.
        os.environ[config.ENV_HTTP_TIMEOUT] = "300"
        self.assertEqual(config.confirm_timeout(), 300.0)

    def test_confirm_timeout_floor_applies_to_default_only(self):
        os.environ.pop(config.ENV_CONFIRM_TIMEOUT, None)
        self.addCleanup(lambda: os.environ.pop(config.ENV_CONFIRM_TIMEOUT, None))
        self.assertEqual(config.confirm_timeout(floor=300), 300.0)
        # An explicit env value wins even below the floor.
        os.environ[config.ENV_CONFIRM_TIMEOUT] = "1"
        self.assertEqual(config.confirm_timeout(floor=300), 1.0)

    def test_confirm_timeout_env_override_and_bad_values(self):
        self.addCleanup(lambda: os.environ.pop(config.ENV_CONFIRM_TIMEOUT, None))
        os.environ[config.ENV_CONFIRM_TIMEOUT] = "45"
        self.assertEqual(config.confirm_timeout(), 45.0)
        for bad in ("not-a-number", "-5", "0"):
            os.environ[config.ENV_CONFIRM_TIMEOUT] = bad
            self.assertEqual(config.confirm_timeout(), 120.0)

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
