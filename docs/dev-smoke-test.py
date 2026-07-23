#!/usr/bin/env python3
"""Manual end-to-end smoke test for the "Save to Numonic" upload core.

WHAT THIS IS
------------
A hand-run integration check that drives the node's real upload path
(``upload_client.upload_asset``) against a *live* Numonic instance, using a real
API key. It uploads a tiny generated-looking PNG with an embedded ComfyUI
workflow and verifies the whole round-trip:

    signed-url  ->  storage PUT  ->  confirm-upload  ->  gallery link + lineage

It exercises the exact server contract the graph nodes use — minus the
ComfyUI-only pixel encode — so it answers "will Save to Numonic actually succeed
against this server?" without needing ComfyUI installed.

THIS IS NOT AN AUTOMATED TEST.
------------------------------
It is deliberately NOT part of the unit suite and NOT run in CI: it makes real
network calls and needs credentials. It CANNOT run in a sandboxed build/CI
container. Run it in an environment that has:

    * network access to your Numonic instance, and
    * these environment variables set:

        NUMONIC_API_KEY   (required)  a write- or comfy-ingest-scoped napi_ key
        NUMONIC_API_URL   (optional)  REST API base, e.g. http://localhost:3000
                                      defaults to https://numonic.ai
        NUMONIC_APP_URL   (optional)  app base for the gallery link fallback

Usage:

    NUMONIC_API_KEY=napi_... NUMONIC_API_URL=http://localhost:3000 \
        python3 docs/dev-smoke-test.py

Exit code 0 = the asset was created and ComfyUI lineage was extracted.
Non-zero  = something in the chain failed (message explains which phase).
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import struct
import sys
import zlib

# ---------------------------------------------------------------------------
# Load the (hyphen-named) node package under an importable alias, exactly like
# tests/_bootstrap.py does, so `from wr import ...` resolves relative imports.
# ---------------------------------------------------------------------------
PKG_DIR = pathlib.Path(__file__).resolve().parents[1]
if "wr" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "wr",
        str(PKG_DIR / "__init__.py"),
        submodule_search_locations=[str(PKG_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["wr"] = module
    spec.loader.exec_module(module)

from wr import credential, image_encode, upload_client  # noqa: E402


def _minimal_png() -> bytes:
    """Build a structurally valid 1x1 PNG with no metadata (stdlib only)."""

    def chunk(ctype: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00")
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _sample_workflow() -> dict:
    return {"last_node_id": 1, "nodes": [], "links": [], "version": 0.4}


def _sample_prompt() -> dict:
    # A minimal ComfyUI API-format prompt so server-side lineage extraction has
    # something real to parse.
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {"seed": 1, "sampler_name": "euler", "model": ["2", 0]},
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "smoke-test.safetensors"},
        },
    }


def main() -> int:
    if not credential.load_api_key():
        print(
            "FAIL: NUMONIC_API_KEY is not set. Export a write- or comfy-ingest-"
            "scoped napi_ key and re-run (see this file's header).",
            file=sys.stderr,
        )
        return 2

    api_base = credential.api_base_url()
    print("Target API base: %s" % api_base)
    print("Building a 1x1 PNG with an embedded ComfyUI workflow...")

    png = image_encode.embed_text_chunks(
        _minimal_png(),
        image_encode.comfy_metadata_mapping(_sample_prompt(), {"workflow": _sample_workflow()}),
    )

    print("Uploading via the node's real 3-phase upload core...")
    try:
        result = upload_client.upload_asset(
            png, filename="numonic-smoke-test.png", mime_type="image/png"
        )
    except credential.MissingCredentialError as exc:
        print("FAIL (credential): %s" % exc, file=sys.stderr)
        return 2
    except upload_client.UploadError as exc:
        status = " [HTTP %s]" % exc.status if exc.status else ""
        print("FAIL (upload)%s: %s" % (status, exc), file=sys.stderr)
        return 1

    asset = (result.get("confirm") or {}).get("asset") or {}
    tool_name = asset.get("toolName")

    print("")
    print("  assetH:      %s" % result.get("assetH"))
    print("  gallery_url: %s" % result.get("gallery_url"))
    print("  toolName:    %s (lineage extracted server-side)" % tool_name)
    print("  full confirm response:")
    print(json.dumps(result.get("confirm"), indent=2)[:2000])
    print("")

    if not result.get("assetH"):
        print("FAIL: no assetH returned.", file=sys.stderr)
        return 1
    if tool_name != "ComfyUI":
        print(
            "WARN: asset created but server did not detect ComfyUI lineage "
            "(toolName=%r). The upload path works, but check that the embedded "
            "workflow reached the extractor." % tool_name,
            file=sys.stderr,
        )
        return 3

    print("PASS: asset created and ComfyUI lineage extracted. Open the gallery_url.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
