"""Server routes registered on ``PromptServer.instance.routes``.

Three routes, namespaced under ``/numonic/workflow-recovery``:

  * ``GET  /status``   — returns non-secret client settings (display name,
    connect URL, whether enhanced recovery is configured). Holds no token.
  * ``POST /recover``  — OPT-IN enhanced recovery. Accepts an uploaded image,
    forwards it to the hosted inspect service, returns the enriched lineage.
    Only ever called when the user has explicitly enabled enhanced recovery in
    the UI. Read-only; stores nothing.
  * ``POST /save``     — OPT-IN, AUTHENTICATED funnel hook. Relays the recovered
    lineage to the user's own account using a token the *user* supplies in the
    request. This package holds no token of its own.

The blocking outbound HTTP calls run in a thread executor so the aiohttp event
loop is never blocked. Registration is a no-op when ComfyUI's server is not
importable (e.g. during unit tests), so importing this module is always safe.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from . import config
from . import inspect_client
from . import save_client

ROUTE_PREFIX = "/numonic/workflow-recovery"


def _json_response(payload: dict, status: int = 200):
    # Imported lazily so this module imports without aiohttp present.
    from aiohttp import web

    return web.json_response(payload, status=status)


async def _run_blocking(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


async def handle_status(_request):
    return _json_response(config.client_settings())


async def handle_recover(request):
    """OPT-IN enhanced recovery. Forwards the uploaded image to the inspect API."""
    from aiohttp import web  # noqa: F401 (ensures aiohttp present at call time)

    try:
        reader = await request.multipart()
    except Exception:
        return _json_response({"error": "Expected multipart/form-data."}, status=400)

    image_bytes: Optional[bytes] = None
    filename = "image.png"
    include_raw = False

    async for part in reader:
        if part.name == "image":
            filename = part.filename or "image.png"
            image_bytes = await part.read(decode=False)
        elif part.name == "include_raw":
            include_raw = (await part.text()).strip().lower() in ("1", "true", "yes")

    if not image_bytes:
        return _json_response({"error": "No image supplied."}, status=400)

    try:
        result = await _run_blocking(
            _enhanced_call, image_bytes, filename, include_raw
        )
    except inspect_client.InspectError as exc:
        status = exc.status or 502
        return _json_response({"error": str(exc)}, status=status)

    return _json_response(result)


def _enhanced_call(image_bytes: bytes, filename: str, include_raw: bool):
    return inspect_client.fetch_enhanced_lineage(
        image_bytes, filename=filename, include_raw=include_raw
    )


async def handle_save(request):
    """OPT-IN authenticated funnel hook. Relays a user-supplied token; stores none."""
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Expected a JSON body."}, status=400)

    lineage_result = body.get("lineage")
    source_filename = body.get("source_filename", "")
    # Token is supplied per-request by the client (browser-stored, user-owned).
    # Prefer the Authorization header; accept a body field as a fallback.
    user_token = _bearer_from_request(request) or body.get("token", "")

    if not isinstance(lineage_result, dict):
        return _json_response({"error": "Missing lineage to save."}, status=400)

    try:
        result = await _run_blocking(
            _save_call, lineage_result, user_token, source_filename
        )
    except save_client.MissingTokenError as exc:
        return _json_response(
            {"error": str(exc), "connect_url": config.connect_url()}, status=401
        )
    except save_client.SaveError as exc:
        return _json_response({"error": str(exc)}, status=exc.status or 502)

    return _json_response({"ok": True, "result": result})


def _bearer_from_request(request) -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _save_call(lineage_result: dict, user_token: str, source_filename: str):
    return save_client.save_lineage(
        lineage_result, user_token=user_token, source_filename=source_filename
    )


def register_routes() -> bool:
    """Attach routes to the running ComfyUI server. No-op if unavailable."""
    try:
        from server import PromptServer  # type: ignore
    except Exception:
        return False

    instance = getattr(PromptServer, "instance", None)
    if instance is None or not hasattr(instance, "routes"):
        return False

    routes = instance.routes
    routes.get(ROUTE_PREFIX + "/status")(handle_status)
    routes.post(ROUTE_PREFIX + "/recover")(handle_recover)
    routes.post(ROUTE_PREFIX + "/save")(handle_save)
    return True
