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
