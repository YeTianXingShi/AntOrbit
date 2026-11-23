"""FastAPI application entry point for AntOrbit server."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from . import __version__
from .config import Settings, get_settings
from .db import Database
from .notifications import NotificationService
from .routes_api import router as api_router
from .routes_sites import router as sites_router
from .sdk import SDK_JS
from .security import SlidingWindowRateLimiter
from .storage import delete_site_files

logger = logging.getLogger("antorbit")


async def _cleanup_expired_loop(db: Database, settings: Settings) -> None:
    while True:
        try:
            expired = db.list_expired_slugs()
            for slug in expired:
                db.delete_site(slug)
                delete_site_files(settings.sites_dir, slug)
                logger.info("Cleaned up expired site: %s", slug)
        except Exception as exc:
            logger.warning("Expired site cleanup error: %s", exc)
        await asyncio.sleep(max(30, settings.cleanup_interval_sec))


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        cfg.sites_dir.mkdir(parents=True, exist_ok=True)
        db = Database(cfg.db_path)
        if cfg.api_key:
            db.ensure_env_api_key(cfg.api_key)
        if cfg.is_default_admin_password:
            logger.warning(
                "ANTORBIT_ADMIN_PASSWORD is using the default value ('antorbit'). "
                "Please set a strong password in production!"
            )

        app.state.settings = cfg
        app.state.db = db
        app.state.secret_key = cfg.resolve_secret_key()
        app.state.notifier = NotificationService(db)
        app.state.rate_limiter = SlidingWindowRateLimiter(
            max_requests=cfg.rate_limit_per_min,
            window_seconds=60,
        )

        cleanup_task = asyncio.create_task(_cleanup_expired_loop(db, cfg))
        try:
            yield
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title="AntOrbit Server",
        version=__version__,
        lifespan=lifespan,
    )

    app.include_router(api_router)
    app.include_router(sites_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/_antorbit/sdk.js")
    async def serve_sdk() -> Response:
        return Response(
            content=SDK_JS,
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": "public, max-age=300"},
        )

    @app.get("/")
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/admin/")

    def _serve_admin_asset(rel_path: str) -> Response:
        dist_dir = cfg.resolve_web_dist_dir()
        if not dist_dir:
            return HTMLResponse(
                "<h1>AntOrbit Server is running</h1>"
                "<p>Admin UI build not found. Run <code>npm run build</code> in <code>web/</code> or use the Docker image.</p>",
                status_code=200,
            )
        dist_resolved = dist_dir.resolve()
        if rel_path:
            candidate = (dist_resolved / rel_path.lstrip("/")).resolve()
            try:
                candidate.relative_to(dist_resolved)
                if candidate.is_file():
                    return FileResponse(candidate)
            except ValueError:
                pass
        return FileResponse(dist_resolved / "index.html")

    @app.get("/admin")
    async def admin_redirect() -> RedirectResponse:
        return RedirectResponse(url="/admin/")

    @app.get("/admin/{path:path}")
    async def admin_spa(path: str) -> Response:
        return _serve_admin_asset(path)

    return app


app = create_app()
