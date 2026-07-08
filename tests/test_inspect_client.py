import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
import fixtures
from mock_server import MockService
from wr import inspect_client


def _enhanced_payload():
    return {
        "source": "comfyui",
        "recovered": True,
        "workflow_graph": {"nodes": []},
        "prompts": {"positive": "cat", "negative": "dog"},
        "models": ["model.safetensors"],
        "loras": ["lora.safetensors"],
        "custom_nodes": ["FancyNode"],
        "seed": 99,
        "sampler": "euler_a",
        "warnings": [],
    }


class InspectClientTests(unittest.TestCase):
    def test_happy_path_normalizes_to_enhanced_mode(self):
        def responder(path, headers, body):
            return 200, _enhanced_payload()

        with MockService(responder) as svc:
            result = inspect_client.fetch_enhanced_lineage(
                fixtures.comfy_png(), url=svc.base_url + "/inspect"
            )
        self.assertEqual(result["mode"], "enhanced")
        self.assertTrue(result["recovered"])
        self.assertEqual(result["models"], ["model.safetensors"])
        self.assertEqual(result["seed"], 99)

    def test_sends_multipart_with_image(self):
        captured = {}

        def responder(path, headers, body):
            captured["ct"] = headers.get("Content-Type", "")
            captured["len"] = len(body)
            return 200, _enhanced_payload()

        with MockService(responder) as svc:
            inspect_client.fetch_enhanced_lineage(
                fixtures.comfy_png(), url=svc.base_url + "/inspect"
            )
        self.assertIn("multipart/form-data", captured["ct"])
        self.assertGreater(captured["len"], 100)

    def test_422_raises_no_metadata(self):
        def responder(path, headers, body):
            return 422, {"error": "no metadata"}

        with MockService(responder) as svc:
            with self.assertRaises(inspect_client.InspectError) as ctx:
                inspect_client.fetch_enhanced_lineage(
                    fixtures.plain_png(), url=svc.base_url + "/inspect"
                )
        self.assertEqual(ctx.exception.status, 422)

    def test_415_raises_unsupported(self):
        def responder(path, headers, body):
            return 415, {"error": "bad media"}

        with MockService(responder) as svc:
            with self.assertRaises(inspect_client.InspectError) as ctx:
                inspect_client.fetch_enhanced_lineage(
                    b"xxxx", url=svc.base_url + "/inspect"
                )
        self.assertEqual(ctx.exception.status, 415)

    def test_unreachable_raises(self):
        # Nothing listening on this port.
        with self.assertRaises(inspect_client.InspectError):
            inspect_client.fetch_enhanced_lineage(
                fixtures.comfy_png(),
                url="http://127.0.0.1:1/inspect",
                timeout=1,
            )

    def test_recovered_false_with_warnings_is_returned(self):
        # A 200 that reports no recovery must pass through cleanly (not raise).
        def responder(path, headers, body):
            return 200, {"source": "comfyui", "recovered": False,
                         "warnings": ["nothing embedded"]}

        with MockService(responder) as svc:
            result = inspect_client.fetch_enhanced_lineage(
                fixtures.plain_png(), url=svc.base_url + "/inspect"
            )
        self.assertFalse(result["recovered"])
        self.assertEqual(result["warnings"], ["nothing embedded"])


if __name__ == "__main__":
    unittest.main()
