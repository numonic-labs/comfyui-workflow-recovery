"""Encode a ComfyUI ``VIDEO`` to a temp file via its own ``save_to`` primitive.

We reuse the *same* primitive the native ``SaveVideo`` node calls internally
(``VIDEO.save_to`` — PyAV, workflow embedded) rather than driving the (V3
typed-IO) ``SaveVideo`` node.

The lineage-critical part is ``build_video_metadata`` — it mirrors native
``SaveVideo`` **exactly** (``metadata.update(extra_pnginfo)`` then
``metadata["prompt"] = prompt``). ``save_to`` writes each *top-level* key of that
dict as a container tag, so this produces top-level ``workflow`` + ``prompt``
tags — the keys Numonic's server-side video metadata extractor scans for.
Passing a nested ``{"extra_pnginfo": {...}}`` instead would bury ``workflow`` and
break extraction, so the shape here is deliberate and covered by a round-trip test.

Guards:
  * ``save_to`` is defined per concrete VIDEO type, not on the base
    ``VideoInput`` — ``hasattr`` check, fail loudly if absent.
  * the native ``VIDEO`` API is recent; on older ComfyUI the video node's input
    socket won't even resolve. The loud message tells the user to update.
"""

from __future__ import annotations

import importlib
import os
import tempfile
from typing import Any, Dict, Optional, Tuple

VIDEO_FLOOR_MESSAGE = (
    "This ComfyUI build's VIDEO object has no native save_to() primitive. "
    "Native video save needs a recent ComfyUI (the typed VIDEO API). Update "
    "ComfyUI, or use 'Save Image to Numonic' for image outputs."
)

# format widget value -> temp-file extension.
_EXT_BY_FORMAT = {"auto": "mp4", "mp4": "mp4", "webm": "webm", "mov": "mov"}
# extension -> MIME type accepted by Numonic's video extractor.
_MIME_BY_EXT = {
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
}


class VideoUnsupportedError(RuntimeError):
    """Raised when the runtime VIDEO object cannot self-encode (version floor)."""


def build_video_metadata(
    prompt: Optional[Any], extra_pnginfo: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Build the ``save_to`` metadata dict, byte-for-byte like native SaveVideo.

    Returns ``None`` when there is nothing to embed (so ``save_to`` skips the
    metadata write entirely, matching ``disable_metadata``).
    """
    metadata: Dict[str, Any] = {}
    if extra_pnginfo:
        metadata.update(extra_pnginfo)  # injects the top-level "workflow" key
    if prompt is not None:
        metadata["prompt"] = prompt
    return metadata or None


def _resolve_enums(video: Any, fmt: str, codec: str) -> Tuple[Any, Any]:
    """Best-effort map format/codec strings to ComfyUI's enums.

    ``save_to`` type-hints ``VideoContainer`` / ``VideoCodec``; those live in the
    same module as the concrete VIDEO type. We resolve them from *that* module so
    we follow ComfyUI wherever it moves the symbols, and fall back to the raw
    lowercase strings when they can't be found (they are str-enums, so
    ``save_to``'s ``== VideoContainer.AUTO`` comparisons still hold). The real
    encode is validated at E2E on the RTX box.
    """
    try:
        module = importlib.import_module(type(video).__module__)
    except Exception:  # pragma: no cover - defensive
        return fmt, codec

    def pick(enum_name: str, value: str) -> Any:
        enum_cls = getattr(module, enum_name, None)
        if enum_cls is None:
            return value
        try:
            return enum_cls(value)  # by value, e.g. "auto"
        except Exception:
            try:
                return enum_cls[value.upper()]  # by member name, e.g. AUTO
            except Exception:
                return getattr(enum_cls, "AUTO", value)

    return pick("VideoContainer", fmt), pick("VideoCodec", codec)


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:  # pragma: no cover - defensive
        pass


def save_video_to_tmp(
    video: Any,
    prompt: Optional[Any] = None,
    extra_pnginfo: Optional[Dict[str, Any]] = None,
    fmt: str = "auto",
    codec: str = "auto",
    tmp_dir: Optional[str] = None,
) -> Tuple[str, str]:
    """Encode ``video`` (workflow embedded) to a temp file; return ``(path, mime)``.

    The caller is responsible for deleting ``path`` after uploading it (the node
    does this in a ``finally``). Raises ``VideoUnsupportedError`` when
    the VIDEO object has no ``save_to``.
    """
    if not hasattr(video, "save_to"):
        raise VideoUnsupportedError(VIDEO_FLOOR_MESSAGE)

    metadata = build_video_metadata(prompt, extra_pnginfo)
    container, video_codec = _resolve_enums(video, fmt, codec)
    ext = _EXT_BY_FORMAT.get((fmt or "auto").lower(), "mp4")

    fd, path = tempfile.mkstemp(suffix="." + ext, dir=tmp_dir)
    os.close(fd)
    try:
        video.save_to(
            path, format=container, codec=video_codec, metadata=metadata
        )
    except Exception:
        _safe_unlink(path)
        raise
    return path, _MIME_BY_EXT.get(ext, "video/mp4")
