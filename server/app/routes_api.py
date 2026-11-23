"""Management REST API (/api/v1/...) for MCP clients and Admin UI."""

from __future__ import annotations

import hmac
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from . import __version__
from .config import Settings
from .db import Database
from .deps import (
    ADMIN_COOKIE_NAME,
    AuthPrincipal,
    attach_site_url,
    get_app_settings,
    get_db,
    get_notifier,
    get_secret_key,
    is_admin_authenticated,
    require_admin,
    require_api_or_admin,
    resolve_public_base_url,
)
from .notifications import NotificationError, NotificationPayload, NotificationService
from .schemas import (
    AdminLoginRequest,
    ApiKeyCreateRequest,
    ChannelUpsertRequest,
    KvSetRequest,
    NotifyRequest,
    SitePublishJsonRequest,
    SiteUpdateRequest,
)
from .security import generate_api_key, hash_password, sign_token
from .storage import (
    StorageError,
    delete_site_files,
    extract_zip_site,
    generate_slug,
    validate_kv_key,
    validate_slug,
    write_html_site,
)

router = APIRouter(prefix="/api/v1", tags=["api"])


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _compute_expires_at(ttl_hours: float | None) -> str | None:
    if ttl_hours is None or ttl_hours <= 0:
        return None
    dt = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    return dt.replace(microsecond=0).isoformat()


# ---- Admin Auth ----


