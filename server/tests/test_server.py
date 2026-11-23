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
