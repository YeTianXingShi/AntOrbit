"""Bark (iOS) push notification provider."""

from __future__ import annotations

from typing import Any

import httpx

from .base import NotificationError, NotificationPayload, NotificationProvider

VALID_LEVELS = {"passive", "active", "timeSensitive", "critical"}


class BarkProvider(NotificationProvider):
    name = "bark"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        server_url = str(config.get("server_url") or "https://api.day.app").strip().rstrip("/")
        device_key = str(config.get("device_key") or "").strip().strip("/")
        if not server_url.startswith(("http://", "https://")):
            raise NotificationError("Bark server_url must start with http:// or https://")
        if not device_key:
            raise NotificationError("Bark device_key is required.")
        return {
            "server_url": server_url,
            "device_key": device_key,
            "default_group": str(config.get("default_group") or "AntOrbit").strip(),
            "default_sound": str(config.get("default_sound") or "").strip(),
            "default_icon": str(config.get("default_icon") or "").strip(),
        }

    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> None:
        server_url = str(config.get("server_url") or "https://api.day.app").rstrip("/")
        device_key = str(config.get("device_key") or "").strip("/")
        if not device_key:
            raise NotificationError("Bark channel is missing device_key.")

        endpoint = f"{server_url}/{device_key}"
        level = payload.level if payload.level in VALID_LEVELS else "active"
        group = payload.group or config.get("default_group") or "AntOrbit"
        sound = payload.sound or config.get("default_sound") or ""
        icon = payload.icon or config.get("default_icon") or ""

        body: dict[str, Any] = {
            "title": payload.title,
            "body": payload.body,
            "level": level,
        }
        if group:
            body["group"] = group
        if payload.url:
            body["url"] = payload.url
        if sound:
            body["sound"] = sound
        if icon:
            body["icon"] = icon

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(endpoint, json=body)
        except httpx.HTTPError as exc:
            raise NotificationError(f"Bark request error: {exc}") from exc

        if resp.status_code >= 400:
            raise NotificationError(f"Bark HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError:
            return
        if isinstance(data, dict) and data.get("code") not in (None, 200):
            raise NotificationError(
                f"Bark API error ({data.get('code')}): {data.get('message', 'unknown error')}"
            )
