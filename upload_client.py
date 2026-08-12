"""Type-agnostic asset-upload core.

One function — ``upload_asset`` — drives Numonic's ComfyUI ingest flow with the
host-configured ``napi_`` key and returns the asset's gallery link. It is
deliberately media-agnostic: it takes already-encoded ``bytes`` plus a
``mime_type``; the per-type work (encoding an IMAGE tensor to PNG, or asking a
``VIDEO`` to ``save_to`` an mp4) lives in the producer that obtains the bytes.

Three phases against the dedicated ComfyUI ingest endpoints (the tenant is
resolved server-side from the key, so the node needs no ``X-Tenant-ID``). An API
key with ``write`` OR ``comfy-ingest`` scope authenticates every call:

  1. ``POST /api/v1/comfy-lineage/asset/signed-url``  ``{ filename, contentType }``
        -> ``{ signedUrl, token, path }``
  2. ``PUT  <signedUrl>``  — bytes go **straight to storage** (the presigned URL
        carries its own token), never through the web tier — this keeps large
        video uploads off the serverless request-body size limit.
  3. ``POST /api/v1/import/comfyui/confirm-upload``
        ``{ path, filename, fileSize, mimeType }``
        -> ``{ success, url, asset: { assetH, ... }, metadata }``
        The server downloads the file, extracts ComfyUI lineage, creates the
        asset, and returns the in-app gallery deep-link as ``url``.

Lineage is auto-extracted **server-side** from the embedded workflow, so this
core does not touch metadata — the producer already embedded it in the bytes.

Stdlib only (``urllib``). Blocking; the graph
node calls it from ComfyUI's worker thread.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from . import config
from . import credential

_SIGNED_URL_PATH = "/api/v1/comfy-lineage/asset/signed-url"
_CONFIRM_PATH = "/api/v1/import/comfyui/confirm-upload"
_USER_AGENT = "numonic-workflow-recovery/0.3 (+https://numonic.ai)"


class UploadError(Exception):
    """Raised on any transport / HTTP failure in the three-phase upload.

    ``status`` mirrors the HTTP code when there is one so the node can map it to
    a user-facing message (401/403 connect, 413 storage full, 429 rate-limited).
    """

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def _friendly_http_error(exc: urllib.error.HTTPError, phase: str) -> UploadError:
    """Translate an HTTP status into an actionable, user-facing message."""
    code = exc.code
    if code in (401, 403):
        return UploadError(
            "Numonic rejected the API key (HTTP %s). Check NUMONIC_API_KEY is a "
            "valid write- or comfy-ingest-scoped key from Settings -> API Keys."
            % code,
            status=code,
        )
    if code == 413:
        return UploadError(
            "Your Numonic storage is full (HTTP 413). Free up space or raise the "
            "tenant storage limit, then re-run.",
            status=413,
        )
    if code == 429:
        return UploadError(
            "Numonic is rate-limiting uploads (HTTP 429). Wait a moment and "
            "re-run the graph.",
            status=429,
        )
    return UploadError(
        "Numonic upload failed during %s (HTTP %s)." % (phase, code), status=code
    )


def _request_json(
    url: str,
    *,
    method: str,
    headers: Dict[str, str],
    body: Optional[bytes] = None,
    timeout: float,
    phase: str,
) -> Any:
    """Issue a request and decode a JSON response, mapping errors uniformly."""
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise _friendly_http_error(exc, phase) from exc
    except urllib.error.URLError as exc:
        raise UploadError(
            "Numonic is unreachable during %s: %s" % (phase, exc.reason)
        ) from exc

    if not payload:
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise UploadError(
            "Numonic returned an invalid response during %s." % phase
        ) from exc


def _phase1_signed_url(
    api_base: str,
    filename: str,
    mime_type: str,
    auth: Dict[str, str],
    timeout: float,
) -> Dict[str, str]:
    body = json.dumps({"filename": filename, "contentType": mime_type}).encode("utf-8")
    data = _request_json(
        "%s%s" % (api_base, _SIGNED_URL_PATH),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **auth,
        },
        body=body,
        timeout=timeout,
        phase="signed-url request",
    )
    signed_url = (data or {}).get("signedUrl")
    path = (data or {}).get("path")
    if not signed_url or not path:
        raise UploadError("Numonic did not return a signed upload URL.")
    return {"signedUrl": signed_url, "path": path}


def _phase2_put_bytes(
    signed_url: str, data: bytes, mime_type: str, timeout: float
) -> None:
    # The presigned URL carries its own token — do NOT attach the napi_ key here.
    request = urllib.request.Request(
        signed_url,
        data=data,
        method="PUT",
        headers={"Content-Type": mime_type, "Content-Length": str(len(data))},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise _friendly_http_error(exc, "storage upload") from exc
    except urllib.error.URLError as exc:
        raise UploadError(
            "Storage upload failed (unreachable): %s" % exc.reason
        ) from exc


def _phase3_confirm(
    api_base: str,
    storage_path: str,
    filename: str,
    file_size: int,
    mime_type: str,
    auth: Dict[str, str],
    timeout: float,
) -> Dict[str, Any]:
    document: Dict[str, Any] = {
        "path": storage_path,
        "filename": filename,
        "fileSize": file_size,
        "mimeType": mime_type,
    }
    body = json.dumps(document).encode("utf-8")
    data = _request_json(
        "%s%s" % (api_base, _CONFIRM_PATH),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **auth,
        },
        body=body,
        timeout=timeout,
        phase="confirm upload",
    )
    if not isinstance(data, dict):
        raise UploadError("Numonic confirm returned an unexpected response.")
    asset = data.get("asset")
    asset_h = asset.get("assetH") if isinstance(asset, dict) else None
    if not asset_h:
        raise UploadError("Numonic confirm did not return an assetH.")
    return data


def upload_asset(
    data: bytes,
    filename: str,
    mime_type: str,
    *,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    app_base: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Run the three-phase upload and return the asset + gallery link.

    Returns a dict::

        {
          "assetH": "...",
          "gallery_url": "https://numonic.ai/app/assets/...",
          "filename": "...",
          "mimeType": "...",
          "confirm": { ...raw confirm-upload response... },
        }

    ``gallery_url`` is the server-provided deep-link (confirm-upload ``url``);
    if the server omits it we fall back to building it from the assetH.

    Raises ``credential.MissingCredentialError`` when no key is configured and
    ``UploadError`` (with ``status``) on any transport/HTTP failure. The upload
    is stateless: re-running it with identical bytes is safe — server-side CID
    dedup keeps a re-save from ballooning tenant storage.
    """
    if not data:
        raise UploadError("Refusing to upload zero bytes.")

    key = (api_key or credential.require_api_key()).strip()
    resolved_api_base = (api_base or credential.api_base_url()).rstrip("/")
    resolved_app_base = (app_base or credential.app_base_url()).rstrip("/")
    effective_timeout = timeout if timeout is not None else config.http_timeout()

    auth: Dict[str, str] = {
        "Authorization": "Bearer %s" % key,
        "User-Agent": _USER_AGENT,
    }

    signed = _phase1_signed_url(
        resolved_api_base, filename, mime_type, auth, effective_timeout
    )
    _phase2_put_bytes(signed["signedUrl"], data, mime_type, effective_timeout)
    confirm = _phase3_confirm(
        resolved_api_base,
        signed["path"],
        filename,
        len(data),
        mime_type,
        auth,
        effective_timeout,
    )

    asset_h = str(confirm["asset"]["assetH"])
    gallery_url = confirm.get("url") or "%s/app/assets/%s" % (
        resolved_app_base,
        asset_h,
    )
    return {
        "assetH": asset_h,
        "gallery_url": gallery_url,
        "filename": filename,
        "mimeType": mime_type,
        "confirm": confirm,
    }
