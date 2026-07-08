import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
import fixtures
from wr import nodes


class NodeRecoveryTests(unittest.TestCase):
    def _write(self, data: bytes) -> str:
        fd, path = tempfile.mkstemp(suffix=".png")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_local_recovery_from_file(self):
        path = self._write(fixtures.comfy_png())
        result = nodes.recover_from_file(path, enhanced=False)
        self.assertTrue(result["recovered"])
        self.assertEqual(result["mode"], "local")
        self.assertEqual(result["models"], ["sd_xl_base_1.0.safetensors"])

    def test_non_png_local_is_graceful(self):
        path = self._write(b"i am a jpeg, honest")
        result = nodes.recover_from_file(path, enhanced=False)
        self.assertFalse(result["recovered"])
        self.assertTrue(any("PNG" in w for w in result["warnings"]))

    def test_missing_file_is_graceful(self):
        result = nodes.recover_from_file("/no/such/file.png", enhanced=False)
        self.assertFalse(result["recovered"])
        self.assertTrue(result["warnings"])

    def test_enhanced_falls_back_to_local_when_endpoint_down(self):
        path = self._write(fixtures.comfy_png())
        # Point the enhanced endpoint at a dead port via env override.
        os.environ["WORKFLOW_RECOVERY_INSPECT_URL"] = "http://127.0.0.1:1/x"
        os.environ["WORKFLOW_RECOVERY_HTTP_TIMEOUT"] = "1"
        try:
            result = nodes.recover_from_file(path, enhanced=True)
        finally:
            os.environ.pop("WORKFLOW_RECOVERY_INSPECT_URL", None)
            os.environ.pop("WORKFLOW_RECOVERY_HTTP_TIMEOUT", None)
        # Falls back to local recovery rather than failing the graph.
        self.assertTrue(result["recovered"])
        self.assertEqual(result["mode"], "local")
        self.assertTrue(any("Enhanced recovery unavailable" in w for w in result["warnings"]))

    def test_node_class_returns_six_string_outputs(self):
        path = self._write(fixtures.comfy_png())
        node = nodes.ExtractWorkflowLineage()
        outputs = node.recover(path, enhanced_recovery=False)
        self.assertEqual(len(outputs), 6)
        self.assertTrue(all(isinstance(o, str) for o in outputs))
        positive, negative, models, loras, custom, lineage_json = outputs
        self.assertEqual(positive, "a photograph of a cat")
        self.assertIn("sd_xl_base_1.0.safetensors", models)
        self.assertEqual(json.loads(lineage_json)["recovered"], True)

    def test_node_mappings_present(self):
        self.assertIn("NumonicExtractWorkflowLineage", nodes.NODE_CLASS_MAPPINGS)
        self.assertIn("NumonicExtractWorkflowLineage", nodes.NODE_DISPLAY_NAME_MAPPINGS)


if __name__ == "__main__":
    unittest.main()
