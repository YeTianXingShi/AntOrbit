"""Safe static site storage: slug validation, Zip Slip guard, atomic replacement."""

from __future__ import annotations

import io
import re
import secrets
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .compat import process_published_site

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$|^[a-z0-9]{2,64}$")
RESERVED_SLUGS = {"admin", "api", "_api", "_antorbit", "health", "static", "assets"}
KV_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9._:-]{1,128}$")


class StorageError(ValueError):
    """Raised when uploaded archive or slug violates safety constraints."""


def validate_slug(slug: str) -> str:
    cleaned = slug.strip().lower()
    if not cleaned or not SLUG_PATTERN.match(cleaned):
        raise StorageError(
            "Invalid slug: use 2-64 lowercase letters, digits, hyphens, or underscores."
        )
    if cleaned in RESERVED_SLUGS or cleaned.startswith("_"):
        raise StorageError(f"Slug '{cleaned}' is reserved.")
    return cleaned


def generate_slug(length: int = 10) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_kv_key(key: str) -> str:
    if not key or not KV_KEY_PATTERN.match(key):
        raise StorageError(
            "Invalid KV key: use 1-128 characters matching [a-zA-Z0-9._:-]."
        )
    return key


def _is_symlink_info(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _strip_single_root_folder(extracted_dir: Path) -> None:
    """If zip contained a single top-level directory containing index.html, hoist its contents."""
    entries = [p for p in extracted_dir.iterdir() if p.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        top = entries[0]
        if (top / "index.html").exists():
            temp_move = extracted_dir.parent / f"hoist_{secrets.token_hex(6)}"
            shutil.move(str(top), str(temp_move))
            for child in temp_move.iterdir():
                shutil.move(str(child), str(extracted_dir / child.name))
            shutil.rmtree(temp_move, ignore_errors=True)
    macosx = extracted_dir / "__MACOSX"
    if macosx.exists():
        shutil.rmtree(macosx, ignore_errors=True)


def _replace_directory_atomic(staging_dir: Path, target_dir: Path) -> None:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    backup_dir: Path | None = None
    if target_dir.exists():
        backup_dir = target_dir.parent / f".old_{target_dir.name}_{secrets.token_hex(6)}"
        shutil.move(str(target_dir), str(backup_dir))
    try:
        shutil.move(str(staging_dir), str(target_dir))
    except Exception:
        if backup_dir and backup_dir.exists() and not target_dir.exists():
            shutil.move(str(backup_dir), str(target_dir))
        raise
    finally:
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)


def write_html_site(
    sites_dir: Path,
    slug: str,
    html_content: str,
    *,
    rewrite_paths: bool = True,
    allow_submit: bool = False,
    kv_mode: str = "off",
) -> tuple[int, int, dict[str, Any]]:
    """Write a single-file HTML site atomically. Returns (size_bytes, file_count, compat_report)."""
    sites_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".staging_{slug}_", dir=sites_dir))
    try:
        data = html_content.encode("utf-8")
        (staging / "index.html").write_bytes(data)
        report = process_published_site(
            staging,
            slug,
            rewrite_paths=rewrite_paths,
            allow_submit=allow_submit,
            kv_mode=kv_mode,
        )
        final_size = len(data) + report["size_delta"]
        _replace_directory_atomic(staging, sites_dir / slug)
        return final_size, 1, report
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def extract_zip_site(
    sites_dir: Path,
    slug: str,
    zip_bytes: bytes,
    *,
    max_files: int,
    max_uncompressed_bytes: int,
    rewrite_paths: bool = True,
    allow_submit: bool = False,
    kv_mode: str = "off",
) -> tuple[int, int, dict[str, Any]]:
    """Safely extract a zip bundle into sites_dir/<slug> atomically. Returns (size_bytes, file_count, compat_report)."""
    sites_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".staging_{slug}_", dir=sites_dir))
    try:
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile as exc:
            raise StorageError("Uploaded file is not a valid ZIP archive.") from exc

        total_size = 0
        file_count = 0
        staging_resolved = staging.resolve()

        with zf:
            for info in zf.infolist():
                filename = info.filename.replace("\\", "/")
                if not filename or filename.startswith("__MACOSX/"):
                    continue
                if info.is_dir():
                    continue
                if _is_symlink_info(info):
                    raise StorageError(f"Archive contains forbidden symlink: {filename}")
                if filename.startswith("/") or ".." in Path(filename).parts:
                    raise StorageError(f"Archive contains unsafe path: {filename}")

                file_count += 1
                if file_count > max_files:
                    raise StorageError(f"Archive exceeds maximum file limit ({max_files}).")

                dest = (staging / filename).resolve()
                try:
                    dest.relative_to(staging_resolved)
                except ValueError as exc:
                    raise StorageError(f"Archive path traversal detected: {filename}") from exc

                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, open(dest, "wb") as dst:
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        total_size += len(chunk)
                        if total_size > max_uncompressed_bytes:
                            raise StorageError(
                                f"Archive uncompressed size exceeds limit ({max_uncompressed_bytes // (1024 * 1024)} MB)."
                            )
                        dst.write(chunk)

        if file_count == 0:
            raise StorageError("Archive does not contain any files.")

        _strip_single_root_folder(staging)
        report = process_published_site(
            staging,
            slug,
            rewrite_paths=rewrite_paths,
            allow_submit=allow_submit,
            kv_mode=kv_mode,
        )
        final_size = total_size + report["size_delta"]
        _replace_directory_atomic(staging, sites_dir / slug)
        return final_size, file_count, report
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def delete_site_files(sites_dir: Path, slug: str) -> None:
    target = sites_dir / slug
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


