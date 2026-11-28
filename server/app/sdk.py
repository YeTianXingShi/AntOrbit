"""Built-in client JS SDK (/_antorbit/sdk.js) and HTML unlock/error pages."""

from __future__ import annotations

import html

SDK_JS = r"""(function (global) {
  'use strict';

  function detectBase() {
    var match = global.location.pathname.match(/^\/s\/([^\/]+)/);
    if (!match) {
      return { slug: '', base: '' };
    }
    return { slug: decodeURIComponent(match[1]), base: '/s/' + match[1] };
  }

  var detected = detectBase();

  async function request(path, options) {
    if (!detected.base) {
      throw new Error('AntOrbit SDK must be used on a hosted /s/<slug>/ page.');
    }
    var opts = Object.assign({ credentials: 'same-origin' }, options || {});
    opts.headers = Object.assign({ 'Accept': 'application/json' }, opts.headers || {});
    var resp = await fetch(detected.base + path, opts);
    var text = await resp.text();
    var data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_) {
      data = text;
    }
    if (!resp.ok) {
      var msg = (data && data.detail) ? data.detail : ('Request failed with status ' + resp.status);
      var err = new Error(msg);
      err.status = resp.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  var AntOrbit = {
    slug: detected.slug,
    baseUrl: detected.base,

    /**
     * Submit form or structured JSON payload to this site's submission inbox.
     * @param {any} payload
     * @returns {Promise<{id: number, created_at: string}>}
     */
    submit: function (payload) {
      return request('/_api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: payload })
      });
    },

    kv: {
      list: async function () {
        var res = await request('/_api/kv', { method: 'GET' });
        return res.items || [];
      },
      get: async function (key) {
        try {
          var res = await request('/_api/kv/' + encodeURIComponent(key), { method: 'GET' });
          return res.value;
        } catch (err) {
          if (err && err.status === 404) return null;
          throw err;
        }
      },
      set: function (key, value) {
        return request('/_api/kv/' + encodeURIComponent(key), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value: value })
        });
      },
      delete: function (key) {
        return request('/_api/kv/' + encodeURIComponent(key), { method: 'DELETE' });
      }
    }
  };

  global.AntOrbit = AntOrbit;
})(window);
"""


