"""Numonic Workflow Recovery — a ComfyUI custom node pack.

Drop in a generated image → recover its full ComfyUI workflow lineage (prompts,
models, LoRAs, seed, sampler, custom nodes). Local-first and privacy-preserving;
optional opt-in enhanced recovery and account save.

This module is the ComfyUI entry point. ComfyUI discovers the pack by importing
this package and reading ``NODE_CLASS_MAPPINGS`` and ``WEB_DIRECTORY``.
"""

from __future__ import annotations

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from . import routes

# Serve the frontend extension (sidebar tab) from ./web.
WEB_DIRECTORY = "./web"

# Register the server routes (status / opt-in recover / opt-in save). Safe no-op
# when the ComfyUI server is not importable.
try:
    routes.register_routes()
except Exception as exc:  # pragma: no cover - never break ComfyUI startup
    print("[Numonic Workflow Recovery] route registration skipped: %s" % exc)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]

__version__ = "0.1.0"
