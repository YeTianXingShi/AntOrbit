---
name: antorbit
description: Publish static or interactive websites (reports, dashboards, prototypes, approval/feedback forms) to a self-hosted AntOrbit server for remote access under /s/<slug>/, inspect submissions or KV state, and push mobile notifications via Bark or ntfy. Use whenever the user asks to put a generated webpage online, share a remote link, collect web form feedback/approvals, or push notifications to their phone/channels.
---

# AntOrbit — Online Site Publishing & Push Notifications

Use the `antorbit` MCP server tools to deploy websites to the user's self-hosted AntOrbit server and send notifications via configured Bark or ntfy channels.

## Core Rules for Generated Websites (CRITICAL)

Because AntOrbit serves every site under a path prefix (`/s/<slug>/`):

1. **Always use relative paths for site assets and links**:
   - Use `./app.js`, `./styles.css`, `assets/logo.png`, or inline CSS/JS.
   - **Never** use root-absolute paths like `/assets/app.js` or `/style.css` — they will 404 under `/s/<slug>/`.
   - If building with Vite/React/Vue, set `base: './'` before running `npm run build`.
2. **The one allowed root-absolute script is the built-in AntOrbit SDK**:
   ```html
   <script src="/_antorbit/sdk.js"></script>
   ```
   Include this tag whenever the page needs form submission or KV state persistence.
3. **Mobile-friendly by default**: Users frequently open published pages directly from Bark/ntfy mobile notifications. Always include `<meta name="viewport" content="width=device-width, initial-scale=1.0">` and responsive CSS.

## Built-in Interactive SDK (`/_antorbit/sdk.js`)

When a site is published with `allow_submit=true` and/or `kv_mode="read" | "readwrite"`, `window.AntOrbit` is ready to use with zero configuration:

### 1. Submitting Forms / Approvals (`allow_submit=true`)

```html
<script src="/_antorbit/sdk.js"></script>
<script>
  async function handleApprove(decision, note) {
    const res = await window.AntOrbit.submit({
      decision,
      note,
      submittedAt: new Date().toISOString()
    });
    alert('已提交，编号 #' + res.id);
  }
</script>
```

- Set `notify_on_submit=true` (and optionally `notify_channel`) when publishing if the user should get a push alert whenever a submission arrives.
- Retrieve submissions later via `get_submissions(slug=...)`.

### 2. Lightweight JSON KV Store (`kv_mode="read"` or `"readwrite"`)

```html
<script src="/_antorbit/sdk.js"></script>
<script>
  // Read a key (returns null if not set yet)
  const checklist = (await window.AntOrbit.kv.get('checklist')) || [];

  // Write JSON value (requires kv_mode="readwrite")
  await window.AntOrbit.kv.set('checklist', [...checklist, { text: 'Done', ok: true }]);

  // List all keys
  const allItems = await window.AntOrbit.kv.list();
</script>
```

- Keep `kv_mode="off"` for plain read-only pages. Only enable `"readwrite"` when visitors need to save state directly from the browser.
- You can also seed or inspect KV entries directly from Ant via `kv_set`, `kv_get`, `kv_list`, and `kv_delete`.

## Publishing Workflows

### Quick Single-File Page
Use `publish_site(html=..., title=..., slug=...)` when a self-contained HTML page is enough (reports, dashboards, interactive calculators, approval forms).

### Multi-File / Built SPA Directory
1. Build or write the site into a local directory containing `index.html` (and relative assets).
2. Call `publish_site(directory="/abs/or/relative/path", title=..., slug=...)`.
   - The local MCP server zips the directory automatically (skipping `.git`, `node_modules`, `__pycache__`, `.venv`).
3. Re-publishing with the same `slug` overwrites static files in place while **preserving** existing form submissions and KV data.

### Security & Lifecycle Options
- `slug`: Omit to auto-generate an unguessable random slug, or pass a memorable lowercase slug (`my-report`).
- `password`: Set an access password for sensitive pages (server renders a clean unlock screen and sets a site-scoped `HttpOnly` cookie).
- `ttl_hours`: Set automatic expiration in hours (e.g., `24`, `168`). Omit or `0` for permanent hosting.

## Notification Pushing Workflows

1. **Publish + Push in one step**: Pass `notify_on_publish=true` to `publish_site` (optionally with `notify_title`, `notify_body`, `notify_channel`, `notify_level`, `notify_group`). The pushed notification automatically attaches the hosted site URL so tapping it opens the page immediately.
2. **Standalone Push**: Call `send_notification(title=..., body=..., url=..., channel=..., level=..., group=...)` when finishing a long task, alerting on errors, or sending reminders.
3. **Discovering Channels**: Call `list_channels()` to see available named channels (`bark` / `ntfy`) before picking a specific `channel`; omit `channel` to use the server's default channel.
4. **Priority Levels**:
   - `passive`: low-priority / silent info
   - `active`: standard notification (default)
   - `timeSensitive`: important / needs prompt attention
   - `critical`: urgent alert

## Error Handling
- If a tool reports missing `ANTORBIT_URL` or `ANTORBIT_API_KEY`, instruct the user to fill them in their plugin's `mcp_config.json`.
- Always return the clickable published URL (`site.url`) clearly in your response to the user.
