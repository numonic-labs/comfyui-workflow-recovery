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


def flux_prompt() -> dict:
    """A modern Flux / custom-sampling API prompt.

    Modeled on a real ``Flux 2 dev`` generation (ComfyUI default Flux 2 template):
    the seed lives on ``RandomNoise.noise_seed`` (not ``KSampler.seed``), the
    sampler on ``KSamplerSelect``, and ``SamplerCustomAdvanced`` links them.
    Regression guard for the noise_seed recovery fix.
    """
    return {
        "12": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors"},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "high fashion, vintage couture, street photography"},
        },
        "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1027111520328378}},
        "13": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": ["25", 0], "sampler": ["16", 0]},
        },
        "101": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "lora_name": "Flux_2-Turbo-LoRA_comfyui.safetensors",
                "model": ["12", 0],
            },
        },
        "26": {"class_type": "FluxGuidance", "inputs": {"guidance": 4.0}},
        # A genuine third-party node, to prove real custom nodes still surface.
        "77": {"class_type": "DetailDaemonSamplerNode", "inputs": {"sampler": ["16", 0]}},
    }


def _core_node(node_id: int, node_type: str) -> dict:
    """A UI-graph node stamped as core ComfyUI, the way ComfyUI writes it."""
    return {
        "id": node_id,
        "type": node_type,
        "properties": {"cnr_id": "comfy-core", "Node name for S&R": node_type},
    }


def flux_workflow() -> dict:
    """UI workflow graph pairing with :func:`flux_prompt`.

    Mirrors a real Flux 2 template: the sampling nodes live inside a *subgraph*
    definition, and every built-in carries ``properties.cnr_id == "comfy-core"``.
    One third-party node carries a different ``cnr_id``.
    """
    return {
        "id": "wf-1",
        "version": 0.4,
        "nodes": [_core_node(12, "UNETLoader"), _core_node(6, "CLIPTextEncode")],
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-1",
                    "name": "Text to Image (Flux.2 Dev)",
                    "nodes": [
                        _core_node(25, "RandomNoise"),
                        _core_node(16, "KSamplerSelect"),
                        _core_node(13, "SamplerCustomAdvanced"),
                        _core_node(26, "FluxGuidance"),
                        {
                            "id": 77,
                            "type": "DetailDaemonSamplerNode",
                            "properties": {"cnr_id": "detail-daemon"},
                        },
                    ],
                }
            ]
        },
    }


def flux_png() -> bytes:
    """A PNG carrying the Flux (noise_seed) prompt as uncompressed tEXt."""
    return make_png(text_chunks={"prompt": json.dumps(flux_prompt())})


def flux_png_with_workflow() -> bytes:
    """A Flux PNG carrying BOTH the API prompt and the UI workflow graph."""
    return make_png(
        text_chunks={
            "prompt": json.dumps(flux_prompt()),
            "workflow": json.dumps(flux_workflow()),
        }
    )


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
