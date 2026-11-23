"""HTTP client and directory bundler for AntOrbit MCP server."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path
from typing import Any

import httpx

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


class AntOrbitError(RuntimeError):
    """Raised when AntOrbit configuration or API call fails."""


def pack_directory_to_zip(directory: str | Path) -> tuple[bytes, int]:
    """Pack a local directory into an in-memory ZIP archive. Returns (zip_bytes, file_count)."""
    root = Path(directory).expanduser().resolve()
    if not root.exists():
        raise AntOrbitError(f"Directory does not exist: {root}")
    if not root.is_dir():
        raise AntOrbitError(f"Path is not a directory: {root}")

    buf = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for filename in filenames:
                if filename in SKIP_FILES:
                    continue
                full_path = Path(dirpath) / filename
                if full_path.is_symlink():
                    continue
                arcname = full_path.relative_to(root).as_posix()
                zf.write(full_path, arcname)
                file_count += 1

    if file_count == 0:
        raise AntOrbitError(f"Directory contains no uploadable files: {root}")
    return buf.getvalue(), file_count


class AntOrbitClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        raw_url = (base_url if base_url is not None else os.environ.get("ANTORBIT_URL", "")).strip()
        raw_key = (api_key if api_key is not None else os.environ.get("ANTORBIT_API_KEY", "")).strip()
        if not raw_url:
            raise AntOrbitError(
                "ANTORBIT_URL is not configured. Set ANTORBIT_URL in your plugin mcp_config.json env."
            )
        if not raw_key:
            raise AntOrbitError(
                "ANTORBIT_API_KEY is not configured. Set ANTORBIT_API_KEY in your plugin mcp_config.json env."
            )
        self.base_url = raw_url.rstrip("/")
        self.api_key = raw_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        url = f"{self.base_url}/api/v1{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise AntOrbitError(f"Failed to reach AntOrbit server ({url}): {exc}") from exc

        try:
            data = resp.json()
        except ValueError:
            data = resp.text

        if resp.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else str(data)
            raise AntOrbitError(f"AntOrbit API error ({resp.status_code}): {detail}")
        return data

    async def publish_site(
        self,
        *,
        directory: str | None = None,
        html: str | None = None,
        slug: str | None = None,
        title: str | None = None,
        description: str = "",
        password: str | None = None,
        clear_password: bool = False,
        ttl_hours: float | None = None,
        allow_submit: bool = False,
        kv_mode: str = "off",
        notify_on_submit: bool = False,
        notify_channel: str = "",
        notify_on_publish: bool = False,
        notify_title: str | None = None,
        notify_body: str | None = None,
        notify_level: str = "active",
        notify_group: str | None = None,
    ) -> dict[str, Any]:
        if bool(directory) == bool(html):
            raise AntOrbitError("Provide exactly one of 'directory' or 'html'.")

        if html is not None:
            payload: dict[str, Any] = {
                "html": html,
                "slug": slug,
                "title": title,
                "description": description,
                "password": password,
                "clear_password": clear_password,
                "ttl_hours": ttl_hours,
                "allow_submit": allow_submit,
                "kv_mode": kv_mode,
                "notify_on_submit": notify_on_submit,
                "notify_channel": notify_channel,
                "notify_on_publish": notify_on_publish,
                "notify_title": notify_title,
                "notify_body": notify_body,
                "notify_level": notify_level,
                "notify_group": notify_group,
            }
            return await self._request("POST", "/sites", json=payload)

        assert directory is not None
        zip_bytes, _ = pack_directory_to_zip(directory)
        form_data: dict[str, str] = {
            "description": description,
            "clear_password": str(clear_password).lower(),
            "allow_submit": str(allow_submit).lower(),
            "kv_mode": kv_mode,
            "notify_on_submit": str(notify_on_submit).lower(),
            "notify_channel": notify_channel,
            "notify_on_publish": str(notify_on_publish).lower(),
            "notify_level": notify_level,
        }
        if slug:
            form_data["slug"] = slug
        if title:
            form_data["title"] = title
        if password:
            form_data["password"] = password
        if ttl_hours is not None:
            form_data["ttl_hours"] = str(ttl_hours)
        if notify_title:
            form_data["notify_title"] = notify_title
        if notify_body:
            form_data["notify_body"] = notify_body
        if notify_group:
            form_data["notify_group"] = notify_group

        return await self._request(
            "POST",
            "/sites",
            data=form_data,
            files={"file": ("site.zip", zip_bytes, "application/zip")},
        )

    async def list_sites(self) -> dict[str, Any]:
        return await self._request("GET", "/sites")

    async def get_site(self, slug: str) -> dict[str, Any]:
        return await self._request("GET", f"/sites/{slug}")

    async def update_site(self, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"/sites/{slug}", json=payload)

    async def delete_site(self, slug: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/sites/{slug}")

    async def get_submissions(
        self, slug: str, *, limit: int = 50, since_id: int | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if since_id is not None:
            params["since_id"] = since_id
        return await self._request("GET", f"/sites/{slug}/submissions", params=params)

    async def kv_list(self, slug: str) -> dict[str, Any]:
        return await self._request("GET", f"/sites/{slug}/kv")

    async def kv_get(self, slug: str, key: str) -> dict[str, Any]:
        return await self._request("GET", f"/sites/{slug}/kv/{key}")

    async def kv_set(self, slug: str, key: str, value: Any) -> dict[str, Any]:
        return await self._request("PUT", f"/sites/{slug}/kv/{key}", json={"value": value})

    async def kv_delete(self, slug: str, key: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/sites/{slug}/kv/{key}")

    async def list_channels(self) -> dict[str, Any]:
        return await self._request("GET", "/channels")

    async def send_notification(
        self,
        *,
        title: str,
        body: str,
        channel: str | None = None,
        url: str | None = None,
        level: str = "active",
        group: str | None = None,
        sound: str | None = None,
        icon: str | None = None,
        site_slug: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": title,
            "body": body,
            "channel": channel,
            "url": url,
            "level": level,
            "group": group,
            "sound": sound,
            "icon": icon,
            "site_slug": site_slug,
        }
        return await self._request("POST", "/notify", json=payload)
