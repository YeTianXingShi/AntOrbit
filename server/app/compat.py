"""Static website compatibility engine: MIME types, caching, path rewriting, and diagnostics."""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any

# Explicit modern MIME map so minimal Docker images (python:3.12-slim) never
# break ES modules, WASM, modern image/font formats, or UTF-8 text decoding.
MODERN_MIME_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".cjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".pdf": "application/pdf",
}

NO_CACHE_FILENAMES = {
    "sw.js",
    "service-worker.js",
    "manifest.json",
    "site.webmanifest",
}

NO_CACHE_EXTENSIONS = {".html", ".htm", ".webmanifest"}

# Match content-hashed bundler assets like `index-D9xK2a1b.js` or `app.8f3a1c2d.css`,
# requiring a separator and either >=8 hex chars OR >=8 alnum/underscore chars with both letter and digit.
HASHED_STEM_RE = re.compile(
    r"[-.](?:[0-9a-fA-F]{8,}|(?=[A-Za-z0-9_]{8,}$)(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_]{8,})$"
)

IMMUTABLE_ASSET_EXTENSIONS = {
    ".js",
    ".mjs",
    ".css",
    ".woff2",
    ".woff",
    ".ttf",
    ".otf",
    ".wasm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".avif",
    ".svg",
    ".gif",
}

# HTML/CSS rewriting patterns
HTML_ATTR_RE = re.compile(
    r"""(\b(?:src|href|poster|action|data)\s*=\s*)(["'])(/(?!/)(?:[^"']*))\2""",
    re.IGNORECASE,
)
HTML_SRCSET_RE = re.compile(
    r"""(\bsrcset\s*=\s*)(["'])([^"']+)\2""",
    re.IGNORECASE,
)
HTML_STYLE_BLOCK_RE = re.compile(
    r"(<style\b[^>]*>)(.*?)(</style>)",
    re.IGNORECASE | re.DOTALL,
)
CSS_URL_RE = re.compile(
    r"""url\(\s*(["']?)(/(?!/)(?:[^)"'\s]*))\1\s*\)""",
    re.IGNORECASE,
)
CSS_IMPORT_RE = re.compile(
    r"""(@import\s+)(["'])(/(?!/)(?:[^"']*))\2""",
    re.IGNORECASE,
)
BASE_TAG_RE = re.compile(r"<base\b[^>]*>", re.IGNORECASE)
HEAD_OPEN_RE = re.compile(r"(<head\b[^>]*>)", re.IGNORECASE)

# Diagnostic patterns
UNBUILT_SRC_RE = re.compile(
    r"""(?:src|href)\s*=\s*["'](?:\.?/)?src/[^"']+\.(?:ts|tsx|jsx|vue|svelte)["']""",
    re.IGNORECASE,
)
JS_ROOT_ASSET_RE = re.compile(
    r"""["'](/(?:assets|static|images|img|fonts|media|data)/[^"'\\\s]+)["']"""
    r"""|fetch\(\s*["'](/(?!/)(?!_antorbit/)(?!_api/)[^"'\\\s]+)["']"""
)

MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024  # 2 MB per file guard


def guess_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in MODERN_MIME_TYPES:
        return MODERN_MIME_TYPES[ext]
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        if guessed.startswith("text/") and "charset=" not in guessed:
            return f"{guessed}; charset=utf-8"
        return guessed
    return "application/octet-stream"


def compute_cache_control(rel_path: Path) -> str:
    name_lower = rel_path.name.lower()
    ext = rel_path.suffix.lower()
    if ext in NO_CACHE_EXTENSIONS or name_lower in NO_CACHE_FILENAMES:
        return "no-cache"
    if ext in IMMUTABLE_ASSET_EXTENSIONS and HASHED_STEM_RE.search(rel_path.stem):
        return "public, max-age=31536000, immutable"
    return "public, max-age=300"


def _is_reserved_root_path(path_value: str, slug: str) -> bool:
    if not path_value.startswith("/") or path_value.startswith("//"):
        return True
    if path_value in (f"/s/{slug}", "/_unlock"):
        return True
    reserved_prefixes = (
        "/_antorbit/",
        "/_api/",
        "/_unlock/",
        f"/s/{slug}/",
    )
    return any(path_value.startswith(prefix) for prefix in reserved_prefixes)


