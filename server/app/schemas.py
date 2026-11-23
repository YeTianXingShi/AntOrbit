"""Pydantic request and response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    password: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SiteUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    password: str | None = None
    clear_password: bool = False
    ttl_hours: float | None = Field(default=None, ge=0)
    allow_submit: bool | None = None
    kv_mode: Literal["off", "read", "readwrite"] | None = None
    notify_on_submit: bool | None = None
    notify_channel: str | None = None


class SitePublishJsonRequest(BaseModel):
    html: str = Field(min_length=1)
    slug: str | None = None
    title: str | None = None
    description: str = ""
    password: str | None = None
    clear_password: bool = False
    ttl_hours: float | None = Field(default=None, ge=0)
    allow_submit: bool = False
    kv_mode: Literal["off", "read", "readwrite"] = "off"
    notify_on_submit: bool = False
    notify_channel: str = ""
    notify_on_publish: bool = False
    notify_title: str | None = None
    notify_body: str | None = None
    notify_level: Literal["passive", "active", "timeSensitive", "critical"] = "active"
    notify_group: str | None = None


class SubmissionCreateRequest(BaseModel):
    payload: Any


class KvSetRequest(BaseModel):
    value: Any


class ChannelUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    provider: Literal["bark", "ntfy"]
    config: dict[str, Any]
    is_default: bool = False
    enabled: bool = True


class NotifyRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    channel: str | None = None
    url: str | None = None
    level: Literal["passive", "active", "timeSensitive", "critical"] = "active"
    group: str | None = None
    sound: str | None = None
    icon: str | None = None
    site_slug: str | None = None
