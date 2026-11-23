"""Notification dispatching service with SQLite delivery logging."""

from __future__ import annotations

from typing import Any

from ..db import Database
from .bark import BarkProvider
from .base import NotificationError, NotificationPayload, NotificationProvider
from .ntfy import NtfyProvider

PROVIDERS: dict[str, NotificationProvider] = {
    "bark": BarkProvider(),
    "ntfy": NtfyProvider(),
}

SUPPORTED_PROVIDERS = tuple(PROVIDERS.keys())


class NotificationService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_provider(self, provider_name: str) -> NotificationProvider:
        provider = PROVIDERS.get(provider_name.lower())
        if not provider:
            raise NotificationError(
                f"Unsupported provider '{provider_name}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
            )
        return provider

    def validate_channel_config(self, provider_name: str, config: dict[str, Any]) -> dict[str, Any]:
        provider = self.get_provider(provider_name)
        return provider.validate_config(config)

    def resolve_channel(self, channel_name: str | None) -> dict[str, Any]:
        if channel_name:
            channel = self.db.get_channel_by_name(channel_name)
            if not channel:
                raise NotificationError(f"Notification channel '{channel_name}' not found.")
            if not channel["enabled"]:
                raise NotificationError(f"Notification channel '{channel_name}' is disabled.")
            return channel
        channel = self.db.get_default_channel()
        if not channel:
            raise NotificationError(
                "No enabled notification channel configured. Please add a Bark or ntfy channel in /admin."
            )
        return channel

    async def send(
        self,
        *,
        payload: NotificationPayload,
        channel_name: str | None = None,
        channel_record: dict[str, Any] | None = None,
        trigger_type: str = "manual",
        site_slug: str | None = None,
    ) -> dict[str, Any]:
        channel = channel_record or self.resolve_channel(channel_name)
        provider = self.get_provider(channel["provider"])
        try:
            await provider.send(channel["config"], payload)
            return self.db.create_notification_log(
                channel_name=channel["name"],
                provider=channel["provider"],
                trigger_type=trigger_type,
                site_slug=site_slug,
                title=payload.title,
                body=payload.body,
                url=payload.url,
                status="success",
            )
        except Exception as exc:
            error_msg = str(exc)
            self.db.create_notification_log(
                channel_name=channel["name"],
                provider=channel["provider"],
                trigger_type=trigger_type,
                site_slug=site_slug,
                title=payload.title,
                body=payload.body,
                url=payload.url,
                status="failed",
                error_message=error_msg,
            )
            raise NotificationError(error_msg) from exc