@router.post("/admin/login")
async def admin_login(
    body: AdminLoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin password.")

    token = sign_token({"role": "admin"}, get_secret_key(request), ttl_seconds=86400 * 7)
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        path="/",
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return {"authenticated": True}


@router.post("/admin/logout")
async def admin_logout(response: Response) -> dict[str, Any]:
    response.delete_cookie(key=ADMIN_COOKIE_NAME, path="/")
    return {"authenticated": False}


@router.get("/admin/me")
async def admin_me(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    return {
        "authenticated": is_admin_authenticated(request),
        "version": __version__,
        "public_url": resolve_public_base_url(request, settings),
        "default_password_warning": settings.is_default_admin_password,
    }


# ---- Sites ----


@router.post("/sites", status_code=status.HTTP_201_CREATED)
async def publish_site(
    request: Request,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    notifier: NotificationService = Depends(get_notifier),
) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    zip_bytes: bytes | None = None
    html_content: str | None = None

    if "application/json" in content_type:
        raw = await request.json()
        req = SitePublishJsonRequest.model_validate(raw)
        html_content = req.html
        slug_input = req.slug
        title = req.title
        description = req.description
        password = req.password
        clear_password = req.clear_password
        ttl_hours = req.ttl_hours
        allow_submit = req.allow_submit
        kv_mode = req.kv_mode
        notify_on_submit = req.notify_on_submit
        notify_channel = req.notify_channel
        notify_on_publish = req.notify_on_publish
        notify_title = req.notify_title
        notify_body = req.notify_body
        notify_level = req.notify_level
        notify_group = req.notify_group
    else:
        form = await request.form()
        upload = form.get("file")
        if upload is not None and hasattr(upload, "read"):
            zip_bytes = await upload.read()
        html_field = form.get("html")
        if html_field is not None and str(html_field).strip():
            html_content = str(html_field)

        slug_input = str(form.get("slug") or "").strip() or None
        title = str(form.get("title") or "").strip() or None
        description = str(form.get("description") or "").strip()
        pw_raw = form.get("password")
        password = str(pw_raw) if pw_raw is not None and str(pw_raw) != "" else None
        clear_password = _parse_bool(form.get("clear_password"), False)
        ttl_raw = form.get("ttl_hours")
        ttl_hours = float(ttl_raw) if ttl_raw not in (None, "") else None
        allow_submit = _parse_bool(form.get("allow_submit"), False)
        kv_mode = str(form.get("kv_mode") or "off").strip().lower()
        if kv_mode not in ("off", "read", "readwrite"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid kv_mode.")
        notify_on_submit = _parse_bool(form.get("notify_on_submit"), False)
        notify_channel = str(form.get("notify_channel") or "").strip()
        notify_on_publish = _parse_bool(form.get("notify_on_publish"), False)
        notify_title = str(form.get("notify_title") or "").strip() or None
        notify_body = str(form.get("notify_body") or "").strip() or None
        notify_level = str(form.get("notify_level") or "active").strip()
        notify_group = str(form.get("notify_group") or "").strip() or None

    if zip_bytes is None and html_content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a ZIP 'file' or inline 'html' content.",
        )

    try:
        slug = validate_slug(slug_input) if slug_input else generate_slug()
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if zip_bytes is not None:
        max_upload_bytes = settings.max_upload_mb * 1024 * 1024
        if len(zip_bytes) > max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload exceeds {settings.max_upload_mb} MB limit.",
            )
        try:
            size_bytes, file_count = extract_zip_site(
                settings.sites_dir,
                slug,
                zip_bytes,
                max_files=settings.max_site_files,
                max_uncompressed_bytes=settings.max_uncompressed_mb * 1024 * 1024,
            )
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    else:
        assert html_content is not None
        size_bytes, file_count = write_html_site(settings.sites_dir, slug, html_content)

    # Password handling on create vs overwrite:
    # - password provided -> set new hash
    # - clear_password=True -> set None
    # - neither -> preserve existing password if overwriting, else None
    preserve_password = False
    password_hash: str | None = None
    if password:
        password_hash = hash_password(password)
    elif clear_password:
        password_hash = None
    else:
        preserve_password = True

    expires_at = _compute_expires_at(ttl_hours)
    site, updated = db.upsert_site(
        slug=slug,
        title=title or slug,
        description=description,
        password_hash=password_hash,
        preserve_password=preserve_password,
        allow_submit=allow_submit,
        kv_mode=kv_mode,
        notify_on_submit=notify_on_submit,
        notify_channel=notify_channel,
        expires_at=expires_at,
        size_bytes=size_bytes,
        file_count=file_count,
    )

    base_url = resolve_public_base_url(request, settings)
    site_with_url = attach_site_url(site, base_url)
    result: dict[str, Any] = {
        "site": site_with_url,
        "updated": updated,
        "notification": None,
    }

    if notify_on_publish:
        action_label = "已更新" if updated else "已发布"
        p_title = notify_title or f"{site['title']} {action_label}"
        p_body = notify_body or (
            site["description"] or f"点击查看在线页面：{site_with_url['url']}"
        )
        try:
            log = await notifier.send(
                payload=NotificationPayload(
                    title=p_title,
                    body=p_body,
                    url=site_with_url["url"],
                    level=notify_level,
                    group=notify_group or "AntOrbit",
                ),
                channel_name=notify_channel or None,
                trigger_type="publish",
                site_slug=slug,
            )
            result["notification"] = {"status": "sent", "log": log}
        except NotificationError as exc:
            result["notification"] = {"status": "failed", "error": str(exc)}

    return result


@router.get("/sites")
async def list_sites(
    request: Request,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    base_url = resolve_public_base_url(request, settings)
    sites = [attach_site_url(s, base_url) for s in db.list_sites()]
    return {"sites": sites}


@router.get("/sites/{slug}")
async def get_site(
    slug: str,
    request: Request,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    site = db.get_site(slug)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    base_url = resolve_public_base_url(request, settings)
    return {"site": attach_site_url(site, base_url)}


@router.patch("/sites/{slug}")
async def update_site(
    slug: str,
    body: SiteUpdateRequest,
    request: Request,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if body.title is not None:
        fields["title"] = body.title.strip() or slug
    if body.description is not None:
        fields["description"] = body.description
    if body.clear_password:
        fields["password_hash"] = None
    elif body.password is not None and body.password != "":
        fields["password_hash"] = hash_password(body.password)
    if body.ttl_hours is not None:
        fields["expires_at"] = _compute_expires_at(body.ttl_hours)
    if body.allow_submit is not None:
        fields["allow_submit"] = int(body.allow_submit)
    if body.kv_mode is not None:
        fields["kv_mode"] = body.kv_mode
    if body.notify_on_submit is not None:
        fields["notify_on_submit"] = int(body.notify_on_submit)
    if body.notify_channel is not None:
        fields["notify_channel"] = body.notify_channel.strip()

    updated = db.update_site_settings(slug, fields)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    base_url = resolve_public_base_url(request, settings)
    return {"site": attach_site_url(updated, base_url)}


@router.delete("/sites/{slug}")
async def delete_site(
    slug: str,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    deleted = db.delete_site(slug)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    delete_site_files(settings.sites_dir, slug)
    return {"deleted": True, "slug": slug}


# ---- Submissions ----


@router.get("/sites/{slug}/submissions")
async def list_submissions(
    slug: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    since_id: int | None = Query(default=None, ge=0),
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    if not db.get_site_raw(slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    items = db.list_submissions(slug, limit=limit, offset=offset, since_id=since_id)
    return {"submissions": items}


@router.delete("/sites/{slug}/submissions/{sub_id}")
async def delete_submission(
    slug: str,
    sub_id: int,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    deleted = db.delete_submission(slug, sub_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    return {"deleted": True, "id": sub_id}


@router.delete("/sites/{slug}/submissions")
async def clear_submissions(
    slug: str,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    if not db.get_site_raw(slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    count = db.clear_submissions(slug)
    return {"deleted_count": count}


# ---- KV Management ----


@router.get("/sites/{slug}/kv")
async def admin_kv_list(
    slug: str,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    if not db.get_site_raw(slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    return {"items": db.kv_list(slug)}


@router.get("/sites/{slug}/kv/{key}")
async def admin_kv_get(
    slug: str,
    key: str,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    try:
        key = validate_kv_key(key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not db.get_site_raw(slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    item = db.kv_get(slug, key)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found.")
    return item


@router.put("/sites/{slug}/kv/{key}")
async def admin_kv_set(
    slug: str,
    key: str,
    body: KvSetRequest,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    try:
        key = validate_kv_key(key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not db.get_site_raw(slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")

    raw_bytes = json.dumps(body.value, ensure_ascii=False).encode("utf-8")
    if len(raw_bytes) > settings.max_kv_value_kb * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"KV value exceeds {settings.max_kv_value_kb} KB limit.",
        )
    return db.kv_set(slug, key, body.value)


@router.delete("/sites/{slug}/kv/{key}")
async def admin_kv_delete(
    slug: str,
    key: str,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    try:
        key = validate_kv_key(key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    deleted = db.kv_delete(slug, key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found.")
    return {"deleted": True, "key": key}


# ---- Notification Channels & Push ----


@router.get("/channels")
async def list_channels(
    principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    return {"channels": db.list_channels(include_config=(principal.kind == "admin"))}


@router.post("/channels", status_code=status.HTTP_201_CREATED)
async def create_channel(
    body: ChannelUpsertRequest,
    _principal: AuthPrincipal = Depends(require_admin),
    db: Database = Depends(get_db),
    notifier: NotificationService = Depends(get_notifier),
) -> dict[str, Any]:
    try:
        clean_config = notifier.validate_channel_config(body.provider, body.config)
        channel = db.create_channel(
            name=body.name.strip(),
            provider=body.provider,
            config=clean_config,
            is_default=body.is_default,
            enabled=body.enabled,
        )
    except NotificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel name '{body.name.strip()}' already exists.",
        ) from exc
    return {"channel": channel}


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: str,
    body: ChannelUpsertRequest,
    _principal: AuthPrincipal = Depends(require_admin),
    db: Database = Depends(get_db),
    notifier: NotificationService = Depends(get_notifier),
) -> dict[str, Any]:
    try:
        clean_config = notifier.validate_channel_config(body.provider, body.config)
        channel = db.update_channel(
            channel_id,
            name=body.name.strip(),
            provider=body.provider,
            config=clean_config,
            is_default=body.is_default,
            enabled=body.enabled,
        )
    except NotificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel name '{body.name.strip()}' already exists.",
        ) from exc
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found.")
    return {"channel": channel}


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str,
    _principal: AuthPrincipal = Depends(require_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    if not db.delete_channel(channel_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found.")
    return {"deleted": True, "id": channel_id}


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: str,
    request: Request,
    _principal: AuthPrincipal = Depends(require_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    notifier: NotificationService = Depends(get_notifier),
) -> dict[str, Any]:
    channel = db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found.")
    base_url = resolve_public_base_url(request, settings)
    try:
        log = await notifier.send(
            payload=NotificationPayload(
                title="AntOrbit 测试推送",
                body=f"渠道「{channel['name']}」({channel['provider']}) 连接正常！",
                url=f"{base_url}/admin/",
                level="active",
                group="AntOrbit",
            ),
            channel_record=channel,
            trigger_type="test",
        )
    except NotificationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"ok": True, "log": log}


@router.post("/notify")
async def send_notification(
    body: NotifyRequest,
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    notifier: NotificationService = Depends(get_notifier),
) -> dict[str, Any]:
    try:
        log = await notifier.send(
            payload=NotificationPayload(
                title=body.title,
                body=body.body,
                url=body.url,
                level=body.level,
                group=body.group,
                sound=body.sound,
                icon=body.icon,
            ),
            channel_name=body.channel,
            trigger_type="manual",
            site_slug=body.site_slug,
        )
    except NotificationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"ok": True, "log": log}


@router.get("/notifications/logs")
async def list_notification_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _principal: AuthPrincipal = Depends(require_api_or_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    return {"logs": db.list_notification_logs(limit=limit, offset=offset)}


# ---- API Keys (Admin only) ----


@router.get("/api-keys")
async def list_api_keys(
    _principal: AuthPrincipal = Depends(require_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    return {"api_keys": db.list_api_keys()}


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    _principal: AuthPrincipal = Depends(require_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    raw_key = generate_api_key()
    record = db.create_api_key(body.name.strip(), raw_key)
    return {"api_key": record, "raw_key": raw_key}


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    _principal: AuthPrincipal = Depends(require_admin),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    if not db.delete_api_key(key_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or managed via ANTORBIT_API_KEY env var.",
        )
    return {"deleted": True, "id": key_id}
