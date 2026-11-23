"""FastMCP stdio server exposing AntOrbit tools to Antigravity."""

from __future__ import annotations

import json
from typing import Any, Literal

try:
    from mcp.server.mcpserver import MCPServer as _MCPServer
except ImportError:  # pragma: no cover - compatibility with mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCPServer

from .client import AntOrbitClient

mcp = _MCPServer(
    "antorbit",
    instructions=(
        "AntOrbit publishes static/SPA websites to a self-hosted server under /s/<slug>/, "
        "supports built-in form submissions and KV state via /_antorbit/sdk.js, and pushes "
        "notifications via configured Bark/ntfy channels."
    ),
)


def _client() -> AntOrbitClient:
    return AntOrbitClient()


def _fmt(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def publish_site(
    directory: str | None = None,
    html: str | None = None,
    slug: str | None = None,
    title: str | None = None,
    description: str = "",
    password: str | None = None,
    clear_password: bool = False,
    ttl_hours: float | None = None,
    allow_submit: bool = False,
    kv_mode: Literal["off", "read", "readwrite"] = "off",
    notify_on_submit: bool = False,
    notify_channel: str = "",
    notify_on_publish: bool = False,
    notify_title: str | None = None,
    notify_body: str | None = None,
    notify_level: Literal["passive", "active", "timeSensitive", "critical"] = "active",
    notify_group: str | None = None,
) -> str:
    """Publish or update a website on AntOrbit from either a local directory or inline HTML.

    Pass either `directory` (local folder containing index.html and relative assets) OR
    `html` (single-file HTML string). Reusing an existing `slug` updates static files in
    place while preserving existing form submissions and KV entries.
    """
    res = await _client().publish_site(
        directory=directory,
        html=html,
        slug=slug,
        title=title,
        description=description,
        password=password,
        clear_password=clear_password,
        ttl_hours=ttl_hours,
        allow_submit=allow_submit,
        kv_mode=kv_mode,
        notify_on_submit=notify_on_submit,
        notify_channel=notify_channel,
        notify_on_publish=notify_on_publish,
        notify_title=notify_title,
        notify_body=notify_body,
        notify_level=notify_level,
        notify_group=notify_group,
    )
    return _fmt(res)


@mcp.tool()
async def list_sites() -> str:
    """List all hosted websites on the AntOrbit server along with URLs and stats."""
    return _fmt(await _client().list_sites())


@mcp.tool()
async def get_site(slug: str) -> str:
    """Get detailed metadata, stats, and URL for a hosted site by slug."""
    return _fmt(await _client().get_site(slug))


@mcp.tool()
async def update_site(
    slug: str,
    title: str | None = None,
    description: str | None = None,
    password: str | None = None,
    clear_password: bool = False,
    ttl_hours: float | None = None,
    allow_submit: bool | None = None,
    kv_mode: Literal["off", "read", "readwrite"] | None = None,
    notify_on_submit: bool | None = None,
    notify_channel: str | None = None,
) -> str:
    """Update site settings (title, password, TTL, interactive flags, submit notify) without re-uploading files."""
    payload: dict[str, Any] = {"clear_password": clear_password}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if password is not None:
        payload["password"] = password
    if ttl_hours is not None:
        payload["ttl_hours"] = ttl_hours
    if allow_submit is not None:
        payload["allow_submit"] = allow_submit
    if kv_mode is not None:
        payload["kv_mode"] = kv_mode
    if notify_on_submit is not None:
        payload["notify_on_submit"] = notify_on_submit
    if notify_channel is not None:
        payload["notify_channel"] = notify_channel
    return _fmt(await _client().update_site(slug, payload))


@mcp.tool()
async def delete_site(slug: str) -> str:
    """Permanently delete a hosted site, its files, submissions, and KV state."""
    return _fmt(await _client().delete_site(slug))


@mcp.tool()
async def get_submissions(
    slug: str,
    limit: int = 50,
    since_id: int | None = None,
) -> str:
    """Fetch form or approval submissions received by a hosted site."""
    return _fmt(await _client().get_submissions(slug, limit=limit, since_id=since_id))


@mcp.tool()
async def kv_list(slug: str) -> str:
    """List all KV state entries stored for a hosted site."""
    return _fmt(await _client().kv_list(slug))


@mcp.tool()
async def kv_get(slug: str, key: str) -> str:
    """Read a single KV entry by key for a hosted site."""
    return _fmt(await _client().kv_get(slug, key))


@mcp.tool()
async def kv_set(slug: str, key: str, value: Any) -> str:
    """Write or update a JSON KV entry for a hosted site."""
    return _fmt(await _client().kv_set(slug, key, value))


@mcp.tool()
async def kv_delete(slug: str, key: str) -> str:
    """Delete a KV entry from a hosted site."""
    return _fmt(await _client().kv_delete(slug, key))


@mcp.tool()
async def list_channels() -> str:
    """List configured notification channels (Bark / ntfy) available on the server."""
    return _fmt(await _client().list_channels())


@mcp.tool()
async def send_notification(
    title: str,
    body: str,
    channel: str | None = None,
    url: str | None = None,
    level: Literal["passive", "active", "timeSensitive", "critical"] = "active",
    group: str | None = None,
    sound: str | None = None,
    icon: str | None = None,
    site_slug: str | None = None,
) -> str:
    """Send a push notification via a named or default Bark/ntfy channel.

    Pass `url` so tapping the notification opens the target webpage directly.
    """
    return _fmt(
        await _client().send_notification(
            title=title,
            body=body,
            channel=channel,
            url=url,
            level=level,
            group=group,
            sound=sound,
            icon=icon,
            site_slug=site_slug,
        )
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
