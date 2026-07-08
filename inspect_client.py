"""Client for the opt-in hosted "enhanced recovery" endpoint (contract v0).

Uses only the Python standard library (``urllib``) so the package carries no
third-party dependency. The outbound call is blocking; server routes invoke it
via a thread executor so the aiohttp event loop is never blocked.

This path is OPT-IN: it sends the user's image to the hosted inspect service to
be parsed by the full extraction engine. The service is read-only and stateless
(it stores nothing), but because the image — and therefore its embedded prompt
text — leaves the machine, the frontend only calls it after explicit user
consent. See README "Privacy model".
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Optional

from . import config
from . import lineage


class InspectError(Exception):
    """Raised when the hosted inspect call fails. ``status`` mirrors HTTP code."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def _multipart_body(image_bytes: bytes, filename: str, include_raw: bool):
    """Encode a minimal multipart/form-data body (stdlib, no `requests`)."""
    boundary = "----WorkflowRecovery" + uuid.uuid4().hex
    crlf = b"\r\n"
    parts = []

    parts.append(("--" + boundary).encode())
    disp = 'Content-Disposition: form-data; name="image"; filename="%s"' % (
        filename or "image.png"
    )
    parts.append(disp.encode())
    parts.append(b"Content-Type: application/octet-stream")
    parts.append(b"")
    parts.append(image_bytes)

    if include_raw:
        parts.append(("--" + boundary).encode())
        parts.append(b'Content-Disposition: form-data; name="include_raw"')
        parts.append(b"")
        parts.append(b"true")

    parts.append(("--" + boundary + "--").encode())
    parts.append(b"")

    body = crlf.join(parts)
    content_type = "multipart/form-data; boundary=%s" % boundary
    return body, content_type


def fetch_enhanced_lineage(
    image_bytes: bytes,
    filename: str = "image.png",
    include_raw: bool = False,
    url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Call the hosted inspect endpoint and return a normalized LineageResult.

    Raises ``InspectError`` on transport / HTTP / decode failure so the caller
    can fall back to local recovery and surface a friendly message.
    """
    target = (url or config.inspect_url()).strip()
    if not target:
        raise InspectError("Enhanced recovery endpoint is not configured.")

    body, content_type = _multipart_body(image_bytes, filename, include_raw)
    request = urllib.request.Request(
        target,
        data=body,
        method="POST",
        headers={
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "numonic-workflow-recovery/0.1 (+https://numonic.ai)",
        },
    )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout if timeout is not None else config.http_timeout()
        ) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 415:
            raise InspectError("Unsupported media type.", status=415) from exc
        if exc.code == 422:
            raise InspectError(
                "No recoverable ComfyUI metadata in the image.", status=422
            ) from exc
        raise InspectError(
            "Enhanced recovery failed (HTTP %s)." % exc.code, status=exc.code
        ) from exc
    except urllib.error.URLError as exc:
        raise InspectError(
            "Enhanced recovery service is unreachable: %s" % exc.reason
        ) from exc

    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InspectError("Enhanced recovery returned invalid JSON.") from exc

    return lineage.coerce_contract(parsed, mode="enhanced")
