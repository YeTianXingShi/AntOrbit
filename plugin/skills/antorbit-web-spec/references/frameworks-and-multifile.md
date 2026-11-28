# Multi-File Sites & Build Framework Guide (Vite / Vue / React / Tailwind)

Use this reference whenever the site has multiple files, local datasets/images, or uses a frontend build toolchain before publishing via `publish_site(directory=...)`.

## 1. Multi-File Vanilla Layout (No Build Step)

Recommended structure when splitting CSS, JS, or data files cleanly without Node/Vite:

```text
my-site/
├── index.html          # Entry page (must sit at directory root)
├── styles/
│   ├── tokens.css      # AntOrbit canonical tokens
│   └── main.css        # Page-specific styles
├── scripts/
│   └── app.js          # Use <script type="module" src="./scripts/app.js">
├── data/
│   └── report.json     # Fetch via fetch('./data/report.json')
└── assets/
    └── diagram.svg     # Reference via <img src="./assets/diagram.svg" alt="...">
```

Rules:
- Every `<link>`, `<script>`, `<img>`, `fetch()`, and internal `<a>` MUST be relative (`./...`), **never** `/styles/main.css` or `/data/report.json`.
- If the site has multiple HTML pages (e.g., `index.html` and `detail.html`), link via `./detail.html` and `./index.html`.
- Publish the root folder directly: `publish_site(directory="./my-site", ...)`.

## 2. Vite Configuration (Vue / React / Svelte / Vanilla TS)

AntOrbit hosts every site under `/s/<slug>/`. Vite's default `base: '/'` will break every JS/CSS bundle with 404s. Always configure `base: './'`:

```js
// vite.config.js / vite.config.ts
import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
})
```

### Additional Static Asset Rules in Vite
- Assets in `public/` MUST be referenced using `import.meta.env.BASE_URL + 'data.json'` or `'./data.json'`, **never** `'/data.json'`.
- Prefer importing images/JSON from `src/` so Vite fingerprints and bundles them with relative paths automatically.

## 3. Client-Side Routing Under `/s/<slug>/`

AntOrbit serves static files and falls back to `404` for unknown subpaths (it does not rewrite `/s/<slug>/deep/route` to `index.html`).

- **Always use Hash Routing**:
  - **Vue Router**: `createWebHashHistory()` (never `createWebHistory()`).
  - **React Router**: `createHashRouter()` or `<HashRouter>` (never `BrowserRouter`).
  - **Vanilla multi-view**: `window.location.hash` (`#/overview`, `#/details`).

## 4. AntOrbit SDK Integration in Framework Apps

Add the SDK tag in `index.html` (the single permitted root-absolute path):

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>Page Title · AntOrbit</title>
    <script src="/_antorbit/sdk.js"></script>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="./src/main.ts"></script>
  </body>
</html>
```

### TypeScript Declarations (`src/env.d.ts` or `src/antorbit.d.ts`)

```ts
export interface AntOrbitSubmitResult {
  id: number
  created_at: string
}

export interface AntOrbitKVEntry<T = unknown> {
  key: string
  value: T
  updated_at?: string
}

export interface AntOrbitSDK {
  slug: string
  baseUrl: string
  submit: (payload: unknown) => Promise<AntOrbitSubmitResult>
  kv: {
    list: () => Promise<AntOrbitKVEntry[]>
    get: <T = unknown>(key: string) => Promise<T | null>
    set: (key: string, value: unknown) => Promise<{ ok?: boolean }>
    delete: (key: string) => Promise<{ ok?: boolean }>
  }
}

declare global {
  interface Window {
    AntOrbit?: AntOrbitSDK
  }
}
```

### Safe Wrapper for Local Dev & Hosted Modes (`src/lib/antorbit.ts`)

```ts
export function isHostedOnAntOrbit(): boolean {
  return Boolean(window.AntOrbit && window.AntOrbit.baseUrl)
}

export async function safeSubmit(payload: unknown) {
  if (!isHostedOnAntOrbit()) {
    throw new Error('当前为本地预览模式，请发布到 AntOrbit 后再提交。')
  }
  return window.AntOrbit!.submit(payload)
}
```

## 5. External Libraries & Charting Policy

1. **Framework builds**: Install libraries via `npm` (`echarts`, `lucide-vue-next`, `lucide-react`, etc.) so everything is bundled locally into `dist/` with **zero runtime CDN dependency**.
2. **Single-file / Vanilla HTML**:
   - Prefer inline SVG for icons and simple charts (bar, sparkline, progress, donut).
   - Only when rich interactive charts (zoom, tooltip, multi-series) are explicitly needed, load a pinned version from a reliable CDN and provide a graceful fallback table/message if the script fails to load (`onerror`).
   - **Never** rely on Google Fonts or unpinned `@latest` CDN URLs.

## 6. Build & Publish Workflow

1. Run the production build (`npm run build` / `pnpm build`).
2. Inspect `dist/index.html` to confirm asset URLs start with `./assets/...` (not `/assets/...`).
3. Call `publish_site(directory="<abs-or-relative-path-to-dist>", title=..., slug=...)`.
   - Note: `antorbit-mcp` automatically skips `.git`, `node_modules`, `__pycache__`, and `.venv`, but always publish `dist/` directly — never upload raw source folders containing `node_modules` or unbuilt `.tsx`/`.vue` files.
