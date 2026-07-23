import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
import fixtures
from wr import image_encode, png_metadata


class MetadataMappingTests(unittest.TestCase):
    def test_mapping_mirrors_saveimage(self):
        prompt = fixtures.sample_prompt()
        extra = {"workflow": fixtures.sample_workflow()}
        mapping = image_encode.comfy_metadata_mapping(prompt, extra)
        # A `prompt` chunk plus a top-level `workflow` chunk (the extractor key).
        self.assertIn("prompt", mapping)
        self.assertIn("workflow", mapping)
        self.assertEqual(json.loads(mapping["prompt"])["3"]["class_type"], "KSampler")
        self.assertEqual(json.loads(mapping["workflow"])["last_node_id"], 12)

    def test_string_values_passed_through(self):
        mapping = image_encode.comfy_metadata_mapping(
            "already-json", {"workflow": "raw-string"}
        )
        self.assertEqual(mapping["prompt"], "already-json")
        self.assertEqual(mapping["workflow"], "raw-string")

    def test_empty_inputs_yield_empty_mapping(self):
        self.assertEqual(image_encode.comfy_metadata_mapping(None, None), {})


class EmbedRoundTripTests(unittest.TestCase):
    def _base_png(self) -> bytes:
        # A structurally valid PNG carrying NO ComfyUI chunks.
        return fixtures.make_png()

    def test_embed_then_local_reader_recovers_both_chunks(self):
        prompt = fixtures.sample_prompt()
        extra = {"workflow": fixtures.sample_workflow()}
        mapping = image_encode.comfy_metadata_mapping(prompt, extra)

        png = image_encode.embed_text_chunks(self._base_png(), mapping)

        # Round-trip through the pack's own PNG reader (what Numonic mirrors).
        chunks = png_metadata.extract_comfy_chunks(png)
        self.assertIn("workflow", chunks)
        self.assertIn("prompt", chunks)
        self.assertEqual(
            json.loads(chunks["prompt"])["4"]["inputs"]["ckpt_name"],
            "sd_xl_base_1.0.safetensors",
        )
        self.assertEqual(json.loads(chunks["workflow"])["last_node_id"], 12)

    def test_embedded_png_is_still_a_valid_png(self):
        png = image_encode.embed_text_chunks(
            self._base_png(), {"workflow": "{}", "prompt": "{}"}
        )
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IEND", png)

    def test_non_png_returned_unchanged(self):
        data = b"not a png"
        self.assertEqual(
            image_encode.embed_text_chunks(data, {"workflow": "{}"}), data
        )

    def test_empty_mapping_returned_unchanged(self):
        base = self._base_png()
        self.assertEqual(image_encode.embed_text_chunks(base, {}), base)


if __name__ == "__main__":
    unittest.main()
