"""Host-side credential + endpoint resolution for the asset-save nodes.

Design constraint (do not weaken): the API key is read from the **host
environment**, never from a node widget. A widget value serializes into saved
workflows *and* embeds into the output PNG's metadata — leaking the key. The
node runs inside ComfyUI's Python process, so it reads the key exactly the way
any host-side tool would:

    1. the ``NUMONIC_API_KEY`` environment variable (highest precedence), or
    2. ``~/.numonic/config.json`` — ``{ "api_key": "napi_..." }``.

Mint a ``write``-scoped ``napi_`` key in Numonic **Settings -> API Keys** (there
is a "ComfyUI node key" preset). Set it once on the host; every graph run then
saves to your tenant with no per-workflow secret.

Endpoint hosts are overridable so the node can be pointed at a local Numonic
during development. All values default to the public product host.
"""

from __future__ import annotations

import json
import os
from typing import Optional

# ---------------------------------------------------------------------------
# Environment variables (all optional except the key itself).
# ---------------------------------------------------------------------------

API_KEY_ENV = "NUMONIC_API_KEY"
# Base host for the app UI — used to build the returned gallery deep-link.
ENV_APP_URL = "NUMONIC_APP_URL"
# Base host for the REST API (`/api/v1/...`). Defaults to the app host.
ENV_API_URL = "NUMONIC_API_URL"

# Canonical host: numonic.ai 301-redirects to www, and urllib turns a redirected
# POST into a GET (dropping the body), so the node must target www directly.
_DEFAULT_APP_URL = "https://www.numonic.ai"

# Path to the optional on-host config file that can carry the key (and,
# optionally, host overrides) when an env var is inconvenient.
_CONFIG_PATH = os.path.join("~", ".numonic", "config.json")


class MissingCredentialError(Exception):
    """Raised when no API key is available on the host.

    The message is user-facing: it tells the operator exactly how to set the
    key, because the fix is a one-time host action, not a graph change.
    """


# The config file holds a credential in plain text (as `~/.aws/credentials`,
# `~/.npmrc` and most developer tooling do): its protection is your OS user
# account. On a machine you share with other people, restrict it — see the
# README, "About this file". Warn at most once per process so a graph that saves
# many images does not spam the console.
_permission_warned = False


def _warn_if_readable_by_others(path: str) -> None:
    """Warn when the config file is group/world-readable.

    POSIX only, deliberately: Windows secures files with NTFS ACLs, and
    ``os.stat()`` there reports synthetic mode bits that do not reflect them —
    checking those bits would print a false warning on every Windows machine.
    Windows guidance (``icacls``) lives in the README instead.
    """
    global _permission_warned
    if _permission_warned or os.name != "posix":
        return
    try:
        mode = os.stat(path).st_mode
    except OSError:  # pragma: no cover - defensive
        return
    if mode & 0o077:
        _permission_warned = True
        print(
            "[Numonic] Warning: %s is readable by other users on this machine. "
            "It contains your API key in plain text. Restrict it with: "
            "chmod 600 %s" % (path, path)
        )


def _read_config_file() -> dict:
    """Return the parsed ``~/.numonic/config.json`` or an empty dict."""
    path = os.path.expanduser(_CONFIG_PATH)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    _warn_if_readable_by_others(path)
    return data if isinstance(data, dict) else {}


def load_api_key() -> Optional[str]:
    """Resolve the ``napi_`` key from env first, then the host config file.

    Returns ``None`` when no key is configured, so callers can surface a
    "connect" message rather than crashing the graph.
    """
    env_key = (os.environ.get(API_KEY_ENV) or "").strip()
    if env_key:
        return env_key
    file_key = str(_read_config_file().get("api_key") or "").strip()
    return file_key or None


def require_api_key() -> str:
    """Return the key or raise ``MissingCredentialError`` with setup guidance."""
    key = load_api_key()
    if not key:
        raise MissingCredentialError(
            "No Numonic API key found. Set NUMONIC_API_KEY (or put "
            '{"api_key": "napi_..."} in ~/.numonic/config.json), then restart '
            "ComfyUI. Mint a write-scoped key in Numonic -> Settings -> API Keys."
        )
    return key


def app_base_url() -> str:
    """Base URL of the Numonic app (for the returned gallery deep-link)."""
    override = (os.environ.get(ENV_APP_URL) or "").strip()
    if override:
        return override.rstrip("/")
    file_url = str(_read_config_file().get("app_url") or "").strip()
    return (file_url or _DEFAULT_APP_URL).rstrip("/")


def api_base_url() -> str:
    """Base URL of the Numonic REST API. Defaults to the app host."""
    override = (os.environ.get(ENV_API_URL) or "").strip()
    if override:
        return override.rstrip("/")
    file_url = str(_read_config_file().get("api_url") or "").strip()
    return (file_url or app_base_url()).rstrip("/")


def gallery_url(asset_h: str) -> str:
    """Build the authenticated gallery deep-link for a confirmed asset."""
    return "%s/app/assets/%s" % (app_base_url(), asset_h)
