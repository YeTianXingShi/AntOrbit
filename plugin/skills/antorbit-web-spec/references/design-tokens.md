# AntOrbit Design Tokens & Base Component System

Use this token set across **all** AntOrbit websites (single-file HTML, multi-file CSS, and Tailwind/Vite apps) so every published page shares one recognizable, calm, high-contrast Slate + Sky identity.

> **Hosted vs. Offline Rule**:
> - For pages published directly to AntOrbit, prefer `<link rel="stylesheet" href="/_antorbit/ui.css">` — it serves this exact token & primitive stylesheet directly from the AntOrbit server with zero inline CSS bloat.
> - Only inline the CSS blocks below when generating a standalone offline HTML file intended to be opened locally via `file://` (or when binding Tailwind utilities in a framework build).

## 1. Canonical CSS Tokens (`tokens.css` or inline `<style>`)

Copy this block verbatim as the foundation of every pure HTML/CSS page (or import it in `src/styles/tokens.css` for multi-file/framework projects):

```css
:root {
  color-scheme: light dark;

  /* Fonts (Zero external CDN, CJK-first) */
  --ao-font-sans: system-ui, -apple-system, BlinkMacSystemFont, "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", "Segoe UI", Roboto, sans-serif;
  --ao-font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;

  /* Light Palette — Crisp Slate + Sky */
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

  /* Elevation & Geometry */
  --ao-shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.05);
  --ao-shadow-md: 0 8px 24px rgba(15, 23, 42, 0.08);
  --ao-radius-sm: 8px;
  --ao-radius-md: 12px;
  --ao-radius-lg: 16px;
  --ao-radius-pill: 999px;

  /* Spacing Scale (8px rhythm) */
  --ao-space-1: 4px;
  --ao-space-2: 8px;
  --ao-space-3: 12px;
  --ao-space-4: 16px;
  --ao-space-6: 24px;
  --ao-space-8: 32px;
  --ao-space-12: 48px;

  /* Layout Containers */
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
```

## 2. Standard Base Reset & Primitive Components

Include only the primitives your page uses, keeping the class naming and geometry consistent:

```css
*, *::before, *::after { box-sizing: border-box; }

html {
  -webkit-text-size-adjust: 100%;
  scroll-behavior: smooth;
}

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

h1, h2, h3, h4 {
  margin: 0;
  line-height: 1.3;
  letter-spacing: -0.015em;
  text-wrap: balance;
}

code, pre, .ao-mono { font-family: var(--ao-font-mono); }
.ao-num { font-variant-numeric: tabular-nums; }

a { color: var(--ao-primary-text); text-decoration: none; }
a:hover { text-decoration: underline; }

:focus-visible {
  outline: 2px solid var(--ao-primary);
  outline-offset: 2px;
}

/* Containers */
.ao-shell {
  width: 100%;
  max-width: var(--ao-max-prose);
  margin: 0 auto;
  padding: 20px 16px max(32px, env(safe-area-inset-bottom));
}
.ao-shell--wide { max-width: var(--ao-max-wide); }

/* Header */
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

/* Cards */
.ao-card {
  background: var(--ao-surface);
  border: 1px solid var(--ao-border);
  border-radius: var(--ao-radius-md);
  padding: 20px;
  box-shadow: var(--ao-shadow-sm);
}

/* Badges */
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

/* Buttons */
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

.ao-btn--primary {
  background: var(--ao-primary);
  border-color: transparent;
  color: var(--ao-primary-fg);
}
.ao-btn--primary:hover:not(:disabled) { background: var(--ao-primary-hover); }

.ao-btn--danger {
  background: var(--ao-danger-soft);
  border-color: var(--ao-danger);
  color: var(--ao-danger-text);
}

/* Form Controls (16px prevents iOS Safari zoom on focus) */
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

/* Responsive Tables */
.ao-table-wrap {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--ao-border);
  border-radius: var(--ao-radius-md);
  background: var(--ao-surface);
}
.ao-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.ao-table th, .ao-table td {
  padding: 11px 14px;
  text-align: left;
  border-bottom: 1px solid var(--ao-border);
  white-space: nowrap;
}
.ao-table th {
  font-size: 12px;
  font-weight: 600;
  color: var(--ao-text-muted);
  background: var(--ao-surface-muted);
}
.ao-table tr:last-child td { border-bottom: none; }

/* Alerts & Native Dialog */
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
```

## 3. Tailwind CSS Mapping (For Framework Projects)

When using Tailwind CSS (v3 or v4), **do NOT invent arbitrary colors** — bind Tailwind utilities directly to the `--ao-*` variables so light/dark adaptation and AntOrbit branding stay 100% identical to pure HTML pages.

### Tailwind v4 (`src/style.css`)

```css
@import "tailwindcss";
@import "./tokens.css";

@theme inline {
  --color-ao-bg: var(--ao-bg);
  --color-ao-surface: var(--ao-surface);
  --color-ao-muted: var(--ao-surface-muted);
  --color-ao-border: var(--ao-border);
  --color-ao-text: var(--ao-text);
  --color-ao-text-secondary: var(--ao-text-secondary);
  --color-ao-text-muted: var(--ao-text-muted);
  --color-ao-primary: var(--ao-primary);
  --color-ao-primary-hover: var(--ao-primary-hover);
  --color-ao-primary-fg: var(--ao-primary-fg);
  --color-ao-success: var(--ao-success);
  --color-ao-warning: var(--ao-warning);
  --color-ao-danger: var(--ao-danger);
  --font-sans: var(--ao-font-sans);
  --font-mono: var(--ao-font-mono);
}
```

### Tailwind v3 (`tailwind.config.js`)

```js
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx,vue,svelte}'],
  theme: {
    extend: {
      colors: {
        ao: {
          bg: 'var(--ao-bg)',
          surface: 'var(--ao-surface)',
          muted: 'var(--ao-surface-muted)',
          border: 'var(--ao-border)',
          text: 'var(--ao-text)',
          secondary: 'var(--ao-text-secondary)',
          'text-muted': 'var(--ao-text-muted)',
          primary: 'var(--ao-primary)',
          'primary-hover': 'var(--ao-primary-hover)',
          'primary-fg': 'var(--ao-primary-fg)',
          success: 'var(--ao-success)',
          warning: 'var(--ao-warning)',
          danger: 'var(--ao-danger)',
        },
      },
      fontFamily: {
        sans: ['var(--ao-font-sans)'],
        mono: ['var(--ao-font-mono)'],
      },
    },
  },
}
```

## 4. Optional Theme Toggle Snippet

If the page offers a manual light/dark switch (keep it compact in the header), use this consistent pattern:

```html
<button type="button" class="ao-btn" id="ao-theme-toggle" aria-label="切换明暗主题">
  主题
</button>
<script>
  (function () {
    const key = 'ao-theme';
    const root = document.documentElement;
    const saved = localStorage.getItem(key);
    if (saved === 'light' || saved === 'dark') root.dataset.theme = saved;
    const btn = document.getElementById('ao-theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const darkNow = root.dataset.theme
        ? root.dataset.theme === 'dark'
        : matchMedia('(prefers-color-scheme: dark)').matches;
      const next = darkNow ? 'light' : 'dark';
      root.dataset.theme = next;
      localStorage.setItem(key, next);
    });
  })();
</script>
```
