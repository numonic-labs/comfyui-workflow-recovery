import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
import fixtures
from mock_server import MockService
from wr import lineage, save_client


def _result():
    return lineage.normalize_embedded_metadata(
        fixtures.sample_workflow(), fixtures.sample_prompt()
    )


class SaveClientTests(unittest.TestCase):
    def test_missing_token_raises_and_sends_nothing(self):
        called = {"n": 0}

        def responder(path, headers, body):
            called["n"] += 1
            return 200, {"ok": True}

        with MockService(responder) as svc:
            with self.assertRaises(save_client.MissingTokenError):
                save_client.save_lineage(
                    _result(), user_token="", url=svc.base_url + "/save"
                )
        self.assertEqual(called["n"], 0, "no request should be sent without a token")

    def test_happy_path_relays_user_token(self):
        captured = {}

        def responder(path, headers, body):
            captured["auth"] = headers.get("Authorization", "")
            captured["body"] = json.loads(body.decode("utf-8"))
            return 200, {"ok": True, "url": "https://app.numonic.ai/x"}

        with MockService(responder) as svc:
            result = save_client.save_lineage(
                _result(),
                user_token="user-abc-123",
                source_filename="cat.png",
                url=svc.base_url + "/save",
            )
        self.assertEqual(captured["auth"], "Bearer user-abc-123")
        self.assertTrue(result.get("ok"))
        self.assertEqual(captured["body"]["source_filename"], "cat.png")

    def test_never_sends_raw_image_bytes(self):
        captured = {}

        def responder(path, headers, body):
            captured["body"] = json.loads(body.decode("utf-8"))
            return 200, {"ok": True}

        with MockService(responder) as svc:
            save_client.save_lineage(
                _result(), user_token="t", url=svc.base_url + "/save"
            )
        # Only lineage + metadata are sent, never image bytes.
        self.assertEqual(set(captured["body"].keys()), {"source", "source_filename", "lineage"})
        self.assertNotIn("image", captured["body"])

    def test_401_raises_save_error(self):
        def responder(path, headers, body):
            return 401, {"error": "bad token"}

        with MockService(responder) as svc:
            with self.assertRaises(save_client.SaveError) as ctx:
                save_client.save_lineage(
                    _result(), user_token="bad", url=svc.base_url + "/save"
                )
        self.assertEqual(ctx.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