@dataclass
class ResolvedTarget:
    kind: Literal["file", "redirect", "spa_fallback", "custom_404", "not_found"]
    path: Path | None = None
    rel_path: Path | None = None
    redirect_to: str | None = None


def resolve_site_target(sites_dir: Path, slug: str, rel_path: str) -> ResolvedTarget:
    """Resolve a requested path inside sites_dir/<slug> with full static-site compatibility.

    Resolution order:
    1. Root (""): index.html -> sole root *.html fallback -> custom 404.html -> not_found
    2. Exact file match
    3. Directory containing index.html (307 redirect if trailing slash is missing)
    4. Clean URL (<path>.html) for extensionless paths
    5. Custom 404.html (if present for HTML/extensionless routes)
    6. SPA fallback to root index.html (for extensionless paths when no custom 404.html)
    """
    site_root = (sites_dir / slug).resolve()
    if not site_root.exists():
        return ResolvedTarget(kind="not_found")

    raw_path = rel_path.lstrip("/")
    root_index = site_root / "index.html"
    custom_404 = site_root / "404.html"

    # 1. Root path
    if not raw_path:
        if root_index.is_file():
            return ResolvedTarget(kind="file", path=root_index, rel_path=Path("index.html"))
        root_htmls = sorted(
            p
            for p in site_root.iterdir()
            if p.is_file() and p.suffix.lower() in (".html", ".htm") and p.name.lower() != "404.html"
        )
        if len(root_htmls) == 1:
            sole = root_htmls[0]
            return ResolvedTarget(kind="file", path=sole, rel_path=Path(sole.name))
        if custom_404.is_file():
            return ResolvedTarget(kind="custom_404", path=custom_404, rel_path=Path("404.html"))
        return ResolvedTarget(kind="not_found")

    trailing_slash = raw_path.endswith("/")
    cleaned = raw_path.rstrip("/")
    if not cleaned:
        return resolve_site_target(sites_dir, slug, "")

    target = (site_root / cleaned).resolve()
    try:
        target.relative_to(site_root)
    except ValueError:
        return ResolvedTarget(kind="not_found")

    # 2. Exact file match
    if not trailing_slash and target.is_file():
        return ResolvedTarget(kind="file", path=target, rel_path=target.relative_to(site_root))

    # 3. Subdirectory index.html (enforce trailing slash via 307 so relative ./ assets resolve)
    if target.is_dir():
        idx = target / "index.html"
        if idx.is_file():
            if not trailing_slash:
                return ResolvedTarget(kind="redirect", redirect_to=f"/s/{slug}/{cleaned}/")
            return ResolvedTarget(kind="file", path=idx, rel_path=idx.relative_to(site_root))

    leaf_name = Path(cleaned).name
    has_extension = "." in leaf_name

    # 4. Clean URL (about -> about.html)
    if not trailing_slash and not has_extension:
        html_candidate = (site_root / f"{cleaned}.html").resolve()
        try:
            html_candidate.relative_to(site_root)
            if html_candidate.is_file():
                return ResolvedTarget(
                    kind="file",
                    path=html_candidate,
                    rel_path=html_candidate.relative_to(site_root),
                )
        except ValueError:
            pass

    # 5. Custom 404.html (for page routes; missing .js/.png assets still get clean 404)
    is_html_like = (not has_extension) or Path(cleaned).suffix.lower() in (".html", ".htm")
    if custom_404.is_file():
        if is_html_like:
            return ResolvedTarget(kind="custom_404", path=custom_404, rel_path=Path("404.html"))
        return ResolvedTarget(kind="not_found")

    # 6. SPA fallback for extensionless routes when root index.html exists
    if not has_extension and root_index.is_file():
        return ResolvedTarget(kind="spa_fallback", path=root_index, rel_path=Path("index.html"))

    return ResolvedTarget(kind="not_found")


def resolve_site_file(sites_dir: Path, slug: str, rel_path: str) -> Path | None:
    """Backwards-compatible wrapper returning a resolved Path or None."""
    resolved = resolve_site_target(sites_dir, slug, rel_path)
    if resolved.kind in ("file", "spa_fallback"):
        return resolved.path
    return None
