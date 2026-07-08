"""Local, zero-dependency reader for ComfyUI metadata embedded in PNG files.

ComfyUI embeds two text chunks into saved PNGs by default:
  * ``workflow`` — the UI graph (JSON)
  * ``prompt``   — the resolved API-format execution graph (JSON)

They are stored in PNG ``tEXt`` (uncompressed), ``zTXt`` (zlib-compressed), or
``iTXt`` (international, optionally compressed) chunks. This module reads all
three using only the Python standard library, so the local-first recovery path
requires no third-party dependency and never leaves the user's machine.

Reference: PNG spec (W3C) chunk layout — length(4) type(4) data(len) crc(4).
"""

from __future__ import annotations

import struct
import zlib
from typing import Dict

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# The two keywords ComfyUI writes. We also keep any other text chunks so callers
# can inspect non-standard tools (e.g. A1111 "parameters"), but only these two
# feed the ComfyUI lineage normalizer.
COMFY_KEYS = ("workflow", "prompt")


class NotAPngError(ValueError):
    """Raised when the supplied bytes are not a PNG image."""


def _read_text_chunks(data: bytes) -> Dict[str, str]:
    """Return a mapping of keyword -> text for all text chunks in a PNG."""
    if not data.startswith(_PNG_SIGNATURE):
        raise NotAPngError("Not a PNG file (bad signature).")

    chunks: Dict[str, str] = {}
    pos = len(_PNG_SIGNATURE)
    n = len(data)

    while pos + 8 <= n:
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        body_start = pos + 8
        body_end = body_start + length
        if body_end + 4 > n:
            break  # truncated chunk; stop gracefully
        body = data[body_start:body_end]

        try:
            if ctype == b"tEXt":
                keyword, text = _parse_text(body)
                if keyword:
                    chunks.setdefault(keyword, text)
            elif ctype == b"zTXt":
                keyword, text = _parse_ztext(body)
                if keyword:
                    chunks.setdefault(keyword, text)
            elif ctype == b"iTXt":
                keyword, text = _parse_itext(body)
                if keyword:
                    chunks.setdefault(keyword, text)
        except Exception:
            # A single malformed chunk must not abort the whole read.
            pass

        if ctype == b"IEND":
            break
        pos = body_end + 4  # skip CRC

    return chunks


def _parse_text(body: bytes):
    keyword, _, text = body.partition(b"\x00")
    return keyword.decode("latin-1", "replace"), text.decode("utf-8", "replace")


def _parse_ztext(body: bytes):
    keyword, _, rest = body.partition(b"\x00")
    if not rest:
        return keyword.decode("latin-1", "replace"), ""
    # rest[0] is the compression method (0 = zlib); remainder is compressed text.
    compressed = rest[1:]
    try:
        text = zlib.decompress(compressed).decode("utf-8", "replace")
    except zlib.error:
        text = ""
    return keyword.decode("latin-1", "replace"), text


def _parse_itext(body: bytes):
    # iTXt: keyword\0 compression_flag(1) compression_method(1)
    #       language_tag\0 translated_keyword\0 text
    keyword, _, rest = body.partition(b"\x00")
    if len(rest) < 2:
        return keyword.decode("latin-1", "replace"), ""
    compression_flag = rest[0]
    # rest[1] is compression method
    after_flags = rest[2:]
    # skip language tag and translated keyword (two null-terminated fields)
    _lang, _, after_lang = after_flags.partition(b"\x00")
    _translated, _, text_bytes = after_lang.partition(b"\x00")
    if compression_flag == 1:
        try:
            text = zlib.decompress(text_bytes).decode("utf-8", "replace")
        except zlib.error:
            text = ""
    else:
        text = text_bytes.decode("utf-8", "replace")
    return keyword.decode("latin-1", "replace"), text


def extract_comfy_chunks(data: bytes) -> Dict[str, str]:
    """Return only the ComfyUI ``workflow``/``prompt`` chunks that are present.

    Raises ``NotAPngError`` for non-PNG input. Returns an empty dict for a valid
    PNG that carries no ComfyUI metadata (caller decides how to surface that).
    """
    all_chunks = _read_text_chunks(data)
    return {k: all_chunks[k] for k in COMFY_KEYS if k in all_chunks}


def all_text_chunks(data: bytes) -> Dict[str, str]:
    """Return every text chunk (for diagnostics / non-ComfyUI tools)."""
    return _read_text_chunks(data)
