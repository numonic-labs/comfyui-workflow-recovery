import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
import fixtures
from wr import lineage


class LocalNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.workflow = json.dumps(fixtures.sample_workflow())
        self.prompt = json.dumps(fixtures.sample_prompt())

    def test_full_recovery_from_both_chunks(self):
        result = lineage.normalize_embedded_metadata(self.workflow, self.prompt)
        self.assertTrue(result["recovered"])
        self.assertEqual(result["mode"], "local")
        self.assertEqual(result["models"], ["sd_xl_base_1.0.safetensors"])
        self.assertEqual(result["loras"], ["add_detail.safetensors"])
        self.assertEqual(result["custom_nodes"], ["RIFE VFI"])
        self.assertEqual(result["prompts"]["positive"], "a photograph of a cat")
        self.assertEqual(result["prompts"]["negative"], "blurry, low quality")
        self.assertEqual(result["seed"], 42)
        self.assertEqual(result["sampler"], "euler")

    def test_model_link_lists_are_not_treated_as_model_names(self):
        # KSampler.inputs.model is a link ["10", 0], not a string; must be ignored.
        result = lineage.normalize_embedded_metadata(self.workflow, self.prompt)
        self.assertNotIn("10", result["models"])
        self.assertEqual(result["models"], ["sd_xl_base_1.0.safetensors"])

    def test_ambiguous_prompt_role_falls_back_to_order(self):
        prompt = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "first"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "second"}},
        }
        result = lineage.normalize_embedded_metadata(None, json.dumps(prompt))
        self.assertEqual(result["prompts"]["positive"], "first")
        self.assertEqual(result["prompts"]["negative"], "second")

    def test_workflow_only_is_partial_recovery(self):
        result = lineage.normalize_embedded_metadata(self.workflow, None)
        self.assertTrue(result["recovered"])
        self.assertTrue(any("best-effort" in w for w in result["warnings"]))

    def test_no_metadata_is_not_recovered(self):
        result = lineage.normalize_embedded_metadata(None, None)
        self.assertFalse(result["recovered"])
        self.assertTrue(result["warnings"])

    def test_include_raw_attaches_prompt(self):
        result = lineage.normalize_embedded_metadata(
            self.workflow, self.prompt, include_raw=True
        )
        self.assertIn("raw", result["prompts"])
        self.assertIsInstance(result["prompts"]["raw"], dict)

    def test_accepts_already_parsed_objects(self):
        result = lineage.normalize_embedded_metadata(
            fixtures.sample_workflow(), fixtures.sample_prompt()
        )
        self.assertTrue(result["recovered"])


class CoerceContractTests(unittest.TestCase):
    def test_fills_missing_keys(self):
        result = lineage.coerce_contract({"recovered": True}, mode="enhanced")
        self.assertEqual(result["mode"], "enhanced")
        self.assertEqual(result["models"], [])
        self.assertEqual(result["prompts"], {"positive": "", "negative": ""})

    def test_coerces_types(self):
        raw = {
            "recovered": 1,
            "models": ["a", None, "b"],
            "prompts": {"positive": "p", "negative": "n"},
            "seed": 7.0,
            "sampler": "dpmpp_2m",
        }
        result = lineage.coerce_contract(raw, mode="enhanced")
        self.assertTrue(result["recovered"])
        self.assertEqual(result["models"], ["a", "b"])
        self.assertEqual(result["seed"], 7)
        self.assertEqual(result["sampler"], "dpmpp_2m")

    def test_malformed_response_is_safe(self):
        result = lineage.coerce_contract("nonsense", mode="enhanced")
        self.assertFalse(result["recovered"])
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
