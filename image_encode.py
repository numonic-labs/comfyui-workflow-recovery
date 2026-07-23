"""Encode an IMAGE tensor to a PNG carrying ComfyUI lineage.

Two concerns, deliberately split so the lineage-embedding logic is testable
with **zero third-party dependencies**:

  * ``embed_text_chunks`` — insert ``tEXt`` chunks into an existing PNG using
    only the standard library (mirrors what ``png_metadata.py`` reads back). No
    PIL. This is the part that carries ``prompt`` / ``workflow`` and must stay
    byte-compatible with Numonic's server-side metadata extractor and the local
    reader.
  * ``tensor_to_png_bytes`` — turn a ComfyUI ``IMAGE`` tensor into raw PNG bytes
    using PIL + numpy (both shipped by ComfyUI). PIL is imported lazily inside
    the function so this module imports cleanly in the stdlib-only test runner.

The metadata mapping mirrors core ``SaveImage``: a ``prompt`` text chunk plus
one chunk per key in ``extra_pnginfo`` (so the UI graph lands under the top-level
``workflow`` keyword). Numonic then auto-extracts lineage from that on confirm.
"""

from __future__ import annotations

import io
import json
import struct
import zlib
from typing import Any, Dict, List, Optional

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def comfy_metadata_mapping(
    prompt: Optional[Any], extra_pnginfo: Optional[Dict[str, Any]]
) -> Dict[str, str]:
    """Build the ``{keyword: json_text}`` chunk map, exactly like ``SaveImage``.

    ``prompt`` -> a ``prompt`` chunk; each key of ``extra_pnginfo`` -> its own
    chunk (``extra_pnginfo = {"workflow": <graph>}`` therefore yields a
    top-level ``workflow`` chunk — the keyword Numonic's extractor scans for).
    Values already given as ``str`` are passed through; everything else is
    JSON-encoded.
    """
    mapping: Dict[str, str] = {}
    if prompt is not None:
        mapping["prompt"] = prompt if isinstance(prompt, str) else json.dumps(prompt)
    if extra_pnginfo:
        for key, value in extra_pnginfo.items():
            mapping[str(key)] = (
                value if isinstance(value, str) else json.dumps(value)
            )
    return mapping


def _text_chunk(keyword: str, text: str) -> bytes:
    body = keyword.encode("latin-1", "replace") + b"\x00" + text.encode("utf-8")
    crc = zlib.crc32(b"tEXt" + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", crc)


def embed_text_chunks(png_bytes: bytes, mapping: Dict[str, str]) -> bytes:
    """Return ``png_bytes`` with ``tEXt`` chunks inserted right after ``IHDR``.

    Placing text chunks immediately after ``IHDR`` (and before ``IDAT``) is
    spec-valid and matches what PIL's ``PngInfo`` does. A non-PNG input or an
    empty mapping is returned unchanged.
    """
    if not mapping or not png_bytes.startswith(_PNG_SIGNATURE):
        return png_bytes

    # Locate the end of the IHDR chunk: sig(8) + len(4)+type(4)+data(len)+crc(4).
    pos = len(_PNG_SIGNATURE)
    if pos + 8 > len(png_bytes):
        return png_bytes
    (ihdr_len,) = struct.unpack(">I", png_bytes[pos : pos + 4])
    ihdr_end = pos + 8 + ihdr_len + 4  # +crc
    if ihdr_end > len(png_bytes):
        return png_bytes

    inserted: List[bytes] = [_text_chunk(k, v) for k, v in mapping.items()]
    return png_bytes[:ihdr_end] + b"".join(inserted) + png_bytes[ihdr_end:]


def tensor_to_png_bytes(
    image: Any,
    prompt: Optional[Any] = None,
    extra_pnginfo: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Encode a single ComfyUI ``IMAGE`` tensor (H×W×C, 0..1) to PNG bytes.

    Uses PIL + numpy (shipped by ComfyUI), imported lazily so this module stays
    importable without them. The embedded lineage is added by the stdlib
    ``embed_text_chunks`` so the encoder and the metadata format are decoupled.
    """
    import numpy as np  # provided by ComfyUI
    from PIL import Image  # provided by ComfyUI

    array = image.cpu().numpy() if hasattr(image, "cpu") else np.asarray(image)
    array = np.clip(255.0 * array, 0, 255).astype(np.uint8)
    pil_image = Image.fromarray(array)

    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    return embed_text_chunks(
        png_bytes, comfy_metadata_mapping(prompt, extra_pnginfo)
    )
