"""Graph nodes for the Numonic pack.

Three nodes:

  * ``Extract Workflow Lineage`` — read a saved image's embedded ComfyUI
    metadata and recover its lineage locally (no network). Unchanged in intent;
    the opt-in "enhanced recovery" network path was removed in v0.3.0.
  * ``Save Image to Numonic`` — drop-in for the stock *Save Image*: encode the
    ``IMAGE`` tensor to PNG (workflow embedded) and ingest it into Numonic as a
    first-class asset, returning the gallery link.
  * ``Save Video to Numonic`` — drop-in for *Save Video*: take a ``VIDEO`` input,
    let ComfyUI's own ``save_to`` primitive encode it (workflow embedded),
    upload it, then delete the temp file.

The two save nodes read the API key from the **host** (env / config file) — never
from a widget (a widget value would serialize into saved workflows and output
files) — and run the shared three-phase upload core.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple

from . import credential
from . import image_encode
from . import lineage
from . import png_metadata
from . import upload_client
from . import video_save

try:  # ComfyUI runtime module; absent when unit-testing this file in isolation.
    import folder_paths  # type: ignore
except Exception:  # pragma: no cover - exercised only outside ComfyUI
    folder_paths = None

CATEGORY = "Numonic"


# ---------------------------------------------------------------------------
# Extract Workflow Lineage (local-only recovery)
# ---------------------------------------------------------------------------


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


def recover_from_file(path: str) -> dict:
    """Recover lineage from a file path. Local-first, no network.

    Pure enough to unit-test: give it a path to a PNG with ComfyUI metadata.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        result = lineage.empty_result("local")
        result["warnings"].append("Could not read image file: %s" % exc)
        return result
    return _local_recover(data)


def _local_recover(data: bytes) -> dict:
    try:
        chunks = png_metadata.extract_comfy_chunks(data)
    except png_metadata.NotAPngError:
        result = lineage.empty_result("local")
        result["warnings"].append(
            "Local recovery supports PNG metadata; this file is not a PNG."
        )
        return result
    return lineage.normalize_embedded_metadata(
        chunks.get("workflow"), chunks.get("prompt")
    )


class ExtractWorkflowLineage:
    """Recover the full ComfyUI lineage embedded in a saved image (local)."""

    CATEGORY = CATEGORY + "/Workflow Recovery"
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
        return {"required": {"image": image_widget}}

    def recover(self, image: str) -> Tuple[str, ...]:
        result = recover_from_file(_resolve_path(image))
        prompts = result.get("prompts", {})
        return (
            prompts.get("positive", ""),
            prompts.get("negative", ""),
            "\n".join(result.get("models", [])),
            "\n".join(result.get("loras", [])),
            "\n".join(result.get("custom_nodes", [])),
            json.dumps(result, indent=2, ensure_ascii=False),
        )


# ---------------------------------------------------------------------------
# Save Image to Numonic
# ---------------------------------------------------------------------------


def _raise_from_upload(exc: Exception) -> None:
    """Re-raise upload/credential failures as a clear graph error."""
    if isinstance(exc, credential.MissingCredentialError):
        raise RuntimeError(str(exc))
    if isinstance(exc, upload_client.UploadError):
        raise RuntimeError(str(exc))
    raise exc


class SaveImageToNumonic:
    """Ingest a generated IMAGE into Numonic as a first-class asset."""

    CATEGORY = CATEGORY
    FUNCTION = "save"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("gallery_url",)
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Save the generated image to your Numonic library (with ComfyUI "
        "lineage) and return its gallery link. Set NUMONIC_API_KEY on the host."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"images": ("IMAGE",)},
            "optional": {
                "filename_prefix": (
                    "STRING",
                    {"default": "numonic", "multiline": False},
                ),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    def save(
        self,
        images,
        filename_prefix: str = "numonic",
        prompt=None,
        extra_pnginfo=None,
    ) -> Dict[str, Any]:
        api_key = credential.require_api_key()
        urls = []
        try:
            for index, image in enumerate(images):
                png_bytes = image_encode.tensor_to_png_bytes(
                    image, prompt=prompt, extra_pnginfo=extra_pnginfo
                )
                filename = "%s_%05d.png" % (filename_prefix or "numonic", index)
                result = upload_client.upload_asset(
                    png_bytes,
                    filename=filename,
                    mime_type="image/png",
                    api_key=api_key,
                )
                urls.append(result["gallery_url"])
        except Exception as exc:  # map to a clean graph error
            _raise_from_upload(exc)

        text = "Saved to Numonic:\n" + "\n".join(urls) if urls else "No image saved."
        return {"ui": {"text": [text]}, "result": (urls[0] if urls else "",)}


# ---------------------------------------------------------------------------
# Save Video to Numonic
# ---------------------------------------------------------------------------


class SaveVideoToNumonic:
    """Ingest a generated VIDEO into Numonic as a first-class asset."""

    CATEGORY = CATEGORY
    FUNCTION = "save"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("gallery_url",)
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Save the generated video to your Numonic library (with ComfyUI "
        "lineage) and return its gallery link. Needs a recent ComfyUI with the "
        "native VIDEO type. Set NUMONIC_API_KEY on the host."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"video": ("VIDEO",)},
            "optional": {
                "filename_prefix": (
                    "STRING",
                    {"default": "numonic", "multiline": False},
                ),
                "format": (["auto", "mp4", "webm"], {"default": "auto"}),
                "codec": (["auto", "h264", "vp9"], {"default": "auto"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    def save(
        self,
        video,
        filename_prefix: str = "numonic",
        format: str = "auto",
        codec: str = "auto",
        prompt=None,
        extra_pnginfo=None,
    ) -> Dict[str, Any]:
        api_key = credential.require_api_key()

        try:
            tmp_path, mime_type = video_save.save_video_to_tmp(
                video,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
                fmt=format,
                codec=codec,
            )
        except video_save.VideoUnsupportedError as exc:
            raise RuntimeError(str(exc))

        try:
            with open(tmp_path, "rb") as handle:
                data = handle.read()
            ext = os.path.splitext(tmp_path)[1].lstrip(".") or "mp4"
            filename = "%s.%s" % (filename_prefix or "numonic", ext)
            try:
                result = upload_client.upload_asset(
                    data,
                    filename=filename,
                    mime_type=mime_type,
                    api_key=api_key,
                )
            except Exception as exc:
                _raise_from_upload(exc)
        finally:
            video_save._safe_unlink(tmp_path)  # delete the transient temp file

        text = "Saved to Numonic:\n" + result["gallery_url"]
        return {"ui": {"text": [text]}, "result": (result["gallery_url"],)}


NODE_CLASS_MAPPINGS = {
    "NumonicExtractWorkflowLineage": ExtractWorkflowLineage,
    "NumonicSaveImageToNumonic": SaveImageToNumonic,
    "NumonicSaveVideoToNumonic": SaveVideoToNumonic,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NumonicExtractWorkflowLineage": "Extract Workflow Lineage",
    "NumonicSaveImageToNumonic": "Save Image to Numonic",
    "NumonicSaveVideoToNumonic": "Save Video to Numonic",
}
