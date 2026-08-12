"""Numonic Workflow Recovery — a ComfyUI custom node pack.

Two things:
  * **Recover** — point the ``Extract Workflow Lineage`` node at a generated
    image and recover its full ComfyUI workflow lineage (prompts, models,
    LoRAs, seed, sampler, custom nodes). Local-first and privacy-preserving.
  * **Save to Numonic** — drop-in replacements for the stock *Save Image* /
    *Save Video* that ingest the generated asset (real bytes, with lineage) into
    your Numonic library and return its gallery link.

This module is the ComfyUI entry point. ComfyUI discovers the pack by importing
this package and reading ``NODE_CLASS_MAPPINGS``.

The pack ships **no frontend extension**: everything is a graph node, so there
is no ``WEB_DIRECTORY`` and no server route to register.
"""

from __future__ import annotations

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]

__version__ = "0.3.0"
