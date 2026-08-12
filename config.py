"""Configuration for the Workflow Recovery custom node.

Design constraints (do not weaken without review):
  * This package holds **no secret**. No API token, signing key, or privileged
    credential is embedded here or anywhere in the repo. The asset-save graph
    nodes read a ``napi_`` key from the **host** (see ``credential.py``); it is
    never persisted by this package.
  * Recovery is **local-first**. The recovery path reads the image's own
    embedded ComfyUI metadata on the user's machine with no network call.

Note: the hosted "enhanced recovery" (image-inspect) path and the browser
sidebar (with its lineage-save funnel) were both removed in v0.3.0 — this file
now covers only the outbound HTTP timeout shared by the save nodes. The
asset-save nodes resolve their own host + key via ``credential.py``.
"""

from __future__ import annotations

import os

ENV_HTTP_TIMEOUT = "WORKFLOW_RECOVERY_HTTP_TIMEOUT"


def http_timeout() -> float:
    """Outbound HTTP timeout (seconds) for the network calls."""
    raw = os.environ.get(ENV_HTTP_TIMEOUT, "20")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 20.0
    return value if value > 0 else 20.0
