---
name: antorbit-web-spec
description: Enforce the unified AntOrbit Design System and modern web engineering standards whenever creating, refactoring, or auditing websites (single-file HTML, multi-file vanilla HTML/CSS/JS, or Vite/Vue/React/Tailwind apps) to be published on AntOrbit. Use whenever generating reports, dashboards, approval/feedback forms, KV tools, or interactive pages for AntOrbit so every site shares one cohesive Slate + Sky visual identity, strong mobile/CJK ergonomics, modern native web APIs, and safe /s/<slug>/ pathing.
---

# AntOrbit Web Specification — Unified Design & Engineering Contract

Every webpage generated for AntOrbit MUST look and feel like part of **one cohesive product family** (matching AntOrbit's Slate + Sky identity) rather than an improvised one-off design. Follow this specification strictly unless the user explicitly asks to override a specific visual element.

## 1. Architecture Mode Selection

Pick the lightest architecture that fits the task; do not add a build step for simple pages, and do not cram a complex multi-view app into a single 2,000-line HTML file.

| Scenario | Mode | Publishing Method |
| --- | --- | --- |
| Report, briefing, approval form, calculator, simple dashboard or KV tool | **Single-file HTML** (zero build, zero external deps) | `publish_site(html=..., ...)` |
| Multi-page static site, shared CSS/JS modules, or local images/JSON datasets | **Multi-file Vanilla** (`index.html`, `./styles.css`, `./app.js`, `./assets/`) | `publish_site(directory=..., ...)` |
| Rich stateful SPA, complex data tables, multi-chart console, or user requests Vue/React/Tailwind | **Framework Build** (Vite + Vue/React/Svelte + Tailwind CSS) | Build to `./dist`, then `publish_site(directory="./dist", ...)` |

For multi-file layouts, Vite/Tailwind setup, routing, and TypeScript SDK typings, read [frameworks-and-multifile.md](references/frameworks-and-multifile.md).

## 2. Strong Unified Visual System (Non-Negotiable)

All AntOrbit sites — whether pure HTML or Tailwind/Vite — MUST use the **AntOrbit Slate + Sky Design Tokens** defined in [design-tokens.md](references/design-tokens.md):

0. **Built-in Stylesheet vs. Inline CSS Rule**:
   - **Publishing directly to AntOrbit (default)**: Link the server-hosted stylesheet `<link rel="stylesheet" href="/_antorbit/ui.css">` and only write page-specific layout/component styles inline (drastically reduces HTML size and guarantees cross-site visual consistency).
   - **Standalone offline HTML** (when the user asks for a local file to double-click via `file://` without a server): Inline the canonical CSS block from [design-tokens.md](references/design-tokens.md) so the page renders identically offline.

1. **Palette & Adaptive Theme**:
   - **Neutral Slate surfaces** (`#f8fafc` / `#ffffff` in light mode; `#0b1120` / `#0f172a` / `#1e293b` in dark mode) + **Sky primary accent** (`#0284c7` light / `#38bdf8` dark).
   - Declare `color-scheme: light dark;` and automatically follow `prefers-color-scheme`. Optionally include a lightweight theme toggle persisted to `localStorage` (`ao-theme`) via `data-theme="light" | "dark"`.
   - Use semantic colors only for meaning: Success (Emerald), Warning (Amber), Danger (Rose), Info (Sky).
2. **Typography & CJK Ergonomics**:
   - Use the local system CJK-first font stack (`--ao-font-sans`) and monospace stack (`--ao-font-mono`). **Do NOT depend on Google Fonts or external font CDNs** (prevents blank/FOIT delays on mobile networks).
   - All numeric KPIs, table numbers, timestamps, and prices MUST use `font-variant-numeric: tabular-nums`.
   - Limit long-form prose line length to `65ch–72ch` with `line-height: 1.7`.
   - Use `text-wrap: balance` on headings and `overflow-wrap: anywhere` on long URLs/IDs/code blocks.
3. **Layout, Rhythm & Mobile First**:
   - Always include `<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">`.
   - Page container max-width: `760px` for reports/forms/tools, `1120px` for dashboards/tables.
   - Use an **8px spacing scale** (`4 / 8 / 12 / 16 / 24 / 32 / 48px`) and calm radii (`8px` controls, `12px` cards, `16px` modals/featured panels, `999px` badges).
   - **Notification-first hierarchy**: Most users open AntOrbit links from a phone push notification. The primary conclusion, KPI summary, or action area MUST appear in the first viewport without splash screens or decorative heroes.
   - **Safe Area & Touch Targets**: Fixed bottom bars MUST add `padding-bottom: max(16px, env(safe-area-inset-bottom))`. Interactive controls MUST be at least `40px` tall (`44px` preferred on mobile), and `<input>`/`<textarea>`/`<select>` MUST use `font-size: 16px` on mobile to prevent iOS Safari auto-zoom.
4. **Strict Anti-Patterns (Forbidden)**:
   - NO purple/neon/rainbow gradients, animated gradient blobs, or glassmorphism over busy backgrounds.
   - NO decorative stock illustrations, fake avatars, or non-functional placeholder buttons.
   - NO blocking `window.alert()`, `window.confirm()`, or `window.prompt()` for primary flows — use inline status banners, toast notifications, or native `<dialog>`.
   - NO horizontal page overflow at `375px` viewport width (wrap tables in `.ao-table-wrap` with `overflow-x: auto`).

Read [design-tokens.md](references/design-tokens.md) for the exact CSS variables, base component styles, and Tailwind v3/v4 token mapping.

## 3. Modern Web Platform & Accessibility Rules

Align with modern Baseline web platform standards (complementing `GoogleChrome/modern-web-guidance` and Vercel's `web-design-guidelines`):

- **Semantic HTML first**: Use `<header>`, `<main>`, `<nav>`, `<section>`, `<article>`, `<footer>`, `<button type="button|submit">`, `<label for="...">`, and native `<form>` submission. Never use clickable `<div>` or `<span>`.
- **Native UI primitives before JS libraries**:
  - Modals/confirmations → native `<dialog>` with `showModal()` and `::backdrop`.
  - Collapsible sections/FAQ → native `<details>` and `<summary>`.
  - Lightweight menus/tooltips → Popover API (`popover`, `popovertarget`) when supported, with simple fallback if needed.
  - Responsive components → CSS Grid (`repeat(auto-fit, minmax(..., 1fr))`) and `@container` queries.
- **Accessibility & Motion**:
  - Maintain WCAG AA contrast (`>= 4.5:1` for normal text, `>= 3:1` for large text and UI boundaries) in **both** light and dark modes.
  - Provide crisp `:focus-visible` outlines (`2px solid var(--ao-primary); outline-offset: 2px;`).
  - Every icon-only button MUST have `aria-label`.
  - Respect `@media (prefers-reduced-motion: reduce)` by disabling transitions/animations.
- **Resilient Assets & Self-Containment**:
  - Prefer inline SVG for icons (`width`/`height` explicit, `stroke="currentColor"`) and simple sparklines/bars.
  - Single-file HTML pages SHOULD work with **zero external CDN requests**. Only load a CDN library (e.g., ECharts for complex multi-series charts) when truly necessary, and render a clear fallback message or table if offline.

## 4. AntOrbit Runtime & Hosting Contract

Because every site is served under `/s/<slug>/`:

1. **Relative Paths Only**: All local assets, scripts, stylesheets, JSON fetches, and links MUST be relative (`./app.js`, `./assets/logo.svg`, `./data.json`). Never rely on root-absolute paths like `/assets/main.js` (even though AntOrbit can auto-rewrite HTML/CSS root paths at publish time, JS strings are not rewritten).
2. **Framework Builds**: Set `base: './'` in `vite.config.*` and prefer **hash routing** (`createWebHashHistory` / `HashRouter`). For SPA History routing fallback, AntOrbit automatically injects `<base href="/s/<slug>/">` on deep extensionless routes if no `<base>` tag is present.
3. **Built-in AntOrbit Assets**: The only allowed root-absolute paths are `/_antorbit/ui.css` (unified Slate + Sky stylesheet) and `/_antorbit/sdk.js` (whenever using `window.AntOrbit.submit()` or `window.AntOrbit.kv`).
4. **Inspect Publish Warnings**: After calling `publish_site`, always inspect `warnings` in the response (e.g., unbuilt source folder, JS root paths, missing SDK) and resolve any issues.
4. **Complete Async State Machine**: Every `submit()` or `kv` call MUST implement:
   - Client-side validation before sending.
   - Loading state (disable trigger button + spinner/label to prevent double submits).
   - Success feedback (e.g., receipt ID `#res.id` + timestamp) and error feedback with retry.
   - **Local preview guard**: Check `window.AntOrbit?.baseUrl` and show a clear notice if opened outside `/s/<slug>/` (e.g., `file://` or `localhost` preview) instead of throwing an unhandled error.

## 5. Page Archetype Blueprints

When building one of AntOrbit's 4 core page types, read [page-patterns.md](references/page-patterns.md) before writing code:
- **Report / Briefing** (`report`): Executive summary header → sticky/collapsible TOC → constrained prose + responsive tables.
- **Dashboard / Metrics** (`dashboard`): Filter bar → KPI metric grid (`tabular-nums`) → charts + sortable/scrollable detail table.
- **Approval / Feedback Form** (`approval-form`): Context summary → clear decision controls → comment field → `AntOrbit.submit` receipt state + duplicate-submit protection.
- **Interactive KV Utility** (`kv-tool`): Initial load skeleton → live interactive list/board → optimistic UI + `AntOrbit.kv.set` sync status indicator.

## 6. Mandatory Pre-Publish Checklist

Before calling `publish_site`, verify all 8 items:
1. [ ] Uses AntOrbit Slate + Sky tokens (`--ao-*`) and supports both light and dark modes with readable contrast.
2. [ ] Zero unintended root-absolute paths (only `/_antorbit/ui.css` and `/_antorbit/sdk.js`); Vite builds have `base: './'`, and `publish_site` returns no unresolved `warnings`.
3. [ ] Mobile-safe at `375px`: `viewport-fit=cover`, no horizontal page overflow, tables wrapped in horizontal scroll containers, form inputs `>= 16px`, bottom actions respect `env(safe-area-inset-bottom)`.
4. [ ] System CJK font stack used; no blocking Google Fonts or unnecessary external CDNs.
5. [ ] Numbers/metrics use `tabular-nums`; prose width constrained (`<= 72ch`).
6. [ ] Semantic HTML, accessible `<label>` / `aria-label`, and visible `:focus-visible` states; no `alert()`/`confirm()`.
7. [ ] All interactive controls work end-to-end with loading, empty, success, and error states (plus local preview guard for `window.AntOrbit`).
8. [ ] If using a build framework, `npm run build` succeeded cleanly and `publish_site` points to the built output directory (e.g., `dist/`).
