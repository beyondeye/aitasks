---
Task: t892_add_to_main_features_workflows.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Add "AI-enhanced workflows" highlight feature to the homepage

## Context

The aitasks website homepage (`website/content/_index.md`) currently shows
**3 highlighted features** in a single row near the top:

1. "Agentic IDE in your terminal" (`fa-terminal`)
2. "Long-term memory for agents" (`fa-brain`)
3. "Tight git coupling, AI-enhanced" (`fa-code-branch`) — will be renamed to just
   "Tight git coupling" to avoid repeating "AI-enhanced" alongside the new 4th feature.

The user wants to add a **4th highlight — "AI-enhanced workflows"** — that links
to the main workflows page (`/docs/workflows/`).

Each highlight uses the Docsy `blocks/feature` shortcode, which **hardcodes
`col-lg-4`** (3 per row) in the theme module
(`docsy@v0.14.3/layouts/_shortcodes/blocks/feature.html`). Simply adding a 4th
block would wrap it to a lone, left-aligned second row (3 + 1). The user chose a
balanced **2×2 grid** instead, which requires widening the highlight columns to
`col-lg-6` — but only for these 4 blocks, **not** for the 3-OS row
(Linux/macOS/Windows) further down the page, which also uses `blocks/feature`
and must stay at 3-across.

## Approach

Add an optional, backwards-compatible `col` parameter to a **local override** of
the `blocks/feature` shortcode (default `col-lg-4`, so all existing untouched
call-sites are unaffected), then pass `col="col-md-6 col-lg-6"` to the 4
highlight features to produce the 2×2 grid.

### Blast-radius / cleanliness assessment

- **Override scope:** `blocks/feature` is used in exactly **two** places, both on
  the homepage — the highlight row and the OS row. The override keeps the
  `col-lg-4` default, so the OS row renders identically. Only the 4 blocks that
  explicitly pass `col=` change. The new param is opt-in and additive.
- **Trade-off (pinning):** A local override pins this copy of `feature.html`, so
  future Docsy updates to that template won't flow through automatically. The
  template is tiny (~13 lines) and stable; this is an accepted, low-cost trade.
  The alternative (section-scoped CSS targeting `nth` section) was rejected as
  more fragile — the section has no unique id/class to anchor on, and it would
  silently break if section order changes.
- **"Someone edits this unaware":** The override is a faithful copy of the v0.14.3
  template with one parameterized line; a comment at the top will record that it
  exists solely to add the `col` param and otherwise mirrors upstream.

## Files to modify

### 1. NEW: `website/layouts/shortcodes/blocks/feature.html` (local shortcode override)

Faithful copy of `docsy@v0.14.3/layouts/_shortcodes/blocks/feature.html` with one
change: read an optional `col` param (default `col-lg-4`) and use it for the
column `<div>` class. Add a header comment noting it mirrors upstream and exists
only to expose the `col` param.

```go-html-template
{{/* Local override of Docsy's blocks/feature shortcode (mirrors docsy v0.14.3).
     Sole change: optional `col` param (default col-lg-4) for the column width,
     so the homepage highlight row can render 2x2 (col-lg-6) without affecting
     other call-sites. Keep in sync with upstream on Docsy upgrades. */ -}}
{{ $icon := .Get "icon" | default "fa-lightbulb" -}}
{{ $col := .Get "col" | default "col-lg-4" -}}
<div class="{{ $col }} mb-5 mb-lg-0 text-center">
<div class="mb-4 h1">
  <i class="{{ if not (or (hasPrefix $icon "fas ") (hasPrefix $icon "fab ")) }}fas {{ end }}{{ $icon }}"></i>
</div>
<h4 class="h3">
  {{- .Get "title" | markdownify -}}
</h4>
<div class="mb-0">
{{ .Inner }}
</div>
{{ with .Get "url" }}<p><a href="{{ . }}">{{ with $.Get "url_text" }}{{ . }}{{ else }}{{ T "ui_read_more" }}{{ end }}</a></p>{{ end }}
</div>
```

> Note: project's existing custom shortcodes live in `layouts/shortcodes/`, so the
> override goes there. During verification, confirm Hugo actually shadows the
> module's `_shortcodes/` copy (grep rendered HTML for `col-lg-6`); if it does not
> take effect, move the file to `website/layouts/_shortcodes/blocks/feature.html`.

### 2. EDIT: `website/content/_index.md` (the highlight row, lines 20–34)

- Add `col="col-md-6 col-lg-6"` to **all 3 existing** highlight feature blocks
  (so the grid is uniform 2×2, not mixed widths).
