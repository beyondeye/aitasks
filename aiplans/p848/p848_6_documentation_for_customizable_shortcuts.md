---
Task: t848_6_documentation_for_customizable_shortcuts.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_1_*.md, aitasks/t848/t848_2_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_5_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_6 — Website documentation for customizable shortcuts

## Goal

Document the new customization layer in the Hugo/Docsy site:
- New cross-cutting section in `tuis/_index.md`.
- Shortcuts tab subsection in `tuis/settings/_index.md`.
- Discoverability callout on every per-TUI page.

All content describes current state only (per CLAUDE.md
"Documentation Writing" rule).

## Files

**Modified:**

- `website/content/docs/tuis/_index.md`
- `website/content/docs/tuis/settings/_index.md`
- `website/content/docs/tuis/board/_index.md`
- `website/content/docs/tuis/monitor/_index.md`
- `website/content/docs/tuis/minimonitor/_index.md`
- `website/content/docs/tuis/codebrowser/_index.md`
- `website/content/docs/tuis/stats/_index.md`
- `website/content/docs/tuis/syncer/_index.md`
- `website/content/docs/tuis/applink/_index.md`
- (Brainstorm doc if present — note the `?` → `H` op-help migration)

## Step-by-step

### 1. Identify the Docsy alert/callout shortcode

```bash
grep -rn "{{% alert %}}" website/content/ | head -5
grep -rn "{{< alert" website/content/ | head -5
grep -rn "{{% notice" website/content/ | head -5
```

Use whichever shortcode is already in use in the site. Fall back to a
plain `> **Customizable keys:** …` blockquote if no alert shortcode is
configured.

### 2. `tuis/_index.md` — new section

Insert after the TUI inventory, before per-TUI links. Suggested heading
`## Customizing keyboard shortcuts` with three subsections:

- **In any TUI** — `?` opens the in-place editor (DataTable, Enter to
  rebind, r to reset, d to clear, s to save). Filter scoped to that
  TUI.
- **Across TUIs** — link to `tuis/settings/#shortcuts-tab`. Mention
  Export / Import.
- **Where the file lives** — `aitasks/metadata/userconfig.yaml` under
  the `shortcuts:` key (per-user, gitignored). Example block:

  ```yaml
  email: user@example.com
  shortcuts:
    board:
      pick_task: o
    monitor:
      send_enter: space
  ```

- **Coherence** — `quit`, `tui_switcher`, `refresh`,
  `shortcuts_editor` should stay aligned across TUIs; the Settings
  tab's Lint button surfaces drift.

### 3. `tuis/settings/_index.md` — Shortcuts tab section

Insert in the natural ordering alongside the other tabs. Heading
`## Shortcuts tab` (anchor `#shortcuts-tab`). Document:

- Tab letter `k`.
- DataTable columns (Scope, Action, Current, Default, Label, Origin).
- Row actions (Enter / r / d).
- Buttons: Reset scope · Export shortcuts · Import shortcuts · Lint
  coherence.
- Export semantics: produces a focused bundle containing only the
  `shortcuts:` section of `userconfig.yaml`.
- Import semantics: merges into current overrides.
- Note: standard Settings → Export already includes shortcuts because
  they live in `userconfig.yaml`; the focused Export is for sharing
  just the keys.

### 4. Per-TUI callout

Identical block on each per-TUI page (board / monitor / minimonitor /
codebrowser / stats / syncer / applink), placed under the page's
"Keyboard shortcuts" section if present, otherwise at the end:

```
{{% alert %}}
**Customizable keys:** every shortcut on this page can be rebound. Press
`?` in this TUI for the in-place editor, or visit
[Settings → Shortcuts]({{< ref "/docs/tuis/settings#shortcuts-tab" >}}).
{{% /alert %}}
```

For the brainstorm page (if it exists) additionally note that
operation help moved from `?` to `H` so the universal `?` shortcut can
open the editor.

## Verification

```bash
cd website && hugo --gc --minify          # site builds cleanly
./serve.sh                                # browse the touched pages
grep -rn "Press \`?\`" website/content/docs/tuis/ | wc -l   # expect >= per-TUI page count
grep -rn "shortcuts-tab" website/content/docs/tuis/         # cross-link present
```

## Verification (for the t848_7 manual-verification sibling)

- `/docs/tuis/` renders the "Customizing keyboard shortcuts" section
  with working anchor links.
- `/docs/tuis/settings/` renders the Shortcuts tab section with
  working internal links.
- Every per-TUI page shows the callout.
- All internal links resolve (no broken `ref`s in the build).

## Step 9 — Post-implementation

Standard archival.
