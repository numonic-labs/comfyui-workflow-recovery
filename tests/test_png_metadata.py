import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401  registers 'wr'
import fixtures
from wr import png_metadata


class PngMetadataTests(unittest.TestCase):
    def test_reads_uncompressed_text_chunks(self):
        data = fixtures.comfy_png()
        chunks = png_metadata.extract_comfy_chunks(data)
        self.assertIn("workflow", chunks)
        self.assertIn("prompt", chunks)
        prompt = json.loads(chunks["prompt"])
        self.assertEqual(prompt["3"]["class_type"], "KSampler")

    def test_reads_compressed_ztxt_chunks(self):
        # Guards against the exifreader zTXt/compressed-iTXt drop (memory note).
        data = fixtures.comfy_png_compressed()
        chunks = png_metadata.extract_comfy_chunks(data)
        self.assertIn("workflow", chunks)
        self.assertIn("prompt", chunks)
        self.assertEqual(json.loads(chunks["prompt"])["4"]["inputs"]["ckpt_name"],
                         "sd_xl_base_1.0.safetensors")

    def test_reads_itxt_chunks(self):
        data = fixtures.make_png(itext_chunks={"prompt": '{"1": {"class_type": "KSampler"}}'})
        chunks = png_metadata.extract_comfy_chunks(data)
        self.assertIn("prompt", chunks)

    def test_plain_png_has_no_comfy_chunks(self):
        chunks = png_metadata.extract_comfy_chunks(fixtures.plain_png())
        self.assertEqual(chunks, {})

    def test_all_text_chunks_includes_non_comfy(self):
        chunks = png_metadata.all_text_chunks(fixtures.plain_png())
        self.assertIn("Software", chunks)

    def test_non_png_raises(self):
        with self.assertRaises(png_metadata.NotAPngError):
            png_metadata.extract_comfy_chunks(b"not a png at all")

    def test_truncated_chunk_does_not_crash(self):
        data = fixtures.comfy_png()[:-40]  # chop the tail
        # Should not raise; returns whatever was parseable.
        png_metadata.extract_comfy_chunks(data)


if __name__ == "__main__":
    unittest.main()
