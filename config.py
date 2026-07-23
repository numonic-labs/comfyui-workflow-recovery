"""Configuration for the Workflow Recovery custom node.

Design constraints (do not weaken without review):
  * This package holds **no secret**. No API token, signing key, or privileged
    credential is embedded here or anywhere in the repo. The sidebar "save
    lineage" funnel relays a *user-supplied* token (pasted into the node's
    client settings, stored browser-side); the asset-save graph nodes read a
    ``napi_`` key from the **host** (see ``credential.py``). Neither is persisted
    by this package.
  * Recovery is **local-first**. The default recovery path reads the image's own
    embedded ComfyUI metadata on the user's machine with no network call.

Endpoint URLs are resolved from environment variables first, then fall back to
the documented public defaults, so the node can be pointed at a local mock
during development.

Phase B note: the hosted "enhanced recovery" (image-inspect) path was removed —
this file now covers only the display name, the HTTP timeout, and the sidebar
lineage-save funnel's connect/save URLs. The asset-save nodes resolve their own
host + key via ``credential.py``.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Public service endpoints for the sidebar lineage-save funnel (kept as a
# lineage-only fallback). Overridable via environment variables so
# the node can run against a local mock before the real URLs are live.
# ---------------------------------------------------------------------------

_DEFAULT_SAVE_URL = "https://api.numonic.ai/v1/comfy-lineage/save"
_DEFAULT_CONNECT_URL = "https://app.numonic.ai/connect/comfyui"

ENV_SAVE_URL = "WORKFLOW_RECOVERY_SAVE_URL"
ENV_CONNECT_URL = "WORKFLOW_RECOVERY_CONNECT_URL"
ENV_HTTP_TIMEOUT = "WORKFLOW_RECOVERY_HTTP_TIMEOUT"

# Product display name surfaced in the UI. Kept in one place so a rename is a
# one-line change.
DISPLAY_NAME = "Numonic Workflow Recovery"


def save_url() -> str:
    """URL of the opt-in authenticated "save lineage to my account" endpoint."""
    return os.environ.get(ENV_SAVE_URL, _DEFAULT_SAVE_URL).strip()


def connect_url() -> str:
    """URL the user opens to connect their account and obtain a scoped token."""
    return os.environ.get(ENV_CONNECT_URL, _DEFAULT_CONNECT_URL).strip()


def http_timeout() -> float:
    """Outbound HTTP timeout (seconds) for the network calls."""
    raw = os.environ.get(ENV_HTTP_TIMEOUT, "20")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 20.0
    return value if value > 0 else 20.0


def client_settings() -> dict:
    """Non-secret configuration handed to the browser extension on load.

    Deliberately contains NO token and NO secret — only public URLs the frontend
    needs to render the correct affordances.
    """
    return {
        "displayName": DISPLAY_NAME,
        "connectUrl": connect_url(),
    }
