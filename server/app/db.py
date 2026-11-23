"""SQLite database layer for AntOrbit server."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .security import hash_api_key


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    is_env INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_used_at TEXT
);

CREATE TABLE IF NOT EXISTS sites (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    password_hash TEXT,
    allow_submit INTEGER NOT NULL DEFAULT 0,
    kv_mode TEXT NOT NULL DEFAULT 'off',
    notify_on_submit INTEGER NOT NULL DEFAULT 0,
    notify_channel TEXT NOT NULL DEFAULT '',
    expires_at TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    file_count INTEGER NOT NULL DEFAULT 0,
    view_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_slug TEXT NOT NULL REFERENCES sites(slug) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_submissions_slug_id ON submissions(site_slug, id DESC);

CREATE TABLE IF NOT EXISTS kv_store (
    site_slug TEXT NOT NULL REFERENCES sites(slug) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (site_slug, key)
);

CREATE TABLE IF NOT EXISTS notification_channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    config_json TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    site_slug TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    url TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notification_logs_created ON notification_logs(id DESC);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.session() as conn:
            conn.executescript(SCHEMA_SQL)

    # ---- API Keys ----

    def ensure_env_api_key(self, raw_key: str) -> None:
        if not raw_key:
            return
        key_hash = hash_api_key(raw_key)
        prefix = raw_key[:10] + "..." if len(raw_key) > 10 else raw_key
        now = utc_now_iso()
        with self.session() as conn:
            existing = conn.execute(
                "SELECT id FROM api_keys WHERE key_hash = ?", (key_hash,)
            ).fetchone()
            if existing:
                return
            conn.execute("DELETE FROM api_keys WHERE is_env = 1")
            conn.execute(
                """
                INSERT INTO api_keys (id, name, key_prefix, key_hash, is_env, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (str(uuid.uuid4()), "Bootstrap (ENV)", prefix, key_hash, now),
            )

    def create_api_key(self, name: str, raw_key: str) -> dict[str, Any]:
        key_id = str(uuid.uuid4())
        key_hash = hash_api_key(raw_key)
        prefix = raw_key[:10] + "..."
        now = utc_now_iso()
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO api_keys (id, name, key_prefix, key_hash, is_env, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (key_id, name, prefix, key_hash, now),
            )
        return {
            "id": key_id,
            "name": name,
            "key_prefix": prefix,
            "is_env": False,
            "created_at": now,
            "last_used_at": None,
        }

    def verify_api_key(self, raw_key: str) -> dict[str, Any] | None:
        key_hash = hash_api_key(raw_key)
        now = utc_now_iso()
        with self.session() as conn:
            row = conn.execute(
                "SELECT id, name, key_prefix, is_env, created_at, last_used_at FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()
            if not row:
                return None
            conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now, row["id"]))
            result = dict(row)
            result["is_env"] = bool(result["is_env"])
            result["last_used_at"] = now
            return result

    def list_api_keys(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT id, name, key_prefix, is_env, created_at, last_used_at FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
            return [{**dict(r), "is_env": bool(r["is_env"])} for r in rows]

    def delete_api_key(self, key_id: str) -> bool:
        with self.session() as conn:
            cur = conn.execute("DELETE FROM api_keys WHERE id = ? AND is_env = 0", (key_id,))
            return cur.rowcount > 0

    # ---- Sites ----

    def upsert_site(
        self,
        *,
        slug: str,
        title: str,
        description: str,
        password_hash: str | None,
        preserve_password: bool,
        allow_submit: bool,
        kv_mode: str,
        notify_on_submit: bool,
        notify_channel: str,
        expires_at: str | None,
        size_bytes: int,
        file_count: int,
    ) -> tuple[dict[str, Any], bool]:
        """Insert or update site metadata while preserving submissions and KV on overwrite."""
        now = utc_now_iso()
        with self.session() as conn:
            existing = conn.execute("SELECT * FROM sites WHERE slug = ?", (slug,)).fetchone()
            if existing:
                final_pw_hash = existing["password_hash"] if preserve_password else password_hash
                conn.execute(
                    """
                    UPDATE sites
                    SET title = ?,
                        description = ?,
                        password_hash = ?,
                        allow_submit = ?,
                        kv_mode = ?,
                        notify_on_submit = ?,
                        notify_channel = ?,
                        expires_at = ?,
                        size_bytes = ?,
                        file_count = ?,
                        updated_at = ?
                    WHERE slug = ?
                    """,
                    (
                        title,
                        description,
                        final_pw_hash,
                        int(allow_submit),
                        kv_mode,
                        int(notify_on_submit),
                        notify_channel,
                        expires_at,
                        size_bytes,
                        file_count,
                        now,
                        slug,
                    ),
                )
                updated = True
            else:
                conn.execute(
                    """
                    INSERT INTO sites (
                        slug, title, description, password_hash, allow_submit, kv_mode,
                        notify_on_submit, notify_channel, expires_at, size_bytes, file_count,
                        view_count, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        slug,
                        title,
                        description,
                        password_hash,
                        int(allow_submit),
                        kv_mode,
                        int(notify_on_submit),
                        notify_channel,
                        expires_at,
                        size_bytes,
                        file_count,
                        now,
                        now,
                    ),
                )
                updated = False
        site = self.get_site(slug)
        assert site is not None
        return site, updated

    def get_site_raw(self, slug: str) -> dict[str, Any] | None:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM sites WHERE slug = ?", (slug,)).fetchone()
            return dict(row) if row else None

    def get_site(self, slug: str) -> dict[str, Any] | None:
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT s.*,
                    (SELECT COUNT(*) FROM submissions sub WHERE sub.site_slug = s.slug) AS submission_count,
                    (SELECT COUNT(*) FROM kv_store kv WHERE kv.site_slug = s.slug) AS kv_count
                FROM sites s
                WHERE s.slug = ?
                """,
                (slug,),
            ).fetchone()
            if not row:
                return None
            return self._format_site(row)

    def list_sites(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                    (SELECT COUNT(*) FROM submissions sub WHERE sub.site_slug = s.slug) AS submission_count,
                    (SELECT COUNT(*) FROM kv_store kv WHERE kv.site_slug = s.slug) AS kv_count
                FROM sites s
                ORDER BY s.updated_at DESC
                """
            ).fetchall()
            return [self._format_site(r) for r in rows]

    def update_site_settings(self, slug: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        if not fields:
            return self.get_site(slug)
        allowed = {
            "title",
            "description",
            "password_hash",
            "allow_submit",
            "kv_mode",
            "notify_on_submit",
            "notify_channel",
            "expires_at",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_site(slug)
        updates["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [slug]
        with self.session() as conn:
            cur = conn.execute(f"UPDATE sites SET {assignments} WHERE slug = ?", values)
            if cur.rowcount == 0:
                return None
        return self.get_site(slug)

    def increment_view_count(self, slug: str) -> None:
        with self.session() as conn:
            conn.execute("UPDATE sites SET view_count = view_count + 1 WHERE slug = ?", (slug,))

    def delete_site(self, slug: str) -> bool:
        with self.session() as conn:
            cur = conn.execute("DELETE FROM sites WHERE slug = ?", (slug,))
            return cur.rowcount > 0

    def list_expired_slugs(self) -> list[str]:
        now = utc_now_iso()
        with self.session() as conn:
            rows = conn.execute(
                "SELECT slug FROM sites WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            ).fetchall()
            return [r["slug"] for r in rows]

    @staticmethod
    def _format_site(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        has_password = bool(d.pop("password_hash", None))
        d["has_password"] = has_password
        d["allow_submit"] = bool(d["allow_submit"])
        d["notify_on_submit"] = bool(d["notify_on_submit"])
        expires_at = parse_iso(d.get("expires_at"))
        d["is_expired"] = bool(expires_at and expires_at <= datetime.now(timezone.utc))
        return d

    # ---- Submissions ----

    def create_submission(
        self, site_slug: str, payload: Any, meta: dict[str, Any]
    ) -> dict[str, Any]:
        now = utc_now_iso()
        payload_json = json.dumps(payload, ensure_ascii=False)
        meta_json = json.dumps(meta, ensure_ascii=False)
        with self.session() as conn:
            cur = conn.execute(
                """
                INSERT INTO submissions (site_slug, payload_json, meta_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (site_slug, payload_json, meta_json, now),
            )
            sub_id = cur.lastrowid
        return {
            "id": sub_id,
            "site_slug": site_slug,
            "payload": payload,
            "meta": meta,
            "created_at": now,
        }

    def list_submissions(
        self, site_slug: str, *, limit: int = 50, offset: int = 0, since_id: int | None = None
    ) -> list[dict[str, Any]]:
        with self.session() as conn:
            if since_id is not None:
                rows = conn.execute(
                    """
                    SELECT id, site_slug, payload_json, meta_json, created_at
                    FROM submissions
                    WHERE site_slug = ? AND id > ?
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (site_slug, since_id, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, site_slug, payload_json, meta_json, created_at
                    FROM submissions
                    WHERE site_slug = ?
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (site_slug, limit, offset),
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "site_slug": r["site_slug"],
                    "payload": json.loads(r["payload_json"]),
                    "meta": json.loads(r["meta_json"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def delete_submission(self, site_slug: str, sub_id: int) -> bool:
        with self.session() as conn:
            cur = conn.execute(
                "DELETE FROM submissions WHERE site_slug = ? AND id = ?",
                (site_slug, sub_id),
            )
            return cur.rowcount > 0

    def clear_submissions(self, site_slug: str) -> int:
        with self.session() as conn:
            cur = conn.execute("DELETE FROM submissions WHERE site_slug = ?", (site_slug,))
            return cur.rowcount

    # ---- KV Store ----

    def kv_list(self, site_slug: str) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT key, value_json, updated_at FROM kv_store WHERE site_slug = ? ORDER BY key ASC",
                (site_slug,),
            ).fetchall()
            return [
                {
                    "key": r["key"],
                    "value": json.loads(r["value_json"]),
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]

    def kv_count(self, site_slug: str) -> int:
        with self.session() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM kv_store WHERE site_slug = ?", (site_slug,)
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def kv_get(self, site_slug: str, key: str) -> dict[str, Any] | None:
        with self.session() as conn:
            row = conn.execute(
                "SELECT key, value_json, updated_at FROM kv_store WHERE site_slug = ? AND key = ?",
                (site_slug, key),
            ).fetchone()
            if not row:
                return None
            return {
                "key": row["key"],
                "value": json.loads(row["value_json"]),
                "updated_at": row["updated_at"],
            }

    def kv_set(self, site_slug: str, key: str, value: Any) -> dict[str, Any]:
        now = utc_now_iso()
        value_json = json.dumps(value, ensure_ascii=False)
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO kv_store (site_slug, key, value_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(site_slug, key)
                DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
                """,
                (site_slug, key, value_json, now),
            )
        return {"key": key, "value": value, "updated_at": now}

    def kv_delete(self, site_slug: str, key: str) -> bool:
        with self.session() as conn:
            cur = conn.execute(
                "DELETE FROM kv_store WHERE site_slug = ? AND key = ?",
                (site_slug, key),
            )
            return cur.rowcount > 0

    # ---- Notification Channels ----

    def list_channels(self, include_config: bool = False) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT * FROM notification_channels ORDER BY is_default DESC, name ASC"
            ).fetchall()
            result: list[dict[str, Any]] = []
            for r in rows:
                item: dict[str, Any] = {
                    "id": r["id"],
                    "name": r["name"],
                    "provider": r["provider"],
                    "is_default": bool(r["is_default"]),
                    "enabled": bool(r["enabled"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                if include_config:
                    item["config"] = json.loads(r["config_json"])
                result.append(item)
            return result

    def get_channel_by_id(self, channel_id: str) -> dict[str, Any] | None:
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM notification_channels WHERE id = ?", (channel_id,)
            ).fetchone()
            return self._format_channel(row) if row else None

    def get_channel_by_name(self, name: str) -> dict[str, Any] | None:
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM notification_channels WHERE name = ?", (name,)
            ).fetchone()
            return self._format_channel(row) if row else None

    def get_default_channel(self) -> dict[str, Any] | None:
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT * FROM notification_channels
                WHERE enabled = 1
                ORDER BY is_default DESC, created_at ASC
                LIMIT 1
                """
            ).fetchone()
            return self._format_channel(row) if row else None

    def create_channel(
        self,
        *,
        name: str,
        provider: str,
        config: dict[str, Any],
        is_default: bool,
        enabled: bool,
    ) -> dict[str, Any]:
        channel_id = str(uuid.uuid4())
        now = utc_now_iso()
        with self.session() as conn:
            if is_default:
                conn.execute("UPDATE notification_channels SET is_default = 0")
            else:
                count = conn.execute("SELECT COUNT(*) AS cnt FROM notification_channels").fetchone()["cnt"]
                if count == 0:
                    is_default = True
            conn.execute(
                """
                INSERT INTO notification_channels (id, name, provider, config_json, is_default, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel_id,
                    name,
                    provider,
                    json.dumps(config, ensure_ascii=False),
                    int(is_default),
                    int(enabled),
                    now,
                    now,
                ),
            )
        ch = self.get_channel_by_id(channel_id)
        assert ch is not None
        return ch

    def update_channel(
        self,
        channel_id: str,
        *,
        name: str,
        provider: str,
        config: dict[str, Any],
        is_default: bool,
        enabled: bool,
    ) -> dict[str, Any] | None:
        now = utc_now_iso()
        with self.session() as conn:
            existing = conn.execute(
                "SELECT id FROM notification_channels WHERE id = ?", (channel_id,)
            ).fetchone()
            if not existing:
                return None
            if is_default:
                conn.execute("UPDATE notification_channels SET is_default = 0")
            conn.execute(
                """
                UPDATE notification_channels
                SET name = ?, provider = ?, config_json = ?, is_default = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    provider,
                    json.dumps(config, ensure_ascii=False),
                    int(is_default),
                    int(enabled),
                    now,
                    channel_id,
                ),
            )
        return self.get_channel_by_id(channel_id)

    def delete_channel(self, channel_id: str) -> bool:
        with self.session() as conn:
            cur = conn.execute("DELETE FROM notification_channels WHERE id = ?", (channel_id,))
            return cur.rowcount > 0

    @staticmethod
    def _format_channel(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "provider": row["provider"],
            "config": json.loads(row["config_json"]),
            "is_default": bool(row["is_default"]),
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ---- Notification Logs ----

    def create_notification_log(
        self,
        *,
        channel_name: str,
        provider: str,
        trigger_type: str,
        site_slug: str | None,
        title: str,
        body: str,
        url: str | None,
        status: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.session() as conn:
            cur = conn.execute(
                """
                INSERT INTO notification_logs (
                    channel_name, provider, trigger_type, site_slug, title, body, url, status, error_message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel_name,
                    provider,
                    trigger_type,
                    site_slug,
                    title,
                    body,
                    url,
                    status,
                    error_message,
                    now,
                ),
            )
            log_id = cur.lastrowid
        return {
            "id": log_id,
            "channel_name": channel_name,
            "provider": provider,
            "trigger_type": trigger_type,
            "site_slug": site_slug,
            "title": title,
            "body": body,
            "url": url,
            "status": status,
            "error_message": error_message,
            "created_at": now,
        }

    def list_notification_logs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM notification_logs
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
