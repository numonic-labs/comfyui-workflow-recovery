"""Shared lineage data shape (contract v0) and local normalization.

The ``LineageResult`` dict is the single response shape used by BOTH recovery
paths so the UI is identical regardless of source:

    {
      "source": "comfyui",
      "recovered": bool,
      "mode": "local" | "enhanced",
      "workflow_graph": {...} | None,     # raw UI graph, when present
      "prompts": {"positive": str, "negative": str, "raw"?: {...}},
      "models": [str, ...],
      "loras": [str, ...],
      "custom_nodes": [str, ...],
      "seed": int | None,
      "sampler": str | None,
      "warnings": [str, ...],
    }

This mirrors the hosted inspect endpoint's contract v0. The *local* path
(``normalize_embedded_metadata``) produces the same shape by parsing the
standard ComfyUI ``workflow`` and ``prompt`` chunks that ComfyUI embeds into
saved PNGs by default — non-proprietary, on-machine, no network. The hosted
endpoint provides an *enriched* version of the same shape (opt-in).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

SOURCE_COMFYUI = "comfyui"

# ``properties.cnr_id`` value ComfyUI stamps on its own built-in nodes.
CORE_PACK_ID = "comfy-core"

# Fallback list of ``class_type`` values that ship with core ComfyUI, used only
# when the image carries no UI workflow graph (or an old one without
# ``cnr_id``). When the graph IS present, ``core_types_from_workflow`` derives
# the real set from the image itself — see that function for why.
_CORE_NODE_TYPES = frozenset(
    {
        "KSampler",
        "KSamplerAdvanced",
        "CheckpointLoaderSimple",
        "CheckpointLoader",
        "CLIPTextEncode",
        "CLIPSetLastLayer",
        "VAEDecode",
        "VAEEncode",
        "VAELoader",
        "EmptyLatentImage",
        "LatentUpscale",
        "LatentUpscaleBy",
        "LoraLoader",
        "LoraLoaderModelOnly",
        "ControlNetLoader",
        "ControlNetApply",
        "ControlNetApplyAdvanced",
        "SaveImage",
        "PreviewImage",
        "LoadImage",
        "ImageScale",
        "ImageUpscaleWithModel",
        "UpscaleModelLoader",
        "ConditioningCombine",
        "ConditioningConcat",
        "ConditioningSetArea",
        "CLIPLoader",
        "DualCLIPLoader",
        "UNETLoader",
        "ModelSamplingDiscrete",
        "RepeatLatentBatch",
        "PrimitiveNode",
        "Note",
        "Reroute",
    }
)

# Heuristic mapping of a node ``class_type`` to the input key that carries a
# checkpoint / model file name.
_MODEL_INPUT_KEYS = ("ckpt_name", "unet_name", "model_name", "model")
_LORA_INPUT_KEYS = ("lora_name",)
# The seed lives on ``seed`` for classic samplers (``KSampler``), but on
# ``noise_seed`` for the modern Flux / custom-sampling pattern where a
# ``RandomNoise`` node feeds ``SamplerCustomAdvanced``. Read both so seeds are
# recovered on Flux workflows, not just classic ones.
_SEED_INPUT_KEYS = ("seed", "noise_seed")
_POSITIVE_HINTS = ("positive", "pos")
_NEGATIVE_HINTS = ("negative", "neg")


def empty_result(mode: str) -> Dict[str, Any]:
    return {
        "source": SOURCE_COMFYUI,
        "recovered": False,
        "mode": mode,
        "workflow_graph": None,
        "prompts": {"positive": "", "negative": ""},
        "models": [],
        "loras": [],
        "custom_nodes": [],
        "seed": None,
        "sampler": None,
        "warnings": [],
    }


def _loads(value: Any) -> Optional[Any]:
    """Best-effort JSON decode; accepts already-parsed objects."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", "replace")
        except Exception:  # pragma: no cover - defensive
            return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _unique(seq: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for item in seq:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _iter_prompt_nodes(prompt_obj: Any) -> List[Tuple[str, Dict[str, Any]]]:
    """Yield ``(node_id, node)`` pairs from a ComfyUI API-format prompt dict."""
    if not isinstance(prompt_obj, dict):
        return []
    nodes: List[Tuple[str, Dict[str, Any]]] = []
    for node_id, node in prompt_obj.items():
        if isinstance(node, dict) and "class_type" in node:
            nodes.append((str(node_id), node))
    return nodes


def _iter_workflow_nodes(workflow_obj: Any):
    """Yield every node dict in a UI workflow graph, including inside subgraphs."""
    if not isinstance(workflow_obj, dict):
        return
    for node in workflow_obj.get("nodes") or []:
        if isinstance(node, dict):
            yield node
    definitions = workflow_obj.get("definitions")
    if isinstance(definitions, dict):
        for subgraph in definitions.get("subgraphs") or []:
            if isinstance(subgraph, dict):
                for node in subgraph.get("nodes") or []:
                    if isinstance(node, dict):
                        yield node


def core_types_from_workflow(workflow_obj: Any) -> set:
    """Node ``type`` names the workflow itself attributes to core ComfyUI.

    ComfyUI stamps every node in the UI graph with ``properties.cnr_id`` — the
    registry id of the pack it came from, or ``"comfy-core"`` for a built-in.
    Trusting that beats guessing from a hand-maintained list, which goes stale
    every time ComfyUI ships new core nodes (the entire Flux / custom-sampling
    family post-dates the fallback list). Returns an empty set for graphs that
    predate ``cnr_id``, so callers fall back to the static list alone.

    Matching is by node ``type``, not node id: the API prompt namespaces ids
    inside subgraphs (``"98:25"``) while the UI graph does not, and types are
    stable across both.
    """
    core = set()
    for node in _iter_workflow_nodes(workflow_obj):
        node_type = node.get("type")
        properties = node.get("properties")
        if not isinstance(node_type, str) or not isinstance(properties, dict):
            continue
        if properties.get("cnr_id") == CORE_PACK_ID:
            core.add(node_type)
    return core


def _extract_from_prompt(
    prompt_obj: Any, result: Dict[str, Any], core_types: Any = None
) -> None:
    """Populate models/loras/custom_nodes/seed/sampler/prompts from API prompt.

    ``core_types`` supplements the fallback list with the set the image's own
    workflow graph declares as core (see ``core_types_from_workflow``).
    """
    nodes = _iter_prompt_nodes(prompt_obj)
    if not nodes:
        return
    known_core = _CORE_NODE_TYPES | set(core_types or ())

    models: List[str] = []
    loras: List[str] = []
    custom_nodes: List[str] = []
    positive_texts: List[str] = []
    negative_texts: List[str] = []
    ambiguous_texts: List[str] = []

    for _node_id, node in nodes:
        class_type = str(node.get("class_type", ""))
        if class_type and class_type not in known_core:
            custom_nodes.append(class_type)

        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue

        for key in _MODEL_INPUT_KEYS:
            val = inputs.get(key)
            if isinstance(val, str) and val:
                models.append(val)
        for key in _LORA_INPUT_KEYS:
            val = inputs.get(key)
            if isinstance(val, str) and val:
                loras.append(val)

        if result["seed"] is None:
            for key in _SEED_INPUT_KEYS:
                seed = inputs.get(key)
                if isinstance(seed, (int, float)) and not isinstance(seed, bool):
                    result["seed"] = int(seed)
                    break
        if result["sampler"] is None:
            sampler = inputs.get("sampler_name")
            if isinstance(sampler, str) and sampler:
                result["sampler"] = sampler

        if class_type == "CLIPTextEncode":
            text = inputs.get("text")
            if isinstance(text, str) and text.strip():
                bucket = _classify_text_role(node, text)
                if bucket == "positive":
                    positive_texts.append(text)
                elif bucket == "negative":
                    negative_texts.append(text)
                else:
                    ambiguous_texts.append(text)

    # If role could not be inferred from titles, fall back to order: first
    # ambiguous prompt is treated as positive, the rest as negative.
    if not positive_texts and ambiguous_texts:
        positive_texts.append(ambiguous_texts.pop(0))
    negative_texts.extend(ambiguous_texts)

    result["models"] = _unique(models)
    result["loras"] = _unique(loras)
    result["custom_nodes"] = _unique(custom_nodes)
    if positive_texts:
        result["prompts"]["positive"] = "\n".join(positive_texts).strip()
    if negative_texts:
        result["prompts"]["negative"] = "\n".join(negative_texts).strip()


def _classify_text_role(node: Dict[str, Any], _text: str) -> str:
    """Infer whether a CLIPTextEncode is the positive or negative prompt."""
    title = str(node.get("_meta", {}).get("title", "")).lower()
    for hint in _NEGATIVE_HINTS:
        if hint in title:
            return "negative"
    for hint in _POSITIVE_HINTS:
        if hint in title:
            return "positive"
    return "ambiguous"


def normalize_embedded_metadata(
    workflow_raw: Any,
    prompt_raw: Any,
    include_raw: bool = False,
) -> Dict[str, Any]:
    """Build a ``LineageResult`` locally from embedded PNG chunks (no network).

    ``workflow_raw`` is the ComfyUI UI-graph chunk; ``prompt_raw`` is the
    API-format execution chunk. Either may be a JSON string or a parsed object;
    either may be missing.
    """
    result = empty_result("local")
    workflow = _loads(workflow_raw)
    prompt = _loads(prompt_raw)

    if workflow is None and prompt is None:
        result["warnings"].append("No embedded ComfyUI metadata found in image.")
        return result

    if workflow is not None:
        result["workflow_graph"] = workflow
    if prompt is not None:
        _extract_from_prompt(prompt, result, core_types_from_workflow(workflow))

    # A graph with no API-prompt chunk still counts as a partial recovery.
    result["recovered"] = bool(
        result["workflow_graph"] is not None
        or result["models"]
        or result["prompts"]["positive"]
        or result["prompts"]["negative"]
    )
    if workflow is not None and prompt is None:
        result["warnings"].append(
            "Only the UI workflow chunk was present; prompt/model details are "
            "best-effort. Enhanced recovery can resolve them fully."
        )

    if include_raw:
        result["prompts"]["raw"] = prompt if isinstance(prompt, dict) else None

    return result


def coerce_contract(result: Any, mode: str) -> Dict[str, Any]:
    """Validate/coerce an arbitrary dict (e.g. hosted response) into the shape.

    Missing keys are filled with safe defaults so the UI can rely on the shape.
    """
    base = empty_result(mode)
    if not isinstance(result, dict):
        base["warnings"].append("Malformed response; expected an object.")
        return base

    base["source"] = str(result.get("source") or SOURCE_COMFYUI)
    base["recovered"] = bool(result.get("recovered", False))
    base["mode"] = mode
    base["workflow_graph"] = result.get("workflow_graph")

    prompts = result.get("prompts")
    if isinstance(prompts, dict):
        base["prompts"]["positive"] = str(prompts.get("positive") or "")
        base["prompts"]["negative"] = str(prompts.get("negative") or "")
        if "raw" in prompts:
            base["prompts"]["raw"] = prompts.get("raw")

    for key in ("models", "loras", "custom_nodes", "warnings"):
        val = result.get(key)
        if isinstance(val, list):
            base[key] = [str(x) for x in val if x is not None]

    seed = result.get("seed")
    if isinstance(seed, (int, float)) and not isinstance(seed, bool):
        base["seed"] = int(seed)
    sampler = result.get("sampler")
    if isinstance(sampler, str) and sampler:
        base["sampler"] = sampler

    return base