def rewrite_css_root_paths(css: str, slug: str) -> tuple[str, int]:
    count = 0
    prefix = f"/s/{slug}"

    def _repl_url(m: re.Match[str]) -> str:
        nonlocal count
        quote, path_val = m.group(1), m.group(2)
        if _is_reserved_root_path(path_val, slug):
            return m.group(0)
        count += 1
        return f"url({quote}{prefix}{path_val}{quote})"

    def _repl_import(m: re.Match[str]) -> str:
        nonlocal count
        head, quote, path_val = m.group(1), m.group(2), m.group(3)
        if _is_reserved_root_path(path_val, slug):
            return m.group(0)
        count += 1
        return f"{head}{quote}{prefix}{path_val}{quote}"

    out = CSS_URL_RE.sub(_repl_url, css)
    out = CSS_IMPORT_RE.sub(_repl_import, out)
    return out, count


def rewrite_html_root_paths(html_text: str, slug: str) -> tuple[str, int]:
    count = 0
    prefix = f"/s/{slug}"

    def _repl_attr(m: re.Match[str]) -> str:
        nonlocal count
        head, quote, path_val = m.group(1), m.group(2), m.group(3)
        if _is_reserved_root_path(path_val, slug):
            return m.group(0)
        count += 1
        return f"{head}{quote}{prefix}{path_val}{quote}"

    def _repl_srcset(m: re.Match[str]) -> str:
        nonlocal count
        head, quote, raw_val = m.group(1), m.group(2), m.group(3)
        parts: list[str] = []
        changed = False
        for item in raw_val.split(","):
            stripped = item.strip()
            if not stripped:
                continue
            tokens = stripped.split(None, 1)
            url_part = tokens[0]
            if url_part.startswith("/") and not _is_reserved_root_path(url_part, slug):
                url_part = f"{prefix}{url_part}"
                count += 1
                changed = True
            parts.append(f"{url_part} {tokens[1]}" if len(tokens) > 1 else url_part)
        if not changed:
            return m.group(0)
        return f"{head}{quote}{', '.join(parts)}{quote}"

    def _repl_style_block(m: re.Match[str]) -> str:
        nonlocal count
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        new_body, c = rewrite_css_root_paths(body, slug)
        count += c
        return f"{open_tag}{new_body}{close_tag}"

    out = HTML_ATTR_RE.sub(_repl_attr, html_text)
    out = HTML_SRCSET_RE.sub(_repl_srcset, out)
    out = HTML_STYLE_BLOCK_RE.sub(_repl_style_block, out)
    return out, count


def inject_base_href(html_text: str, slug: str) -> str:
    """Ensure root index.html has <base href="/s/<slug>/"> when served on a deep SPA route."""
    if BASE_TAG_RE.search(html_text):
        return html_text
    base_tag = f'<base href="/s/{slug}/">'
    if HEAD_OPEN_RE.search(html_text):
        return HEAD_OPEN_RE.sub(rf"\1\n  {base_tag}", html_text, count=1)
    return f"{base_tag}\n{html_text}"


