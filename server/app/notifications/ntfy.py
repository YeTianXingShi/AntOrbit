"""ntfy push notification provider."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from .base import NotificationError, NotificationPayload, NotificationProvider

LEVEL_TO_PRIORITY = {
    "passive": "2",
    "active": "3",
    "timeSensitive": "4",
    "critical": "5",
}


class NtfyProvider(NotificationProvider):
    name = "ntfy"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        server_url = str(config.get("server_url") or "https://ntfy.sh").strip().rstrip("/")
        topic = str(config.get("topic") or "").strip().strip("/")
        if not server_url.startswith(("http://", "https://")):
            raise NotificationError("ntfy server_url must start with http:// or https://")
        if not topic:
            raise NotificationError("ntfy topic is required.")
        return {
            "server_url": server_url,
            "topic": topic,
            "token": str(config.get("token") or "").strip(),
            "username": str(config.get("username") or "").strip(),
            "password": str(config.get("password") or "").strip(),
            "default_tags": str(config.get("default_tags") or "").strip(),
        }

    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> None:
        server_url = str(config.get("server_url") or "https://ntfy.sh").rstrip("/")
        topic = str(config.get("topic") or "").strip("/")
        if not topic:
            raise NotificationError("ntfy channel is missing topic.")

        endpoint = f"{server_url}/{topic}"
        headers: dict[str, str] = {
            "Priority": LEVEL_TO_PRIORITY.get(payload.level, "3"),
        }
        # ntfy supports UTF-8 headers or JSON publishing; JSON publishing to server_url
        # avoids non-ASCII HTTP header encoding issues with Chinese titles!
        json_body: dict[str, Any] = {
            "topic": topic,
            "title": payload.title,
            "message": payload.body,
            "priority": int(LEVEL_TO_PRIORITY.get(payload.level, "3")),
        }
        if payload.url:
            json_body["click"] = payload.url

        tags: list[str] = []
        if payload.group:
            tags.append(payload.group)
        elif config.get("default_tags"):
            tags.extend(
                [t.strip() for t in str(config["default_tags"]).split(",") if t.strip()]
            )
        if tags:
            json_body["tags"] = tags
        if payload.icon:
            json_body["icon"] = payload.icon

        token = str(config.get("token") or "").strip()
        username = str(config.get("username") or "").strip()
        password = str(config.get("password") or "").strip()
        req_headers: dict[str, str] = {}
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            raw = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            req_headers["Authorization"] = f"Basic {raw}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(server_url, json=json_body, headers=req_headers)
        except httpx.HTTPError as exc:
            raise NotificationError(f"ntfy request error: {exc}") from exc

        if resp.status_code >= 400:
            raise NotificationError(f"ntfy HTTP {resp.status_code}: {resp.text[:200]}")
