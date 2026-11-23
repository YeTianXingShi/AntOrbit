"""Tests for AntOrbit MCP client and directory zip bundler."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from antorbit_mcp.client import AntOrbitClient, AntOrbitError, pack_directory_to_zip
from antorbit_mcp.server import mcp as mcp_server


@pytest.mark.asyncio
async def test_mcp_server_registers_all_tools() -> None:
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    expected = {
        "publish_site",
        "list_sites",
        "get_site",
        "update_site",
        "delete_site",
        "get_submissions",
        "kv_list",
        "kv_get",
        "kv_set",
        "kv_delete",
        "list_channels",
        "send_notification",
    }
    assert expected.issubset(names)


def test_pack_directory_skips_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("big", encoding="utf-8")

    raw, count = pack_directory_to_zip(tmp_path)
    assert count == 2
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = sorted(zf.namelist())
    assert names == ["assets/app.js", "index.html"]


def test_client_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTORBIT_URL", raising=False)
    monkeypatch.delenv("ANTORBIT_API_KEY", raising=False)
    with pytest.raises(AntOrbitError):
        AntOrbitClient()


@respx.mock
@pytest.mark.asyncio
async def test_client_publish_directory_and_notify(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Hi</h1>", encoding="utf-8")

    pub_route = respx.post("https://orbit.example.com/api/v1/sites").mock(
        return_value=httpx.Response(
            201,
            json={
                "site": {"slug": "demo", "url": "https://orbit.example.com/s/demo/"},
                "updated": False,
                "notification": None,
            },
        )
    )
    notify_route = respx.post("https://orbit.example.com/api/v1/notify").mock(
        return_value=httpx.Response(200, json={"ok": True, "log": {"id": 1, "status": "success"}})
    )

    client = AntOrbitClient(base_url="https://orbit.example.com", api_key="ao_test")
    res = await client.publish_site(directory=str(tmp_path), slug="demo", allow_submit=True)
    assert pub_route.called
    assert res["site"]["url"] == "https://orbit.example.com/s/demo/"

    nres = await client.send_notification(title="Done", body="Ready", url=res["site"]["url"])
    assert notify_route.called
    assert nres["ok"] is True