def process_published_site(
    site_dir: Path,
    slug: str,
    *,
    rewrite_paths: bool = True,
    allow_submit: bool = False,
    kv_mode: str = "off",
) -> dict[str, Any]:
    """Rewrite root-absolute paths (if enabled) and collect compatibility warnings.

    Runs inside staging before atomic directory replacement.
    Returns {"warnings": [...], "rewrites": {"html_files": n, "css_files": n, "urls_rewritten": n}, "size_delta": int}.
    """
    warnings: list[str] = []
    html_files_rewritten = 0
    css_files_rewritten = 0
    total_urls_rewritten = 0
    unrewritten_root_refs = 0
    size_delta = 0

    any_html_mentions_sdk = False
    js_root_path_samples: list[str] = []

    # Diagnostic 1 (must inspect raw index.html BEFORE root-path rewriting)
    pkg_json = site_dir / "package.json"
    root_index = site_dir / "index.html"
    if pkg_json.is_file() and root_index.is_file():
        try:
            raw_idx_text = root_index.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_idx_text = ""
        if UNBUILT_SRC_RE.search(raw_idx_text):
            if (site_dir / "dist" / "index.html").is_file():
                warnings.append(
                    "Detected unbuilt source project directory (package.json + /src/... entry), "
                    "and a built dist/index.html exists inside it. Publish the dist/ directory instead."
                )
            elif (site_dir / "build" / "index.html").is_file():
                warnings.append(
                    "Detected unbuilt source project directory (package.json + /src/... entry), "
                    "and a built build/index.html exists inside it. Publish the build/ directory instead."
                )
            else:
                warnings.append(
                    "Detected unbuilt source project directory (package.json + /src/... entry in index.html). "
                    "Run your build command (e.g., npm run build) and publish the built output directory."
                )

    all_files = [p for p in site_dir.rglob("*") if p.is_file()]

    for file_path in all_files:
        ext = file_path.suffix.lower()
        try:
            fsize = file_path.stat().st_size
        except OSError:
            continue
        if fsize > MAX_TEXT_SCAN_BYTES:
            continue

        if ext in (".html", ".htm"):
            try:
                original = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            if "/_antorbit/sdk.js" in original or "/_api/submit" in original or "/_api/kv" in original:
                any_html_mentions_sdk = True

            rewritten, count = rewrite_html_root_paths(original, slug)
            if count > 0:
                if rewrite_paths:
                    old_len = len(original.encode("utf-8"))
                    new_bytes = rewritten.encode("utf-8")
                    file_path.write_bytes(new_bytes)
                    size_delta += len(new_bytes) - old_len
                    html_files_rewritten += 1
                    total_urls_rewritten += count
                else:
                    unrewritten_root_refs += count

        elif ext == ".css":
            try:
                original = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            rewritten, count = rewrite_css_root_paths(original, slug)
            if count > 0:
                if rewrite_paths:
                    old_len = len(original.encode("utf-8"))
                    new_bytes = rewritten.encode("utf-8")
                    file_path.write_bytes(new_bytes)
                    size_delta += len(new_bytes) - old_len
                    css_files_rewritten += 1
                    total_urls_rewritten += count
                else:
                    unrewritten_root_refs += count

        elif ext in (".js", ".mjs") and len(js_root_path_samples) < 3:
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for match in JS_ROOT_ASSET_RE.finditer(content):
                sample = match.group(1) or match.group(2)
                if sample and not _is_reserved_root_path(sample, slug):
                    if sample not in js_root_path_samples:
                        js_root_path_samples.append(sample)
                    if len(js_root_path_samples) >= 3:
                        break

    # Diagnostic 2: Missing root index.html
    if not root_index.is_file():
        root_htmls = sorted(
            p.name
            for p in site_dir.iterdir()
            if p.is_file() and p.suffix.lower() in (".html", ".htm") and p.name.lower() != "404.html"
        )
        if len(root_htmls) == 1:
            warnings.append(
                f"No root index.html found; AntOrbit will automatically serve '{root_htmls[0]}' at /s/{slug}/."
            )
        else:
            warnings.append(
                f"No root index.html found; visiting /s/{slug}/ directly will return 404 unless a specific file path is requested."
            )

    # Diagnostic 3: Root-absolute paths in JS bundles
    if js_root_path_samples:
        sample_str = ", ".join(js_root_path_samples)
        warnings.append(
            f"Detected root-absolute paths in JS files ({sample_str}). "
            "Server path rewriting does not modify JS code; configure base: './' in Vite/bundler or use relative './' paths."
        )

    # Diagnostic 4: Unrewritten HTML/CSS root paths when rewrite_paths=False
    if not rewrite_paths and unrewritten_root_refs > 0:
        warnings.append(
            f"Found {unrewritten_root_refs} root-absolute path(s) in HTML/CSS while rewrite_paths=false; "
            f"they may 404 under /s/{slug}/."
        )

    # Diagnostic 5: Interactive flags enabled without referencing SDK
    if (allow_submit or kv_mode != "off") and not any_html_mentions_sdk:
        warnings.append(
            "Interactive mode (allow_submit or kv_mode) is enabled, "
            'but no HTML file references <script src="/_antorbit/sdk.js"></script>.'
        )

    return {
        "warnings": warnings,
        "rewrites": {
            "enabled": rewrite_paths,
            "html_files": html_files_rewritten,
            "css_files": css_files_rewritten,
            "urls_rewritten": total_urls_rewritten,
        },
        "size_delta": size_delta,
    }
