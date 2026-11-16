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
ENV_CONFIRM_TIMEOUT = "WORKFLOW_RECOVERY_CONFIRM_TIMEOUT"

_DEFAULT_HTTP_TIMEOUT = 20.0
# The confirm phase makes the server download the file, extract lineage and
# create the asset, so it scales with file size (a 20 s+ LTX video exceeded the
# 20 s default). It gets its own, longer default.
_DEFAULT_CONFIRM_TIMEOUT = 120.0


def _positive_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def http_timeout() -> float:
    """Outbound HTTP timeout (seconds) for the quick network calls."""
    return _positive_float(
        os.environ.get(ENV_HTTP_TIMEOUT), _DEFAULT_HTTP_TIMEOUT
    )


def confirm_timeout(floor: float = 0.0) -> float:
    """Timeout (seconds) for the confirm-upload call.

    A valid ``WORKFLOW_RECOVERY_CONFIRM_TIMEOUT`` always wins, even when it is
    lower than the shared timeout. Otherwise it is the 120 s default, but never
    lower than ``WORKFLOW_RECOVERY_HTTP_TIMEOUT`` (or ``floor``, the caller's own
    shared timeout) so a user who raised the shared timeout does not see it
    shrink for confirm.
    """
    default = max(_DEFAULT_CONFIRM_TIMEOUT, http_timeout(), floor)
    return _positive_float(os.environ.get(ENV_CONFIRM_TIMEOUT), default)
