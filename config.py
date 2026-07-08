"""Configuration for the Workflow Recovery custom node.

Design constraints (do not weaken without review):
  * This package holds **no secret**. No API token, signing key, or privileged
    credential is embedded here or anywhere in the repo. Any authenticated call
    (the opt-in "save to Numonic" funnel) relays a *user-supplied* token that the
    user pastes into the node's client settings; it is never persisted server-side.
  * Recovery is **local-first**. The default recovery path reads the image's own
    embedded ComfyUI metadata on the user's machine with no network call. The
    hosted "enhanced recovery" endpoint is strictly opt-in.

Endpoint URLs are resolved from environment variables first, then fall back to
the documented public defaults. The public defaults are intentionally overridable
so the node can be pointed at a local mock during development and at the real
service once its URL is confirmed at integration time.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Public service endpoints.
#
# These are PUBLIC product endpoints (read-only inspect; authenticated save),
# not internal infrastructure. They are overridable via environment variables
# so the node can run against a local mock before the real URLs are live.
#
# NOTE (integration): the inspect endpoint contract is owned by the private
# "comfy-inspect" service (shared contract v0). Confirm the final base URL and
# path at integration time; until then these defaults may be pointed at a mock.
# ---------------------------------------------------------------------------

_DEFAULT_INSPECT_URL = "https://api.numonic.ai/v1/comfy-inspect"
_DEFAULT_SAVE_URL = "https://api.numonic.ai/v1/comfy-lineage/save"
_DEFAULT_CONNECT_URL = "https://app.numonic.ai/connect/comfyui"

ENV_INSPECT_URL = "WORKFLOW_RECOVERY_INSPECT_URL"
ENV_SAVE_URL = "WORKFLOW_RECOVERY_SAVE_URL"
ENV_CONNECT_URL = "WORKFLOW_RECOVERY_CONNECT_URL"
ENV_HTTP_TIMEOUT = "WORKFLOW_RECOVERY_HTTP_TIMEOUT"

# Product display name surfaced in the UI. Kept in one place so a rename is a
# one-line change.
DISPLAY_NAME = "Numonic Workflow Recovery"


def inspect_url() -> str:
    """URL of the opt-in hosted "enhanced recovery" endpoint (read-only)."""
    return os.environ.get(ENV_INSPECT_URL, _DEFAULT_INSPECT_URL).strip()


def save_url() -> str:
    """URL of the opt-in authenticated "save lineage to my account" endpoint."""
    return os.environ.get(ENV_SAVE_URL, _DEFAULT_SAVE_URL).strip()


def connect_url() -> str:
    """URL the user opens to connect their account and obtain a scoped token."""
    return os.environ.get(ENV_CONNECT_URL, _DEFAULT_CONNECT_URL).strip()


def http_timeout() -> float:
    """Outbound HTTP timeout (seconds) for the opt-in network calls."""
    raw = os.environ.get(ENV_HTTP_TIMEOUT, "20")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 20.0
    return value if value > 0 else 20.0


def client_settings() -> dict:
    """Non-secret configuration handed to the browser extension on load.

    Deliberately contains NO token and NO secret — only public URLs and flags
    the frontend needs to render the correct affordances.
    """
    return {
        "displayName": DISPLAY_NAME,
        "connectUrl": connect_url(),
        # The frontend never needs the raw inspect/save URLs: it always calls
        # this package's own server routes, which proxy outward. Exposing only
        # the connect URL keeps endpoint configuration server-side.
        "enhancedRecoveryAvailable": bool(inspect_url()),
    }
