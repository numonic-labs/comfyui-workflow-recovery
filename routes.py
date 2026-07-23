"""Server routes registered on ``PromptServer.instance.routes``.

Two routes, namespaced under ``/numonic/workflow-recovery``:

  * ``GET  /status``   — returns non-secret client settings (display name,
    connect URL). Holds no token.
  * ``POST /save``     — OPT-IN, AUTHENTICATED funnel hook for the sidebar
    lineage-save fallback. Relays the recovered lineage to the user's own
    account using a token the *user* supplies in the request. This package holds
    no token of its own.

(The Phase B asset-save graph nodes upload real bytes directly from the worker
thread and do not use a server route — see ``upload_client.py``.)

The blocking outbound HTTP call runs in a thread executor so the aiohttp event
loop is never blocked. Registration is a no-op when ComfyUI's server is not
importable (e.g. during unit tests), so importing this module is always safe.
"""

from __future__ import annotations

import asyncio

from . import config
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
    routes.post(ROUTE_PREFIX + "/save")(handle_save)
    return True
