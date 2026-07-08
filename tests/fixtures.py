"""Stdlib-only helpers to build PNG fixtures with embedded ComfyUI metadata."""

import json
import struct
import zlib


def _chunk(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)


def make_png(text_chunks=None, ztext_chunks=None, itext_chunks=None) -> bytes:
    """Build a minimal but structurally-valid PNG carrying the given text chunks.

    ``text_chunks``  -> tEXt (uncompressed)
    ``ztext_chunks`` -> zTXt (zlib-compressed)
    ``itext_chunks`` -> iTXt (uncompressed international)
    """
    sig = b"\x89PNG\r\n\x1a\n"
    parts = [sig, _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))]

    for key, value in (text_chunks or {}).items():
        body = key.encode("latin-1") + b"\x00" + value.encode("utf-8")
        parts.append(_chunk(b"tEXt", body))

    for key, value in (ztext_chunks or {}).items():
        compressed = zlib.compress(value.encode("utf-8"))
        body = key.encode("latin-1") + b"\x00" + b"\x00" + compressed
        parts.append(_chunk(b"zTXt", body))

    for key, value in (itext_chunks or {}).items():
        # keyword\0 compflag(0) compmethod(0) lang\0 translated\0 text
        body = (
            key.encode("latin-1")
            + b"\x00"
            + b"\x00\x00"
            + b"\x00"
            + b"\x00"
            + value.encode("utf-8")
        )
        parts.append(_chunk(b"iTXt", body))

    parts.append(_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")))
    parts.append(_chunk(b"IEND", b""))
    return b"".join(parts)


def sample_prompt() -> dict:
    """A realistic ComfyUI API-format prompt graph."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "sampler_name": "euler",
                "model": ["10", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
        },
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024}},
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a photograph of a cat", "clip": ["10", 1]},
            "_meta": {"title": "Positive Prompt"},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "blurry, low quality", "clip": ["10", 1]},
            "_meta": {"title": "Negative Prompt"},
        },
        "10": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "add_detail.safetensors",
                "model": ["4", 0],
                "clip": ["4", 1],
            },
        },
        "12": {
            "class_type": "RIFE VFI",  # a custom (non-core) node
            "inputs": {"frames": ["3", 0]},
        },
    }


def sample_workflow() -> dict:
    """A minimal UI-graph chunk."""
    return {"last_node_id": 12, "nodes": [], "links": [], "version": 0.4}


def comfy_png() -> bytes:
    """A PNG carrying both ComfyUI chunks as uncompressed tEXt."""
    return make_png(
        text_chunks={
            "workflow": json.dumps(sample_workflow()),
            "prompt": json.dumps(sample_prompt()),
        }
    )


def comfy_png_compressed() -> bytes:
    """A PNG carrying the ComfyUI chunks as zTXt (compressed) — the exifreader trap."""
    return make_png(
        ztext_chunks={
            "workflow": json.dumps(sample_workflow()),
            "prompt": json.dumps(sample_prompt()),
        }
    )


def plain_png() -> bytes:
    """A valid PNG with no ComfyUI metadata."""
    return make_png(text_chunks={"Software": "GIMP"})
