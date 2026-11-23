"""Configuration settings for AntOrbit server."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANTORBIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("./data")
    web_dist_dir: Path | None = None
    admin_password: str = "antorbit"
    public_url: str = ""
    api_key: str = ""
    secret_key: str = ""

    max_upload_mb: int = 50
    max_uncompressed_mb: int = 120
    max_site_files: int = 2000
    max_submission_kb: int = 256
    max_kv_value_kb: int = 256
    max_kv_keys_per_site: int = 500
    cleanup_interval_sec: int = 300
    rate_limit_per_min: int = 60

    @property
    def sites_dir(self) -> Path:
        return self.data_dir / "sites"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "antorbit.db"

    @property
    def is_default_admin_password(self) -> bool:
        return self.admin_password == "antorbit"

    def resolve_secret_key(self) -> str:
        if self.secret_key:
            return self.secret_key
        key_file = self.data_dir / ".secret_key"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        generated = secrets.token_hex(32)
        key_file.write_text(generated, encoding="utf-8")
        return generated

    def resolve_web_dist_dir(self) -> Path | None:
        if self.web_dist_dir and self.web_dist_dir.exists():
            return self.web_dist_dir
        candidates = [
            Path("/app/web_dist"),
            Path(__file__).resolve().parents[2] / "web" / "dist",
        ]
        for candidate in candidates:
            if candidate.exists() and (candidate / "index.html").exists():
                return candidate
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
