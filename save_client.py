"""Client for the opt-in, authenticated "save lineage to my account" funnel.

This is the single privacy-critical write surface. Rules (enforced here):
  * The package holds **no secret**. The bearer token is supplied per-request by
    the user (pasted into the node's client settings, stored browser-side). It is
    relayed once and never persisted by this package.
  * No token → no call. The caller returns a "connect your account" prompt and
    keeps everything local. There is no anonymous save.
  * Only the *recovered lineage* the user chose to save is sent — never the raw
    image bytes, and never anything the user did not explicitly save.

Stdlib-only (``urllib``); blocking call invoked from a thread executor.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from . import config


class SaveError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class MissingTokenError(SaveError):
    """Raised when no user token is present — caller shows the connect prompt."""


def save_lineage(
    lineage_result: Dict[str, Any],
    user_token: str,
    source_filename: str = "",
    url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """POST the recovered lineage to the user's account using their own token.

    Returns the parsed JSON response on success (expected to include a link the
    user can open in Connected Folders). Raises ``MissingTokenError`` when no
    token is supplied and ``SaveError`` on any transport/HTTP failure.
    """
    token = (user_token or "").strip()
    if not token:
        raise MissingTokenError(
            "Connect your Numonic account to save this lineage.", status=401
        )

    target = (url or config.save_url()).strip()
    if not target:
        raise SaveError("Save endpoint is not configured.")

    document = {
        "source": lineage_result.get("source", "comfyui"),
        "source_filename": source_filename,
        "lineage": lineage_result,
    }
    body = json.dumps(document).encode("utf-8")

    request = urllib.request.Request(
        target,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer %s" % token,
            "User-Agent": "numonic-workflow-recovery/0.1 (+https://numonic.ai)",
        },
    )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout if timeout is not None else config.http_timeout()
        ) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise SaveError(
                "Your Numonic account token was rejected. Reconnect your account.",
                status=exc.code,
            ) from exc
        raise SaveError("Save failed (HTTP %s)." % exc.code, status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise SaveError("Numonic is unreachable: %s" % exc.reason) from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # A 2xx with a non-JSON body still counts as success.
        return {"ok": True}