- **Rename the git feature** from `title="Tight git coupling, AI-enhanced"` to
  `title="Tight git coupling"` — avoids repeating "AI-enhanced" now that the new
  4th feature carries that phrasing. (URL/icon/body unchanged.)
- Add a **4th** feature block:

```
{{% blocks/feature icon="fa-arrows-spin" title="AI-enhanced workflows" url="/docs/workflows/" col="col-md-6 col-lg-6" %}}
End-to-end guides that combine the CLI tools and agent skills into repeatable flows — task decomposition, parallel development, code review, QA, and releases.
{{% /blocks/feature %}}
```

Leave the OS row (`fab fa-linux` / `fa-apple` / `fa-windows`, lines ~123–137)
**unchanged** — no `col=` param, stays 3-across.

## Verification

1. Build the site:
   ```bash
   cd website && hugo build --gc --minify
   ```
   Must complete without errors.
2. Confirm the override is active and the 2×2 widths rendered:
   ```bash
   grep -o 'col-md-6 col-lg-6' website/public/index.html | head
   ```
   Expect 4 matches (one per highlight feature). If 0 matches, the override
   didn't shadow the module — move it to `layouts/_shortcodes/blocks/feature.html`
   and rebuild.
3. Confirm the OS row is untouched — the page should still contain the 3-OS
   `col-lg-4` blocks (the Linux/macOS/Windows section renders 3-across).
4. Visually (optional): `cd website && ./serve.sh`, open the homepage, confirm
   the 4 highlights form a balanced 2×2 on desktop and that "AI-enhanced
   workflows" links to `/docs/workflows/`.

## Post-Implementation

Follow **Step 8** (user review/approval) → **Step 9** (commit; this is a
`documentation` task → commit message `documentation: ... (t892)`; no branch was
created so no merge/worktree cleanup) → archival via
`./.aitask-scripts/aitask_archive.sh 892`.

Per the project skill conventions: this homepage change is Claude-Code-side
website content (not a skill), so no parallel agent-skill ports are needed.

## Post-Review Changes

### Change Request 1 (2026-06-01)
- **Requested by user:** Drop the "End-to-end guides that" lead-in from the new
  feature's body; start it at "Combine the CLI tools and agent skills …".
- **Changes made:** Edited the 4th feature body in `_index.md` to
  "Combine the CLI tools and agent skills into repeatable flows — task
  decomposition, parallel development, code review, QA, and releases."
- **Files affected:** `website/content/_index.md`
- Also during review: renamed the 3rd feature title "Tight git coupling,
  AI-enhanced" → "Tight git coupling" to avoid repeating "AI-enhanced".

### Change Request 2 (2026-06-01)
- **Requested by user:** "Combine CLI tools", not "Combine the CLI tools".
- **Changes made:** Dropped "the" — body now starts "Combine CLI tools and agent
  skills into repeatable flows — …".
- **Files affected:** `website/content/_index.md`

### Change Request 3 (2026-06-01)
- **Requested by user:** "repeatable workflows", not "repeatable flows".
- **Changes made:** Body now reads "Combine CLI tools and agent skills into
  repeatable workflows — task decomposition, parallel development, code review,
  QA, and releases."
- **Files affected:** `website/content/_index.md`

## Final Implementation Notes
- **Actual work done:** Added a local Docsy `blocks/feature` shortcode override
  (`website/layouts/shortcodes/blocks/feature.html`) exposing an optional `col`
  param (default `col-lg-4`), and edited `website/content/_index.md` to add a 4th
  homepage highlight ("AI-enhanced workflows" → `/docs/workflows/`, icon
  `fa-arrows-spin`), widen all 4 highlights to `col-md-6 col-lg-6` (2×2 grid), and
  rename "Tight git coupling, AI-enhanced" → "Tight git coupling".
- **Deviations from plan:** None structurally. Final feature body wording iterated
  during review (see Post-Review Changes): "Combine CLI tools and agent skills into
  repeatable workflows — task decomposition, parallel development, code review, QA,
  and releases."
- **Issues encountered:** None. The `layouts/shortcodes/` location successfully
  shadows the Docsy module's `_shortcodes/blocks/feature.html` — verified via
  `hugo build` + grep of `public/index.html` (4 × `col-md-6 col-lg-6`, OS row
  unchanged at 3 × `col-lg-4`). No fallback to `_shortcodes/` needed.
- **Key decisions:** 2×2 grid via a backwards-compatible shortcode param (opt-in,
  default unchanged) rather than section-scoped CSS — keeps the OS row untouched
  and avoids fragile `nth`-section selectors.
- **Upstream defects identified:** None.
