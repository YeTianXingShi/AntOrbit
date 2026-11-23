"""Base types for notification push providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class NotificationError(RuntimeError):
    """Raised when sending or validating a notification fails."""


@dataclass(slots=True)
class NotificationPayload:
    title: str
    body: str
    url: str | None = None
    level: str = "active"  # passive | active | timeSensitive | critical
    group: str | None = None
    sound: str | None = None
    icon: str | None = None


class NotificationProvider(ABC):
    name: str

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize provider-specific channel configuration."""

    @abstractmethod
    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> None:
        """Send the notification via this provider."""
