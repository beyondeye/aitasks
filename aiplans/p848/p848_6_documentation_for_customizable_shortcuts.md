---
Task: t848_6_documentation_for_customizable_shortcuts.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 19:12
---

# p848_6 — Website documentation for customizable shortcuts (verified)

## Context

`t848` made every TUI shortcut customizable. Children t848_1–t848_5 (+t848_9,
t848_10) shipped: a scope/action→key registry with override resolution, the
`(X)plore` label renderer, the in-TUI `?` editor modal, the Settings → Shortcuts
tab with export/import + lint, eager sub-scope registration, and case-aware
mnemonic labels. **t848_6** (this task) documents that customization layer on the
Hugo/Docsy website so users discover the `?` editor from any TUI's docs and find
the cross-TUI Shortcuts tab from the Settings page.

All content describes **current state only** (CLAUDE.md "Documentation Writing" —
no "previously"/"now"/"earlier" framings).

## Verify-mode findings (deltas from the on-disk p848_6 plan)

Confirmed against the live codebase + website (2026-05-31). The on-disk plan was
written before the siblings landed and carries several **factual errors**; these
corrections are folded into the steps below:

1. **Callout shortcode is wrong.** The plan uses Docsy `{{% alert %}}` and
   `{{< ref … >}}`. **Neither is used anywhere in this site** (grep: 0 hits for
   `{{% alert`, `{{< alert`, `{{% notice`, `{{< ref`). The established
   conventions are **`> **Note:** …` blockquotes** for callouts and
   **`{{< relref "…#anchor" >}}`** for internal links (e.g.
   `stats/_index.md:24`, `board/how-to.md:236`). → Use a **blockquote** callout
   with a `relref` link.

2. **Settings Shortcuts tab letter is `s`, not `k`.** `_TAB_SHORTCUTS`
   (`settings_app.py:159`) = `a/b/c/m/p/s/t` → Shortcuts is **`s`**.

3. **No dedicated Export/Import buttons on the tab.** CR3 in p848_5 removed them.
   The tab has only **(D) Reset scope** and **(L)int coherence** buttons.
   Export/import is the **general Settings Export (`e`) / Import (`i`)** flow's
   **"Shortcuts" category checkbox** — not a separate action.

4. **Export bundle is `.aitcfg.json` (JSON), not a tar/zst
   `aitasks_config_export_*` bundle.** (`config_utils.EXPORT_EXTENSION =
   ".aitcfg.json"`.) Selecting only "Shortcuts" in Export produces a bundle whose
   top-level `shortcuts` member is the `shortcuts:` subtree **only** (no email).
   Import **deep-merges** it into `userconfig.yaml`, preserving
   `email`/`last_used_labels`.

5. **`?` editor row actions are `Enter`/`r`/`d`/`s`/`Esc` with precise
   meanings:** `Enter` = rebind (key-capture), **`r` = revert the unsaved edit on
   the current row**, **`d` = reset to default (clear the override)**, `s` = save,
   `Esc` = cancel. Editor columns: **Scope · Action · Key · Default · Label ·
   Origin**. Saved rebinds apply on **next launch** (restart-to-apply; Textual
   8.2.7 does not live-rekey) — this must be documented.

6. **Settings tab table** columns are **Scope · Action · Current · Default ·
   Label · Origin**; `Enter` on a row opens the `?` editor modal scoped to that
   row's scope (the per-row r/d live inside the modal, not the tab).

7. **There is no brainstorm docs page.** `tuis/brainstorm/_index.md` does not
   exist; the only brainstorm mention is one line in `tuis/_index.md:24`
   ("Dedicated documentation is pending"). → **Drop** the planned brainstorm
   callout and the `?`→`H` op-help migration note — there is no page to host
   them, and brainstorm docs are explicitly pending. (The universal-`?` fact is
   still conveyed by the new cross-cutting section.)

8. **Per-TUI pages are multi-file** (`_index.md` + often `how-to.md` /
   `reference.md`); shortcuts frequently live in `reference.md`. The
   discoverability callout still belongs on each **`_index.md`** (the entry
   point every TUI has). `diffviewer` is omitted (transitional, per CLAUDE.md).

## Files

**Modified (10):**

- `website/content/docs/tuis/_index.md` — new "Customizing keyboard shortcuts"
  section.
- `website/content/docs/tuis/settings/_index.md` — new `### Shortcuts (s)`
  tab subsection + a `**s**` row in the Navigating table.
- Per-TUI `_index.md` discoverability callout (identical blockquote) on:
  `board/`, `monitor/`, `minimonitor/`, `codebrowser/`, `stats/`, `syncer/`,
  `applink/`.

## Step-by-step

### 1. Cross-cutting section in `tuis/_index.md`

Insert a new `## Customizing keyboard shortcuts` section after the
"Navigating between TUIs" section and before the closing `---` / **Next** footer.
Subsections (prose, current-state):

