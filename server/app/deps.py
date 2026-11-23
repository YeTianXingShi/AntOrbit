"""FastAPI dependencies, app state accessors, and auth helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from .config import Settings
from .db import Database
from .notifications import NotificationService
from .security import SlidingWindowRateLimiter, verify_token

ADMIN_COOKIE_NAME = "antorbit_admin"


@dataclass
class AuthPrincipal:
    kind: str  # "admin" | "api_key"
    name: str


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_notifier(request: Request) -> NotificationService:
    return request.app.state.notifier


def get_rate_limiter(request: Request) -> SlidingWindowRateLimiter:
    return request.app.state.rate_limiter


def get_secret_key(request: Request) -> str:
    return request.app.state.secret_key


def resolve_public_base_url(request: Request, settings: Settings) -> str:
    if settings.public_url:
        return settings.public_url.rstrip("/")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def is_admin_authenticated(request: Request) -> bool:
    cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    payload = verify_token(cookie, get_secret_key(request))
    return bool(payload and payload.get("role") == "admin")


def require_admin(request: Request) -> AuthPrincipal:
    if not is_admin_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )
    return AuthPrincipal(kind="admin", name="admin")


def require_api_or_admin(
    request: Request,
    db: Database = Depends(get_db),
) -> AuthPrincipal:
    if is_admin_authenticated(request):
        return AuthPrincipal(kind="admin", name="admin")

    auth_header = request.headers.get("authorization") or ""
    raw_key = ""
    if auth_header.lower().startswith("bearer "):
        raw_key = auth_header[7:].strip()
    elif request.headers.get("x-api-key"):
        raw_key = request.headers["x-api-key"].strip()

    if raw_key:
        record = db.verify_api_key(raw_key)
        if record:
            return AuthPrincipal(kind="api_key", name=record["name"])

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid API key or admin session required.",
    )


def site_cookie_name(slug: str) -> str:
    return f"antorbit_site_{slug}"


def attach_site_url(site: dict[str, Any], base_url: str) -> dict[str, Any]:
    return {
        **site,
        "url": f"{base_url}/s/{site['slug']}/",
    }
