"""End-to-end tests for AntOrbit FastAPI server."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path / "data",
        admin_password="test-admin-password",
        public_url="https://orbit.example.com",
        api_key="ao_bootstrap_test_key",
        cleanup_interval_sec=3600,
    )
    app = create_app(settings)
    with TestClient(app) as tc:
        yield tc


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer ao_bootstrap_test_key"}


def _make_zip(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_health_and_sdk(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    sdk = client.get("/_antorbit/sdk.js")
    assert sdk.status_code == 200
    assert "window.AntOrbit" in sdk.text or "global.AntOrbit = AntOrbit" in sdk.text


def test_admin_auth_and_api_keys(client: TestClient) -> None:
    # Unauthenticated fails
    assert client.get("/api/v1/api-keys").status_code == 401
    assert client.post("/api/v1/admin/login", json={"password": "wrong"}).status_code == 401

    # Login succeeds
    r = client.post("/api/v1/admin/login", json={"password": "test-admin-password"})
    assert r.status_code == 200
    assert client.get("/api/v1/admin/me").json()["authenticated"] is True

    # Create API key
    created = client.post("/api/v1/api-keys", json={"name": "my-laptop"})
    assert created.status_code == 201
    raw_key = created.json()["raw_key"]
    key_id = created.json()["api_key"]["id"]
    assert raw_key.startswith("ao_")

    # Logout admin and verify newly created API key works
    client.post("/api/v1/admin/logout")
    assert client.get("/api/v1/sites", headers={"Authorization": f"Bearer {raw_key}"}).status_code == 200

    # Login again and delete key
    client.post("/api/v1/admin/login", json={"password": "test-admin-password"})
    assert client.delete(f"/api/v1/api-keys/{key_id}").status_code == 200


def test_publish_html_zip_and_overwrite_preserves_data(client: TestClient) -> None:
    # Publish HTML with interactive enabled
    r = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        json={
            "slug": "demo-app",
            "title": "Demo App v1",
            "html": "<html><body><h1>v1</h1></body></html>",
            "allow_submit": True,
            "kv_mode": "readwrite",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["updated"] is False
    assert data["site"]["url"] == "https://orbit.example.com/s/demo-app/"

    # Serve static page
    page = client.get("/s/demo-app/")
    assert page.status_code == 200
    assert "<h1>v1</h1>" in page.text

    # Submit form + write KV via hosted site API
    sub = client.post("/s/demo-app/_api/submit", json={"payload": {"approved": True, "note": "LGTM"}})
    assert sub.status_code == 200

    kv = client.put("/s/demo-app/_api/kv/theme", json={"value": {"dark": True}})
    assert kv.status_code == 200

    # Overwrite with a ZIP bundle
    bundle = _make_zip(
        {
            "dist/index.html": "<html><body><h1>v2</h1><script src='./app.js'></script></body></html>",
            "dist/app.js": "console.log('v2');",
        }
    )
    r2 = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        data={
            "slug": "demo-app",
            "title": "Demo App v2",
            "allow_submit": "true",
            "kv_mode": "readwrite",
        },
        files={"file": ("site.zip", bundle, "application/zip")},
    )
    assert r2.status_code == 201
    assert r2.json()["updated"] is True

    # Verify hoisted dist/index.html and app.js
    assert "<h1>v2</h1>" in client.get("/s/demo-app/").text
    assert "console.log('v2');" in client.get("/s/demo-app/app.js").text

    # Verify submissions & KV were preserved across overwrite
    subs = client.get("/api/v1/sites/demo-app/submissions", headers=_auth_headers()).json()["submissions"]
    assert len(subs) == 1
    assert subs[0]["payload"]["approved"] is True

    kv_val = client.get("/s/demo-app/_api/kv/theme").json()["value"]
    assert kv_val == {"dark": True}


def test_zip_slip_rejected(client: TestClient) -> None:
    malicious = _make_zip({"../evil.txt": "pwned"})
    r = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        data={"slug": "bad-zip"},
        files={"file": ("evil.zip", malicious, "application/zip")},
    )
    assert r.status_code == 400
    assert "unsafe path" in r.json()["detail"].lower()


def test_password_protection_and_cookie_isolation(client: TestClient) -> None:
    # Create two password-protected sites
    for slug, pw in [("site-a", "secret-a"), ("site-b", "secret-b")]:
        r = client.post(
            "/api/v1/sites",
            headers=_auth_headers(),
            json={
                "slug": slug,
                "title": slug,
                "html": f"<h1>{slug}</h1>",
                "password": pw,
                "allow_submit": True,
                "kv_mode": "readwrite",
            },
        )
        assert r.status_code == 201

    # Both locked initially
    assert client.get("/s/site-a/").status_code == 401
    assert client.post("/s/site-a/_api/submit", json={"payload": {"x": 1}}).status_code == 401

    # Unlock site-a
    unlock = client.post(
        "/s/site-a/_unlock",
        json={"password": "secret-a"},
        headers={"Accept": "application/json"},
    )
    assert unlock.status_code == 200

    # site-a page + interactive API now accessible
    assert client.get("/s/site-a/").status_code == 200
    assert client.post("/s/site-a/_api/submit", json={"payload": {"x": 1}}).status_code == 200

    # site-b remains locked!
    assert client.get("/s/site-b/").status_code == 401
    assert client.post("/s/site-b/_api/submit", json={"payload": {"x": 1}}).status_code == 401


def test_ttl_expiration(client: TestClient) -> None:
    client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        json={"slug": "ephemeral", "html": "<h1>temp</h1>", "ttl_hours": 1},
    )
    assert client.get("/s/ephemeral/").status_code == 200

    # Force expires_at into the past directly in SQLite
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    db = client.app.state.db
    db.update_site_settings("ephemeral", {"expires_at": past})

    assert client.get("/s/ephemeral/").status_code == 410
    assert client.post("/s/ephemeral/_api/submit", json={"payload": {}}).status_code == 410


@respx.mock
def test_bark_and_ntfy_notifications(client: TestClient) -> None:
    bark_route = respx.post("https://api.day.app/test-device-key").mock(
        return_value=httpx.Response(200, json={"code": 200, "message": "success"})
    )
    ntfy_route = respx.post("https://ntfy.sh").mock(
        return_value=httpx.Response(200, json={"id": "msg1"})
    )

    # Admin login to configure channels
    client.post("/api/v1/admin/login", json={"password": "test-admin-password"})

    r1 = client.post(
        "/api/v1/channels",
        json={
            "name": "my-iphone",
            "provider": "bark",
            "config": {"server_url": "https://api.day.app", "device_key": "test-device-key"},
            "is_default": True,
            "enabled": True,
        },
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/v1/channels",
        json={
            "name": "ops-ntfy",
            "provider": "ntfy",
            "config": {"server_url": "https://ntfy.sh", "topic": "antorbit-alerts", "token": "tk_123"},
            "is_default": False,
            "enabled": True,
        },
    )
    assert r2.status_code == 201

    client.post("/api/v1/admin/logout")

    # API key listing channels hides secrets
    chs = client.get("/api/v1/channels", headers=_auth_headers()).json()["channels"]
    assert len(chs) == 2
    assert "config" not in chs[0]

    # Standalone notification to default (Bark)
    n1 = client.post(
        "/api/v1/notify",
        headers=_auth_headers(),
        json={
            "title": "Build Done",
            "body": "All tests passed!",
            "url": "https://orbit.example.com/s/demo/",
            "level": "timeSensitive",
        },
    )
    assert n1.status_code == 200
    assert bark_route.called

    # Publish site with notify_on_publish + notify_on_submit targeting ntfy
    pub = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        json={
            "slug": "review-plan",
            "title": "Architecture Plan",
            "html": "<h1>Review me</h1>",
            "allow_submit": True,
            "notify_on_submit": True,
            "notify_channel": "ops-ntfy",
            "notify_on_publish": True,
        },
    )
    assert pub.status_code == 201
    assert pub.json()["notification"]["status"] == "sent"
    assert ntfy_route.call_count == 1

    # Submitting form triggers background notification to ntfy
    sub = client.post("/s/review-plan/_api/submit", json={"payload": {"decision": "approve"}})
    assert sub.status_code == 200
    assert ntfy_route.call_count == 2

    # Logs recorded all 3 deliveries
    logs = client.get("/api/v1/notifications/logs", headers=_auth_headers()).json()["logs"]
    assert len(logs) == 3
    assert all(item["status"] == "success" for item in logs)


def test_builtin_ui_css_and_head_requests(client: TestClient) -> None:
    css = client.get("/_antorbit/ui.css")
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert "--ao-primary:" in css.text
    assert ".ao-card" in css.text

    css_head = client.head("/_antorbit/ui.css")
    assert css_head.status_code == 200
    assert css_head.text == ""

    sdk_head = client.head("/_antorbit/sdk.js")
    assert sdk_head.status_code == 200
    assert sdk_head.text == ""


def test_path_rewriting_and_js_warning(client: TestClient) -> None:
    bundle = _make_zip(
        {
            "index.html": (
                "<!doctype html><html><head>"
                '<link rel="stylesheet" href="/_antorbit/ui.css">'
                '<link rel="stylesheet" href="/styles/app.css">'
                '<script src="/_antorbit/sdk.js"></script>'
                '<script type="module" src="/assets/index-D9xK2a1b.js"></script>'
                '<script src="//cdn.example.com/lib.js"></script>'
                "<style>body{background:url(/images/bg.png);}</style>"
                "</head><body>"
                '<img srcset="/images/a.png 1x, /images/b.png 2x">'
                "</body></html>"
            ),
            "styles/app.css": '@import "/styles/reset.css"; .hero { background: url("/images/hero.webp"); }',
            "assets/index-D9xK2a1b.js": 'console.log("loaded"); fetch("/data/info.json");',
        }
    )
    r = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        data={"slug": "rewrite-demo", "allow_submit": "true"},
        files={"file": ("site.zip", bundle, "application/zip")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["rewrites"]["enabled"] is True
    assert body["rewrites"]["html_files"] == 1
    assert body["rewrites"]["css_files"] == 1
    assert body["rewrites"]["urls_rewritten"] >= 6
    # JS root path should produce a warning, not modify JS
    assert any("JS files" in w for w in body["warnings"])

    html = client.get("/s/rewrite-demo/").text
    assert 'href="/_antorbit/ui.css"' in html
    assert 'src="/_antorbit/sdk.js"' in html
    assert 'src="//cdn.example.com/lib.js"' in html
    assert 'href="/s/rewrite-demo/styles/app.css"' in html
    assert 'src="/s/rewrite-demo/assets/index-D9xK2a1b.js"' in html
    assert "url(/s/rewrite-demo/images/bg.png)" in html
    assert 'srcset="/s/rewrite-demo/images/a.png 1x, /s/rewrite-demo/images/b.png 2x"' in html

    css = client.get("/s/rewrite-demo/styles/app.css").text
    assert '@import "/s/rewrite-demo/styles/reset.css"' in css
    assert 'url("/s/rewrite-demo/images/hero.webp")' in css

    js = client.get("/s/rewrite-demo/assets/index-D9xK2a1b.js").text
    assert 'fetch("/data/info.json")' in js

    # Disabling rewrite_paths preserves raw root paths and emits a warning
    r_raw = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        json={
            "slug": "no-rewrite",
            "html": '<html><head><link rel="stylesheet" href="/style.css"></head></html>',
            "rewrite_paths": False,
        },
    )
    assert r_raw.status_code == 201
    assert r_raw.json()["rewrites"]["urls_rewritten"] == 0
    assert any("rewrite_paths=false" in w for w in r_raw.json()["warnings"])
    assert 'href="/style.css"' in client.get("/s/no-rewrite/").text


def test_spa_deep_route_injects_base_and_preserves_existing_base(client: TestClient) -> None:
    r = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        json={
            "slug": "spa-app",
            "html": '<!doctype html><html><head><title>SPA</title><script type="module" src="./assets/app.js"></script></head><body>OK</body></html>',
        },
    )
    assert r.status_code == 201

    # Root page does not need injected <base>
    root_resp = client.get("/s/spa-app/")
    assert root_resp.status_code == 200
    assert "<base " not in root_resp.text

    # Deep extensionless route falls back to index.html and injects <base href="/s/spa-app/">
    deep = client.get("/s/spa-app/users/42")
    assert deep.status_code == 200
    assert '<base href="/s/spa-app/">' in deep.text
    assert deep.headers["cache-control"] == "no-cache"

    # Missing asset with extension returns 404 (not SPA index.html)
    assert client.get("/s/spa-app/missing.js").status_code == 404


def test_multifile_trailing_slash_clean_url_custom_404_and_single_html(client: TestClient) -> None:
    mpa_zip = _make_zip(
        {
            "index.html": "<h1>Home</h1>",
            "about.html": "<h1>About Us</h1>",
            "docs/index.html": "<h1>Docs</h1>",
            "404.html": "<h1>Custom Missing Page</h1>",
        }
    )
    r = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        data={"slug": "mpa-site"},
        files={"file": ("site.zip", mpa_zip, "application/zip")},
    )
    assert r.status_code == 201

    # Subdirectory without trailing slash redirects 307 with query string preserved
    redir = client.get("/s/mpa-site/docs?tab=api", follow_redirects=False)
    assert redir.status_code == 307
    assert redir.headers["location"] == "/s/mpa-site/docs/?tab=api"

    # Subdirectory with trailing slash serves docs/index.html
    assert "<h1>Docs</h1>" in client.get("/s/mpa-site/docs/").text

    # Clean URL resolves about -> about.html
    about = client.get("/s/mpa-site/about")
    assert about.status_code == 200
    assert "<h1>About Us</h1>" in about.text

    # Custom 404.html returned with status 404 for unknown page route
    missing = client.get("/s/mpa-site/nonexistent")
    assert missing.status_code == 404
    assert "<h1>Custom Missing Page</h1>" in missing.text

    # Single-HTML directory without index.html auto-serves the sole HTML file
    sole_zip = _make_zip({"report.html": "<h1>Quarterly Report</h1>", "data.json": '{"ok":true}'})
    r_sole = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        data={"slug": "sole-html"},
        files={"file": ("site.zip", sole_zip, "application/zip")},
    )
    assert r_sole.status_code == 201
    assert any("report.html" in w for w in r_sole.json()["warnings"])
    assert "<h1>Quarterly Report</h1>" in client.get("/s/sole-html/").text


def test_modern_mime_cache_control_head_and_diagnostics(client: TestClient) -> None:
    assets_zip = _make_zip(
        {
            "index.html": "<!doctype html><html><body>" + ("hello " * 200) + "</body></html>",
            "assets/index-D9xK2a1b.js": "export const x = 1;",
            "assets/my-module-file.mjs": "export const y = 2;",
            "assets/core.wasm": b"\x00asm\x01\x00\x00\x00",
            "site.webmanifest": '{"name":"Test"}',
        }
    )
    r = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        data={"slug": "modern-web", "allow_submit": "true"},
        files={"file": ("site.zip", assets_zip, "application/zip")},
    )
    assert r.status_code == 201
    # Missing SDK warning when allow_submit=True
    assert any("sdk.js" in w for w in r.json()["warnings"])

    # HEAD does not increment view_count
    head_resp = client.head("/s/modern-web/")
    assert head_resp.status_code == 200
    assert head_resp.text == ""
    assert head_resp.headers["cache-control"] == "no-cache"
    assert head_resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    site_meta = client.get("/api/v1/sites/modern-web", headers=_auth_headers()).json()["site"]
    assert site_meta["view_count"] == 0

    # GET increments view_count
    get_resp = client.get("/s/modern-web/")
    assert get_resp.status_code == 200
    assert "text/html" in get_resp.headers["content-type"]
    site_meta2 = client.get("/api/v1/sites/modern-web", headers=_auth_headers()).json()["site"]
    assert site_meta2["view_count"] == 1

    # Modern MIME & layered Cache-Control
    hashed_js = client.get("/s/modern-web/assets/index-D9xK2a1b.js")
    assert "text/javascript" in hashed_js.headers["content-type"]
    assert hashed_js.headers["cache-control"] == "public, max-age=31536000, immutable"

    plain_mjs = client.get("/s/modern-web/assets/my-module-file.mjs")
    assert "text/javascript" in plain_mjs.headers["content-type"]
    assert plain_mjs.headers["cache-control"] == "public, max-age=300"

    wasm = client.get("/s/modern-web/assets/core.wasm")
    assert wasm.headers["content-type"] == "application/wasm"

    manifest = client.get("/s/modern-web/site.webmanifest")
    assert "application/manifest+json" in manifest.headers["content-type"]
    assert manifest.headers["cache-control"] == "no-cache"

    # Unbuilt source directory diagnostic (with dist/ present)
    src_zip = _make_zip(
        {
            "package.json": '{"name":"my-app"}',
            "index.html": '<html><body><script type="module" src="/src/main.ts"></script></body></html>',
            "dist/index.html": "<html><body>Built</body></html>",
        }
    )
    r_src = client.post(
        "/api/v1/sites",
        headers=_auth_headers(),
        data={"slug": "unbuilt-proj"},
        files={"file": ("site.zip", src_zip, "application/zip")},
    )
    assert r_src.status_code == 201
    assert any("dist/" in w for w in r_src.json()["warnings"])
