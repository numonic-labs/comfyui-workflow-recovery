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


class FluxNoiseSeedTests(unittest.TestCase):
    """Regression: recover the seed from ``RandomNoise.noise_seed`` (Flux /
    custom-sampling), not only ``KSampler.seed``. Guards the gap confirmed on a
    real Flux 2 dev image (seed 1027111520328378 was dropped before the fix)."""

    def test_seed_recovered_from_noise_seed(self):
        result = lineage.normalize_embedded_metadata(None, json.dumps(fixtures.flux_prompt()))
        self.assertTrue(result["recovered"])
        self.assertEqual(result["seed"], 1027111520328378)
        self.assertEqual(result["sampler"], "euler")
        self.assertEqual(result["models"], ["flux2_dev_fp8mixed.safetensors"])
        self.assertEqual(result["loras"], ["Flux_2-Turbo-LoRA_comfyui.safetensors"])

    def test_classic_seed_preferred_over_noise_seed_within_a_node(self):
        prompt = {"1": {"class_type": "KSampler", "inputs": {"seed": 5, "noise_seed": 9}}}
        result = lineage.normalize_embedded_metadata(None, json.dumps(prompt))
        self.assertEqual(result["seed"], 5)

    def test_linked_noise_seed_is_ignored_not_crashing(self):
        # A noise_seed wired from another node is a link list, not an int; it must
        # be skipped (link resolution is a separate, larger enhancement), no crash.
        prompt = {"1": {"class_type": "RandomNoise", "inputs": {"noise_seed": ["9", 0]}}}
        result = lineage.normalize_embedded_metadata(None, json.dumps(prompt))
        self.assertIsNone(result["seed"])


class CoreNodeClassificationTests(unittest.TestCase):
    """Custom-node detection must trust the graph's own ``cnr_id`` stamps.

    The static fallback list predates the Flux / custom-sampling era, so without
    this every built-in in a modern template (RandomNoise, KSamplerSelect,
    SamplerCustomAdvanced, FluxGuidance...) was reported as a *custom* node.
    """

    def test_workflow_cnr_id_suppresses_core_nodes(self):
        result = lineage.normalize_embedded_metadata(
            json.dumps(fixtures.flux_workflow()), json.dumps(fixtures.flux_prompt())
        )
        # Only the genuine third-party node survives.
        self.assertEqual(result["custom_nodes"], ["DetailDaemonSamplerNode"])

    def test_without_workflow_falls_back_to_static_list(self):
        # No UI graph => no cnr_id evidence => conservative static list only, so
        # the modern core nodes are (still) reported. Documents the fallback.
        result = lineage.normalize_embedded_metadata(
            None, json.dumps(fixtures.flux_prompt())
        )
        for node_type in ("RandomNoise", "KSamplerSelect", "DetailDaemonSamplerNode"):
            self.assertIn(node_type, result["custom_nodes"])

    def test_core_types_walks_subgraph_definitions(self):
        core = lineage.core_types_from_workflow(fixtures.flux_workflow())
        # Top-level and subgraph-nested built-ins alike.
        self.assertIn("UNETLoader", core)
        self.assertIn("RandomNoise", core)
        self.assertIn("SamplerCustomAdvanced", core)
        # A third-party cnr_id is never treated as core.
        self.assertNotIn("DetailDaemonSamplerNode", core)

    def test_graph_without_cnr_id_yields_empty_set(self):
        legacy = {"nodes": [{"id": 1, "type": "KSampler", "properties": {}}]}
        self.assertEqual(lineage.core_types_from_workflow(legacy), set())

    def test_malformed_workflow_is_safe(self):
        for bad in (None, "nonsense", 42, {"nodes": "not-a-list"}, {"definitions": 5}):
            self.assertEqual(lineage.core_types_from_workflow(bad), set())


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
