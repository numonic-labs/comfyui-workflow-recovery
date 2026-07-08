"""Graph node: Extract Workflow Lineage.

A real ComfyUI graph node (so the pack is Registry-native and can anchor a
showcase template workflow). It reads the *raw file* the user selects — where
the embedded ComfyUI metadata is still intact — and recovers the workflow
lineage locally. Optionally, with an explicit opt-in toggle, it calls the hosted
enhanced-recovery endpoint.

Note on why this reads a file and not an ``IMAGE`` tensor: a decoded IMAGE
tensor has no embedded PNG metadata (it is stripped at decode time). Recovery
must operate on the original file bytes, exactly like core ``LoadImage`` does.
"""

from __future__ import annotations

import json
import os
from typing import Tuple

from . import inspect_client
from . import lineage
from . import png_metadata

try:  # ComfyUI runtime module; absent when unit-testing this file in isolation.
    import folder_paths  # type: ignore
except Exception:  # pragma: no cover - exercised only outside ComfyUI
    folder_paths = None


def _list_input_images():
    if folder_paths is None:
        return []
    try:
        input_dir = folder_paths.get_input_directory()
        return sorted(
            f
            for f in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, f))
            and f.lower().endswith((".png", ".webp", ".jpg", ".jpeg", ".flac"))
        )
    except Exception:  # pragma: no cover - defensive
        return []


def _resolve_path(image: str) -> str:
    if folder_paths is not None:
        try:
            return folder_paths.get_annotated_filepath(image)
        except Exception:  # pragma: no cover - defensive
            pass
    return image


def recover_from_file(path: str, enhanced: bool = False) -> dict:
    """Recover lineage from a file path. Local-first; enhanced is opt-in.

    Pure enough to unit-test: give it a path to a PNG with ComfyUI metadata.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        result = lineage.empty_result("local")
        result["warnings"].append("Could not read image file: %s" % exc)
        return result

    if enhanced:
        try:
            return inspect_client.fetch_enhanced_lineage(
                data, filename=os.path.basename(path)
            )
        except inspect_client.InspectError as exc:
            # Fall back to local recovery; never fail the graph on a network error.
            local = _local_recover(data)
            local["warnings"].append("Enhanced recovery unavailable: %s" % exc)
            return local

    return _local_recover(data)


def _local_recover(data: bytes) -> dict:
    try:
        chunks = png_metadata.extract_comfy_chunks(data)
    except png_metadata.NotAPngError:
        result = lineage.empty_result("local")
        result["warnings"].append(
            "Local recovery supports PNG metadata; this file is not a PNG. "
            "Use enhanced recovery for other formats."
        )
        return result
    return lineage.normalize_embedded_metadata(
        chunks.get("workflow"), chunks.get("prompt")
    )


class ExtractWorkflowLineage:
    """Recover the full ComfyUI lineage embedded in a saved image."""

    CATEGORY = "Numonic/Workflow Recovery"
    FUNCTION = "recover"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = (
        "positive_prompt",
        "negative_prompt",
        "models",
        "loras",
        "custom_nodes",
        "lineage_json",
    )
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        images = _list_input_images()
        if images:
            image_widget = (images, {"image_upload": True})
        else:  # allows the node to load even before any image is uploaded
            image_widget = ("STRING", {"default": "", "multiline": False})
        return {
            "required": {
                "image": image_widget,
            },
            "optional": {
                "enhanced_recovery": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "enhanced (sends image to Numonic)",
                        "label_off": "local only",
                    },
                ),
            },
        }

    def recover(self, image: str, enhanced_recovery: bool = False) -> Tuple[str, ...]:
        result = recover_from_file(_resolve_path(image), enhanced=enhanced_recovery)
        prompts = result.get("prompts", {})
        return (
            prompts.get("positive", ""),
            prompts.get("negative", ""),
            "\n".join(result.get("models", [])),
            "\n".join(result.get("loras", [])),
            "\n".join(result.get("custom_nodes", [])),
            json.dumps(result, indent=2, ensure_ascii=False),
        )


NODE_CLASS_MAPPINGS = {
    "NumonicExtractWorkflowLineage": ExtractWorkflowLineage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NumonicExtractWorkflowLineage": "Extract Workflow Lineage",
}
