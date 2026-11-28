# AntOrbit Page Archetype Blueprints

Select the matching archetype below and follow its structural layout and interaction contract. All archetypes use the tokens and classes from [design-tokens.md](design-tokens.md).

---

## Archetype 1: Report / Analysis Briefing (`report`)

Best for: daily/weekly summaries, code/incident reviews, research notes, deployment changelogs pushed to phone.

### Required Structure
1. **Compact Header (`.ao-header`)**:
   - Status badge (`.ao-badge`) + concise `<h1>` + metadata line (date, author/source, reading scope).
   - Optional theme toggle button.
2. **Executive Summary Card (`.ao-card`) — First Viewport**:
   - 2–4 bullet takeaways or 3 compact summary metrics so a phone user grasps the conclusion immediately without scrolling.
3. **Collapsible Table of Contents** (for reports with >= 3 sections):
   - Use native `<details class="ao-card">` with `<summary>` and anchor links (`#sec-1`, `#sec-2`).
4. **Content Sections (`max-width: var(--ao-max-prose)`)**:
   - Clear `<h2>` / `<h3>` hierarchy, constrained prose, `.ao-table-wrap` around every table, `<pre><code>` with `overflow-x: auto` and `overflow-wrap: anywhere` for long URLs.
5. **Footer**: Generation timestamp and source context.

---

## Archetype 2: Dashboard / Metrics Console (`dashboard`)

Best for: monitoring snapshots, experiment comparisons, benchmark tables, interactive explorers.

### Required Structure
1. **Header (`.ao-header` inside `.ao-shell--wide`)**:
   - Title + dataset timestamp badge + compact filter/segmented controls (e.g., time range or category tabs).
2. **KPI Strip**:
   - Responsive grid: `grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px;`
   - Each KPI card shows: muted label (12px), primary figure (24–28px bold + `.ao-num`), and semantic delta badge (`.ao-badge--success` / `--danger` / neutral).
3. **Primary Visualization + Breakdown**:
   - Single column on `< 800px`, 2-column grid on desktop (`grid-template-columns: repeat(auto-fit, minmax(340px, 1fr))`).
   - Charts MUST use the AntOrbit palette (`#0284c7` / `#38bdf8` primary, `#059669` / `#34d399`, `#d97706` / `#fbbf24`, `#64748b` / `#94a3b8`) and readable axis labels in both light and dark modes.
4. **Detail Table (`.ao-table-wrap`)**:
   - Include client-side search/filter input (`font-size: 16px`) when rows > 10.
   - Numeric columns right-aligned with `.ao-num`.
   - Always render an explicit empty state row when filters match zero records.

---

## Archetype 3: Approval / Feedback Form (`approval-form`)

Best for: deployment approvals, design sign-offs, quick mobile surveys (`allow_submit=true`, optional `notify_on_submit=true`).

### Required Structure & State Machine
1. **Decision Context Card (Top)**:
   - Clearly summarize **what** is being approved/reviewed (key parameters, risk level badge, diff/link summary) before asking for input.
2. **Form (`<form novalidate>`)**:
   - Explicit `<label for="...">` on every field.
   - For approve/reject flows, use clear selectable radio cards or distinct primary/danger decision controls rather than ambiguous dropdowns.
   - Optional sticky mobile action bar with `padding-bottom: max(16px, env(safe-area-inset-bottom))`.
3. **Mandatory SDK Interaction Contract (`/_antorbit/sdk.js`)**:
   - Validate required fields inline (highlight missing field with `.ao-alert--danger`, no `alert()`).
   - Check `window.AntOrbit?.baseUrl` first; if missing (local preview), show a `.ao-alert--warning` banner instead of crashing.
   - Disable submit button + show `"提交中..."` while `window.AntOrbit.submit(payload)` is in flight.
   - On success: hide or lock the form and display a `.ao-alert--success` receipt containing **`#${res.id}`** and timestamp, plus an optional `"再次提交"` reset button if multiple submissions make sense.
   - On failure: re-enable the button and display the error message in `.ao-alert--danger` so the user can retry without losing typed input.

### Reference Submit Handler

```html
<script src="/_antorbit/sdk.js"></script>
<script>
  const form = document.getElementById('approval-form');
  const submitBtn = document.getElementById('submit-btn');
  const feedback = document.getElementById('feedback');

  function showBanner(kind, text) {
    feedback.className = 'ao-alert ao-alert--' + kind;
    feedback.textContent = text;
    feedback.hidden = false;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    feedback.hidden = true;

    const data = Object.fromEntries(new FormData(form).entries());
    if (!data.decision) {
      showBanner('danger', '请先选择审批意见。');
      return;
    }
    if (!window.AntOrbit || !window.AntOrbit.baseUrl) {
      showBanner('warning', '当前处于本地预览模式，发布到 AntOrbit 后即可真实提交。');
      return;
    }

    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';
    try {
      const res = await window.AntOrbit.submit({
        ...data,
        submittedAt: new Date().toISOString(),
      });
      showBanner('success', `已提交成功，回执编号 #${res.id}。`);
      form.reset();
    } catch (err) {
      showBanner('danger', `提交失败：${err.message || '请稍后重试'}`);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
  });
</script>
```

---

## Archetype 4: Interactive KV Utility (`kv-tool`)

Best for: shared checklists, live status boards, lightweight notes, sign-up lists (`kv_mode="read"` or `"readwrite"`).

### Required Structure & State Machine
1. **Header with Sync Status Pill**:
   - Show live sync status in a compact `.ao-badge`: `加载中…` / `已同步` / `保存中…` / `本地预览` / `同步失败`.
2. **Initial Hydration**:
   - On load, show a calm skeleton/loading state while calling `window.AntOrbit.kv.get(key)`.
   - If `window.AntOrbit?.baseUrl` is absent, gracefully fall back to `localStorage` with a visible `"本地预览模式（仅本机保存）"` badge so the tool remains testable locally.
3. **Write & Error Recovery (`kv_mode="readwrite"`)**:
   - Guard concurrent writes (serialize or disable conflicting controls during `kv.set`).
   - Show immediate feedback on save; if `kv.set` fails (e.g., `403` because `kv_mode` is read-only, or network offline), revert or mark unsaved and display an inline `.ao-alert--danger` with a retry button.
4. **Empty State**:
   - When the KV list is empty (`null` or `[]`), render a clean empty-state card with a clear next-step prompt.
