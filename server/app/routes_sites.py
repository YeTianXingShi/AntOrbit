"""Hosted site serving (/s/<slug>/...) and built-in site interactive endpoints."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from .compat import compute_cache_control, guess_media_type, inject_base_href
from .config import Settings
from .db import Database, parse_iso
from .deps import (
    get_app_settings,
    get_db,
    get_notifier,
    get_rate_limiter,
    get_secret_key,
    is_admin_authenticated,
    resolve_public_base_url,
    site_cookie_name,
)
from .notifications import NotificationPayload, NotificationService
from .schemas import KvSetRequest, SubmissionCreateRequest
from .sdk import render_status_page, render_unlock_page
from .security import SlidingWindowRateLimiter, sign_token, verify_password, verify_token
from .storage import StorageError, resolve_site_target, validate_kv_key

logger = logging.getLogger("antorbit.sites")

router = APIRouter(tags=["hosted-sites"])


def _load_active_site(db: Database, slug: str, *, as_json: bool) -> dict[str, Any]:
    site = db.get_site_raw(slug)
    if not site:
        if as_json:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
        return {}
    expires_at = parse_iso(site.get("expires_at"))
    if expires_at and expires_at <= datetime.now(timezone.utc):
        if as_json:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Site has expired.")
        return {"_expired": True, **site}
    return site


def _has_site_access(request: Request, site: dict[str, Any]) -> bool:
    pw_hash = site.get("password_hash")
    if not pw_hash:
        return True
    if is_admin_authenticated(request):
        return True
    cookie_val = request.cookies.get(site_cookie_name(site["slug"]))
    payload = verify_token(cookie_val, get_secret_key(request))
    if not payload:
        return False
    return payload.get("slug") == site["slug"] and payload.get("pw") == pw_hash[:24]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _dispatch_submission_notification(
    notifier: NotificationService,
    site: dict[str, Any],
    payload: Any,
    site_url: str,
) -> None:
    try:
        preview = json.dumps(payload, ensure_ascii=False)
        if len(preview) > 240:
            preview = preview[:237] + "..."
        await notifier.send(
            payload=NotificationPayload(
                title=f"新提交 · {site['title']}",
                body=preview,
                url=site_url,
                level="active",
                group="AntOrbit",
            ),
            channel_name=site.get("notify_channel") or None,
            trigger_type="submission",
            site_slug=site["slug"],
        )
    except Exception as exc:
        logger.warning("Failed to dispatch submission notification for %s: %s", site["slug"], exc)


@router.api_route("/s/{slug}", methods=["GET", "HEAD"])
async def redirect_site_root(slug: str, request: Request) -> RedirectResponse:
    target = f"/s/{slug}/"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/s/{slug}/_unlock")
async def unlock_site(
    slug: str,
    request: Request,
    db: Database = Depends(get_db),
    rate_limiter: SlidingWindowRateLimiter = Depends(get_rate_limiter),
) -> Response:
    if not rate_limiter.allow(f"unlock:{slug}:{_client_ip(request)}"):
        return HTMLResponse(
            render_status_page(429, "请求过于频繁", "请稍后再试。"),
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    site = _load_active_site(db, slug, as_json=False)
    if not site:
        return HTMLResponse(
            render_status_page(404, "站点不存在", f"未找到站点 {slug}。"),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if site.get("_expired"):
        return HTMLResponse(
            render_status_page(410, "站点已过期", f"站点 {slug} 已超过有效期。"),
            status_code=status.HTTP_410_GONE,
        )

    password = ""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        password = str(body.get("password") or "")
    else:
        form = await request.form()
        password = str(form.get("password") or "")

    pw_hash = site.get("password_hash")
    if pw_hash and not verify_password(password, pw_hash):
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"detail": "Invalid password."}, status_code=status.HTTP_401_UNAUTHORIZED)
        return HTMLResponse(
            render_unlock_page(slug, site["title"], error="密码不正确，请重试。"),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = sign_token(
        {"slug": slug, "pw": (pw_hash or "")[:24]},
        get_secret_key(request),
        ttl_seconds=86400 * 7,
    )
    if "application/json" in request.headers.get("accept", ""):
        resp: Response = JSONResponse({"ok": True})
    else:
        resp = RedirectResponse(url=f"/s/{slug}/", status_code=status.HTTP_303_SEE_OTHER)

    resp.set_cookie(
        key=site_cookie_name(slug),
        value=token,
        path=f"/s/{slug}/",
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return resp


# ---- Built-in Site Interactive API (/s/{slug}/_api/...) ----


@router.post("/s/{slug}/_api/submit")
async def site_submit(
    slug: str,
    body: SubmissionCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    notifier: NotificationService = Depends(get_notifier),
    rate_limiter: SlidingWindowRateLimiter = Depends(get_rate_limiter),
) -> dict[str, Any]:
    if not rate_limiter.allow(f"submit:{slug}:{_client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions. Please try again later.",
        )

    site = _load_active_site(db, slug, as_json=True)
    if not _has_site_access(request, site):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Site is password protected.")
    if not site["allow_submit"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Submissions are disabled for this site.")

    raw_bytes = json.dumps(body.payload, ensure_ascii=False).encode("utf-8")
    if len(raw_bytes) > settings.max_submission_kb * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Submission exceeds {settings.max_submission_kb} KB limit.",
        )

    meta = {
        "ip": _client_ip(request),
        "user_agent": (request.headers.get("user-agent") or "")[:200],
    }
    record = db.create_submission(slug, body.payload, meta)

    if site["notify_on_submit"]:
        base_url = resolve_public_base_url(request, settings)
        site_url = f"{base_url}/s/{slug}/"
        background_tasks.add_task(_dispatch_submission_notification, notifier, site, body.payload, site_url)

    return {"id": record["id"], "created_at": record["created_at"]}


@router.get("/s/{slug}/_api/kv")
async def site_kv_list(
    slug: str,
    request: Request,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    site = _load_active_site(db, slug, as_json=True)
    if not _has_site_access(request, site):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Site is password protected.")
    if site["kv_mode"] not in ("read", "readwrite"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="KV access is disabled for this site.")
    return {"items": db.kv_list(slug)}


@router.get("/s/{slug}/_api/kv/{key}")
async def site_kv_get(
    slug: str,
    key: str,
    request: Request,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    try:
        key = validate_kv_key(key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    site = _load_active_site(db, slug, as_json=True)
    if not _has_site_access(request, site):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Site is password protected.")
    if site["kv_mode"] not in ("read", "readwrite"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="KV access is disabled for this site.")

    item = db.kv_get(slug, key)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found.")
    return item


@router.put("/s/{slug}/_api/kv/{key}")
async def site_kv_set(
    slug: str,
    key: str,
    body: KvSetRequest,
    request: Request,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    rate_limiter: SlidingWindowRateLimiter = Depends(get_rate_limiter),
) -> dict[str, Any]:
    if not rate_limiter.allow(f"kv:{slug}:{_client_ip(request)}"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")

    try:
        key = validate_kv_key(key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    site = _load_active_site(db, slug, as_json=True)
    if not _has_site_access(request, site):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Site is password protected.")
    if site["kv_mode"] != "readwrite":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="KV write is disabled for this site.")

    raw_bytes = json.dumps(body.value, ensure_ascii=False).encode("utf-8")
    if len(raw_bytes) > settings.max_kv_value_kb * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"KV value exceeds {settings.max_kv_value_kb} KB limit.",
        )

    if db.kv_get(slug, key) is None and db.kv_count(slug) >= settings.max_kv_keys_per_site:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Site reached maximum KV keys limit ({settings.max_kv_keys_per_site}).",
        )

    return db.kv_set(slug, key, body.value)


@router.delete("/s/{slug}/_api/kv/{key}")
async def site_kv_delete(
    slug: str,
    key: str,
    request: Request,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    try:
        key = validate_kv_key(key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    site = _load_active_site(db, slug, as_json=True)
    if not _has_site_access(request, site):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Site is password protected.")
    if site["kv_mode"] != "readwrite":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="KV write is disabled for this site.")

    deleted = db.kv_delete(slug, key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found.")
    return {"deleted": True, "key": key}


# ---- Static File Serving (/s/{slug}/...) ----


def _apply_site_security_headers(resp: Response, cache_control: str) -> Response:
    resp.headers["Cache-Control"] = cache_control
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


@router.api_route("/s/{slug}/{path:path}", methods=["GET", "HEAD"])
async def serve_site_file(
    slug: str,
    path: str,
    request: Request,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    is_head = request.method == "HEAD"

    site = _load_active_site(db, slug, as_json=False)
    if not site:
        return HTMLResponse(
            "" if is_head else render_status_page(404, "站点不存在", f"未找到站点 {slug}，可能已被删除。"),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if site.get("_expired"):
        return HTMLResponse(
            "" if is_head else render_status_page(410, "站点已过期", f"站点 {slug} 已超过有效期并停止访问。"),
            status_code=status.HTTP_410_GONE,
        )

    if not _has_site_access(request, site):
        return HTMLResponse(
            "" if is_head else render_unlock_page(slug, site["title"]),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    resolved = resolve_site_target(settings.sites_dir, slug, path)

    if resolved.kind == "redirect" and resolved.redirect_to:
        location = resolved.redirect_to
        if request.url.query:
            location = f"{location}?{request.url.query}"
        return RedirectResponse(url=location, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    if resolved.kind == "custom_404" and resolved.path is not None:
        if is_head:
            return _apply_site_security_headers(
                Response(status_code=status.HTTP_404_NOT_FOUND, media_type="text/html; charset=utf-8"),
                "no-cache",
            )
        content = resolved.path.read_bytes()
        return _apply_site_security_headers(
            Response(content=content, status_code=status.HTTP_404_NOT_FOUND, media_type="text/html; charset=utf-8"),
            "no-cache",
        )

    if resolved.kind == "not_found" or resolved.path is None or resolved.rel_path is None:
        return HTMLResponse(
            "" if is_head else render_status_page(404, "文件未找到", f"站点 {slug} 中不存在路径 /{path}。"),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if not is_head and (not path or path.endswith("/") or resolved.path.name == "index.html" or resolved.kind == "spa_fallback"):
        db.increment_view_count(slug)

    # For deep SPA fallback routes, ensure <base href="/s/<slug>/"> is present so relative ./ assets resolve.
    if resolved.kind == "spa_fallback":
        try:
            html_text = resolved.path.read_text(encoding="utf-8")
            patched = inject_base_href(html_text, slug)
            return _apply_site_security_headers(
                Response(
                    content="" if is_head else patched.encode("utf-8"),
                    media_type="text/html; charset=utf-8",
                ),
                "no-cache",
            )
        except UnicodeDecodeError:
            pass

    media_type = guess_media_type(resolved.path)
    cache_control = compute_cache_control(resolved.rel_path)

    if is_head:
        stat_res = resolved.path.stat()
        resp: Response = Response(
            status_code=status.HTTP_200_OK,
            media_type=media_type,
            headers={"Content-Length": str(stat_res.st_size)},
        )
        return _apply_site_security_headers(resp, cache_control)

    resp = FileResponse(resolved.path, media_type=media_type)
    return _apply_site_security_headers(resp, cache_control)