- **In any TUI** — press **`?`** to open the in-place editor (a `DataTable`;
  `Enter` rebinds via key capture, `r` reverts the unsaved edit, `d` resets to
  default, `s` saves, `Esc` cancels). It is filtered to that TUI's scope (plus
  the global `shared` actions). Saved rebinds apply **the next time you launch
  the TUI**.
- **Across TUIs** — link to the Settings Shortcuts tab:
  `[Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}})`
  for a single place to browse/edit every TUI's keys, reset a scope, lint
  cross-TUI coherence, and export/import.
- **Where customizations live** — `aitasks/metadata/userconfig.yaml` under the
  `shortcuts:` key (per-user, gitignored). Map is `shortcuts: <scope>:
  <action_id>: <key>`. Example (use the real action_ids verified from
  `tests/test_config_utils_shortcuts.py`):

  ```yaml
  email: you@example.com
  shortcuts:
    board:
      pick: o
    monitor:
      refresh: g
  ```

- **Labels** — button labels like `(P)ick` follow the current key; a rebind is
  reflected after the TUI restarts.
- **Coherence** — shared actions (e.g. the `j` TUI switcher, the `?` editor) keep
  the same key across TUIs; the Settings tab's **Lint coherence** button reports
  drift.

### 2. `### Shortcuts (s)` subsection in `settings/_index.md`

Add a new `### Shortcuts (s)` subsection under "## Understanding the Layout",
placed after `### Profiles (p)` and before `## Navigating`, matching the existing
per-tab style (`### Agent Defaults (a)` …). Auto-anchor = `shortcuts-s` (the
anchor the per-TUI callouts link to). Document:

- A single `DataTable` of every TUI's bindings, columns **Scope · Action ·
  Current · Default · Label · Origin** (Origin = `user` if overridden, else
  `default`).
- **Enter** on a row opens the in-place editor scoped to that row's scope (same
  modal as `?`); `r`/`d`/`s` live inside that editor.
- Buttons: **(D) Reset scope** (clears overrides for the selected row's scope,
  with a confirm) and **(L)int coherence** (reports cross-TUI mismatches for
  shared actions).
- **Export / Import of shortcuts is part of the general Export (`e`) / Import
  (`i`) flow**, not a tab button: tick the **"Shortcuts"** category. Export emits
  a focused `.aitcfg.json` whose top-level `shortcuts` member is the `shortcuts:`
  subtree only (no email). Import **deep-merges** it into `userconfig.yaml`,
  preserving `email`/`last_used_labels`.
- Rebinds apply on next launch (restart-to-apply).

Also update the layout intro: the page currently says the TUI "organizes
configuration into **five tabs**" and lists `a/b/c/m/p`. Adding Shortcuts (and
the already-shipped Tmux `t` tab) makes that count stale — change "five tabs" to
"tabs" (no hard number) to stay current-state-accurate, and add a
`| **s** | Switch to Shortcuts tab |` row to the Navigating table.

> **Out-of-scope note:** the Tmux tab (`t`) is also undocumented in
> `settings/_index.md`. It predates t848 and is unrelated to shortcuts —
> surfaced here as a candidate follow-up, not fixed in this task.

### 3. Per-TUI discoverability callout

Append the same blockquote callout to each per-TUI `_index.md`
(`board`, `monitor`, `minimonitor`, `codebrowser`, `stats`, `syncer`,
`applink`), placed near the page top (after the intro paragraph / before the
first `##`), so it is visible without scrolling:

```markdown
> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).
```

(Single source of truth for the full how-to is the `tuis/_index.md` section; the
callout is just the per-page pointer.)

## Verification

```bash
cd website && hugo build --gc --minify     # MUST build clean — Docsy fails the
                                            # build on unresolvable relref
grep -rl "Press \`?\`" content/docs/tuis/ | wc -l   # expect 7 per-TUI callouts
grep -rn "shortcuts-s" content/docs/tuis/           # cross-links present (7 + section)
grep -rn "Customizing keyboard shortcuts" content/docs/tuis/_index.md
./serve.sh   # spot-check rendered pages (handed to the t848_7 manual-verify sibling):
             #   /docs/tuis/                 → new section + working anchors
             #   /docs/tuis/settings/        → Shortcuts (s) subsection + nav row
             #   /docs/tuis/{board,monitor,…}/ → callout visible, link resolves
```

Anchor note: `relref` only validates the *page* exists (build-fatal if not); the
`#shortcuts-s` fragment is appended literally, so confirm it matches the rendered
heading id in `serve.sh` (Goldmark anchorizes `### Shortcuts (s)` → `shortcuts-s`).

## Notes for sibling tasks

t848_7 (manual verification) is the only remaining sibling — its checklist covers
the rendered-page / working-link checks above. No code/behavior changes here.

## Step 9 — Post-implementation

Standard child-task archival (`./.aitask-scripts/aitask_archive.sh 848_6`). On the
verify path, a `plan_verified` entry is appended to this plan before commit.
