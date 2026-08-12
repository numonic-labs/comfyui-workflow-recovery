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
        result = nodes.recover_from_file(path)
        self.assertTrue(result["recovered"])
        self.assertEqual(result["mode"], "local")
        self.assertEqual(result["models"], ["sd_xl_base_1.0.safetensors"])

    def test_recovers_seed_from_noise_seed_flux(self):
        # End-to-end file path for a modern Flux workflow: the seed lives on
        # RandomNoise.noise_seed, not KSampler.seed. Regression for the fix.
        path = self._write(fixtures.flux_png())
        result = nodes.recover_from_file(path)
        self.assertTrue(result["recovered"])
        self.assertEqual(result["seed"], 1027111520328378)
        self.assertEqual(result["sampler"], "euler")

    def test_core_nodes_not_reported_as_custom(self):
        # Same image, but carrying the UI graph: its cnr_id stamps prove which
        # nodes are built-ins, so only the third-party node is listed.
        path = self._write(fixtures.flux_png_with_workflow())
        result = nodes.recover_from_file(path)
        self.assertEqual(result["custom_nodes"], ["DetailDaemonSamplerNode"])
        self.assertEqual(result["seed"], 1027111520328378)

    def test_non_png_local_is_graceful(self):
        path = self._write(b"i am a jpeg, honest")
        result = nodes.recover_from_file(path)
        self.assertFalse(result["recovered"])
        self.assertTrue(any("PNG" in w for w in result["warnings"]))

    def test_missing_file_is_graceful(self):
        result = nodes.recover_from_file("/no/such/file.png")
        self.assertFalse(result["recovered"])
        self.assertTrue(result["warnings"])

    def test_node_class_returns_six_string_outputs(self):
        path = self._write(fixtures.comfy_png())
        node = nodes.ExtractWorkflowLineage()
        outputs = node.recover(path)
        self.assertEqual(len(outputs), 6)
        self.assertTrue(all(isinstance(o, str) for o in outputs))
        positive, negative, models, loras, custom, lineage_json = outputs
        self.assertEqual(positive, "a photograph of a cat")
        self.assertIn("sd_xl_base_1.0.safetensors", models)
        self.assertEqual(json.loads(lineage_json)["recovered"], True)

    def test_all_three_node_mappings_present(self):
        for key in (
            "NumonicExtractWorkflowLineage",
            "NumonicSaveImageToNumonic",
            "NumonicSaveVideoToNumonic",
        ):
            self.assertIn(key, nodes.NODE_CLASS_MAPPINGS)
            self.assertIn(key, nodes.NODE_DISPLAY_NAME_MAPPINGS)

    def test_save_nodes_are_output_nodes_with_gallery_output(self):
        for cls in (nodes.SaveImageToNumonic, nodes.SaveVideoToNumonic):
            self.assertTrue(cls.OUTPUT_NODE)
            self.assertEqual(cls.RETURN_NAMES, ("gallery_url",))
            # Hidden inputs carry prompt + workflow so lineage embeds.
            hidden = cls.INPUT_TYPES().get("hidden", {})
            self.assertIn("prompt", hidden)
            self.assertIn("extra_pnginfo", hidden)


if __name__ == "__main__":
    unittest.main()