UI_CSS = r"""/* AntOrbit Built-in Design System (/_antorbit/ui.css) — Slate + Sky */
:root {
  color-scheme: light dark;

  --ao-font-sans: system-ui, -apple-system, BlinkMacSystemFont, "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", "Segoe UI", Roboto, sans-serif;
  --ao-font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;

  --ao-bg: #f8fafc;
  --ao-surface: #ffffff;
  --ao-surface-muted: #f1f5f9;
  --ao-border: #e2e8f0;
  --ao-border-strong: #cbd5e1;

  --ao-text: #0f172a;
  --ao-text-secondary: #475569;
  --ao-text-muted: #64748b;

  --ao-primary: #0284c7;
  --ao-primary-hover: #0369a1;
  --ao-primary-fg: #ffffff;
  --ao-primary-soft: rgba(2, 132, 199, 0.10);
  --ao-primary-text: #0369a1;

  --ao-success: #059669;
  --ao-success-soft: rgba(5, 150, 105, 0.10);
  --ao-success-text: #047857;

  --ao-warning: #d97706;
  --ao-warning-soft: rgba(217, 119, 6, 0.12);
  --ao-warning-text: #b45309;

  --ao-danger: #dc2626;
  --ao-danger-soft: rgba(220, 38, 38, 0.10);
  --ao-danger-text: #b91c1c;

  --ao-shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.05);
  --ao-shadow-md: 0 8px 24px rgba(15, 23, 42, 0.08);
  --ao-radius-sm: 8px;
  --ao-radius-md: 12px;
  --ao-radius-lg: 16px;
  --ao-radius-pill: 999px;

  --ao-space-1: 4px;
  --ao-space-2: 8px;
  --ao-space-3: 12px;
  --ao-space-4: 16px;
  --ao-space-6: 24px;
  --ao-space-8: 32px;
  --ao-space-12: 48px;

  --ao-max-prose: 760px;
  --ao-max-wide: 1120px;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ao-bg: #0b1120;
    --ao-surface: #0f172a;
    --ao-surface-muted: #1e293b;
    --ao-border: rgba(148, 163, 184, 0.18);
    --ao-border-strong: rgba(148, 163, 184, 0.32);

    --ao-text: #f8fafc;
    --ao-text-secondary: #cbd5e1;
    --ao-text-muted: #94a3b8;

    --ao-primary: #38bdf8;
    --ao-primary-hover: #7dd3fc;
    --ao-primary-fg: #082f49;
    --ao-primary-soft: rgba(56, 189, 248, 0.14);
    --ao-primary-text: #38bdf8;

    --ao-success: #34d399;
    --ao-success-soft: rgba(52, 211, 153, 0.14);
    --ao-success-text: #6ee7b7;

    --ao-warning: #fbbf24;
    --ao-warning-soft: rgba(251, 191, 36, 0.14);
    --ao-warning-text: #fde68a;

    --ao-danger: #f87171;
    --ao-danger-soft: rgba(248, 113, 113, 0.14);
    --ao-danger-text: #fca5a5;

    --ao-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.35);
    --ao-shadow-md: 0 12px 32px rgba(0, 0, 0, 0.45);
  }
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --ao-bg: #0b1120;
  --ao-surface: #0f172a;
  --ao-surface-muted: #1e293b;
  --ao-border: rgba(148, 163, 184, 0.18);
  --ao-border-strong: rgba(148, 163, 184, 0.32);

  --ao-text: #f8fafc;
  --ao-text-secondary: #cbd5e1;
  --ao-text-muted: #94a3b8;

  --ao-primary: #38bdf8;
  --ao-primary-hover: #7dd3fc;
  --ao-primary-fg: #082f49;
  --ao-primary-soft: rgba(56, 189, 248, 0.14);
  --ao-primary-text: #38bdf8;

  --ao-success: #34d399;
  --ao-success-soft: rgba(52, 211, 153, 0.14);
  --ao-success-text: #6ee7b7;

  --ao-warning: #fbbf24;
  --ao-warning-soft: rgba(251, 191, 36, 0.14);
  --ao-warning-text: #fde68a;

  --ao-danger: #f87171;
  --ao-danger-soft: rgba(248, 113, 113, 0.14);
  --ao-danger-text: #fca5a5;

  --ao-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.35);
  --ao-shadow-md: 0 12px 32px rgba(0, 0, 0, 0.45);
}

*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100dvh;
  background: var(--ao-bg);
  color: var(--ao-text);
  font-family: var(--ao-font-sans);
  font-size: 15px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 { margin: 0; line-height: 1.3; letter-spacing: -0.015em; text-wrap: balance; }
code, pre, .ao-mono { font-family: var(--ao-font-mono); }
.ao-num { font-variant-numeric: tabular-nums; }
a { color: var(--ao-primary-text); text-decoration: none; }
a:hover { text-decoration: underline; }
:focus-visible { outline: 2px solid var(--ao-primary); outline-offset: 2px; }

.ao-shell {
  width: 100%;
  max-width: var(--ao-max-prose);
  margin: 0 auto;
  padding: 20px 16px max(32px, env(safe-area-inset-bottom));
}
.ao-shell--wide { max-width: var(--ao-max-wide); }
.ao-stack { display: flex; flex-direction: column; gap: 20px; }

.ao-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 16px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--ao-border);
}

.ao-card {
  background: var(--ao-surface);
  border: 1px solid var(--ao-border);
  border-radius: var(--ao-radius-md);
  padding: 20px;
  box-shadow: var(--ao-shadow-sm);
}

.ao-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
}
.ao-grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.ao-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--ao-radius-pill);
  font-size: 12px;
  font-weight: 600;
  background: var(--ao-primary-soft);
  color: var(--ao-primary-text);
}
.ao-badge--success { background: var(--ao-success-soft); color: var(--ao-success-text); }
.ao-badge--warning { background: var(--ao-warning-soft); color: var(--ao-warning-text); }
.ao-badge--danger  { background: var(--ao-danger-soft);  color: var(--ao-danger-text); }
.ao-badge--neutral { background: var(--ao-surface-muted); color: var(--ao-text-secondary); }

.ao-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 10px 16px;
  border-radius: var(--ao-radius-sm);
  border: 1px solid var(--ao-border-strong);
  background: var(--ao-surface);
  color: var(--ao-text);
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 150ms ease, border-color 150ms ease, opacity 150ms ease;
}
.ao-btn:hover:not(:disabled) { background: var(--ao-surface-muted); }
.ao-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.ao-btn--primary { background: var(--ao-primary); border-color: transparent; color: var(--ao-primary-fg); }
.ao-btn--primary:hover:not(:disabled) { background: var(--ao-primary-hover); }
.ao-btn--danger { background: var(--ao-danger-soft); border-color: var(--ao-danger); color: var(--ao-danger-text); }

.ao-field { display: flex; flex-direction: column; gap: 6px; }
.ao-label { font-size: 13px; font-weight: 600; color: var(--ao-text-secondary); }
.ao-input, .ao-textarea, .ao-select {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border-radius: var(--ao-radius-sm);
  border: 1px solid var(--ao-border-strong);
  background: var(--ao-bg);
  color: var(--ao-text);
  font-family: inherit;
  font-size: 16px;
}
.ao-textarea { min-height: 96px; resize: vertical; }
.ao-input:focus, .ao-textarea:focus, .ao-select:focus {
  border-color: var(--ao-primary);
  outline: none;
  box-shadow: 0 0 0 3px var(--ao-primary-soft);
}

.ao-table-wrap {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--ao-border);
  border-radius: var(--ao-radius-md);
  background: var(--ao-surface);
}
.ao-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.ao-table th, .ao-table td {
  padding: 11px 14px;
  text-align: left;
  border-bottom: 1px solid var(--ao-border);
  white-space: nowrap;
}
.ao-table th { font-size: 12px; font-weight: 600; color: var(--ao-text-muted); background: var(--ao-surface-muted); }
.ao-table tr:last-child td { border-bottom: none; }

.ao-alert {
  padding: 12px 14px;
  border-radius: var(--ao-radius-sm);
  border: 1px solid var(--ao-border);
  background: var(--ao-surface-muted);
  font-size: 14px;
}
.ao-alert--success { background: var(--ao-success-soft); border-color: var(--ao-success); color: var(--ao-success-text); }
.ao-alert--warning { background: var(--ao-warning-soft); border-color: var(--ao-warning); color: var(--ao-warning-text); }
.ao-alert--danger  { background: var(--ao-danger-soft);  border-color: var(--ao-danger);  color: var(--ao-danger-text); }

details.ao-details {
  background: var(--ao-surface);
  border: 1px solid var(--ao-border);
  border-radius: var(--ao-radius-md);
  padding: 16px 20px;
}
details.ao-details summary { cursor: pointer; font-weight: 600; font-size: 14px; }

dialog.ao-dialog {
  width: min(460px, calc(100vw - 32px));
  padding: 24px;
  border: 1px solid var(--ao-border-strong);
  border-radius: var(--ao-radius-lg);
  background: var(--ao-surface);
  color: var(--ao-text);
  box-shadow: var(--ao-shadow-md);
}
dialog.ao-dialog::backdrop {
  background: rgba(2, 6, 23, 0.65);
  backdrop-filter: blur(3px);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
"""


def render_unlock_page(slug: str, title: str, error: str = "") -> str:
    safe_title = html.escape(title or slug)
    safe_slug = html.escape(slug)
    error_html = (
        f'<div class="err">{html.escape(error)}</div>' if error else ""
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Unlock · {safe_title}</title>
  <style>
    :root {{ color-scheme: dark light; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      padding: 20px;
    }}
    .card {{
      width: 100%;
      max-width: 380px;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 28px;
      box-shadow: 0 20px 45px rgba(0,0,0,0.35);
    }}
    .badge {{
      display: inline-block;
      font-size: 12px;
      font-weight: 600;
      color: #38bdf8;
      background: rgba(56,189,248,0.12);
      padding: 4px 10px;
      border-radius: 999px;
      margin-bottom: 12px;
    }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    p {{ margin: 0 0 20px; font-size: 14px; color: #94a3b8; }}
    input {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid #475569;
      background: #0f172a;
      color: #f8fafc;
      font-size: 15px;
      outline: none;
      margin-bottom: 14px;
    }}
    input:focus {{ border-color: #38bdf8; }}
    button {{
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 10px;
      background: #0ea5e9;
      color: #fff;
      font-weight: 600;
      font-size: 15px;
      cursor: pointer;
    }}
    button:hover {{ background: #0284c7; }}
    .err {{
      background: rgba(239,68,68,0.15);
      border: 1px solid rgba(239,68,68,0.4);
      color: #fca5a5;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 13px;
      margin-bottom: 14px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">AntOrbit · 受保护站点</div>
    <h1>{safe_title}</h1>
    <p>请输入访问密码以查看站点 <code>{safe_slug}</code>。</p>
    {error_html}
    <form method="post" action="/s/{safe_slug}/_unlock">
      <input type="password" name="password" placeholder="输入访问密码" autofocus required />
      <button type="submit">解锁访问</button>
    </form>
  </div>
</body>
</html>"""


def render_status_page(code: int, heading: str, message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{code} · {html.escape(heading)}</title>
  <style>
    body {{
      margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0; text-align: center; padding: 24px;
    }}
    .box {{ max-width: 420px; }}
    .code {{ font-size: 56px; font-weight: 800; color: #38bdf8; line-height: 1; }}
    h1 {{ font-size: 20px; margin: 12px 0 8px; }}
    p {{ font-size: 14px; color: #94a3b8; margin: 0; }}
  </style>
</head>
<body>
  <div class="box">
    <div class="code">{code}</div>
    <h1>{html.escape(heading)}</h1>
    <p>{html.escape(message)}</p>
  </div>
</body>
</html>"""
