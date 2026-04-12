---
Task: t519_6_tui_switcher_docs_and_footer_label.md
Parent Task: aitasks/t519_rewrite_of_website_for_tmux_integration.md
Sibling Tasks: aitasks/t519/t519_1_*.md, aitasks/t519/t519_2_*.md, aitasks/t519/t519_3_*.md, aitasks/t519/t519_4_*.md, aitasks/t519/t519_5_*.md
Archived Sibling Plans: aiplans/archived/p519/p519_1_*.md, aiplans/archived/p519/p519_2_*.md, aiplans/archived/p519/p519_3_*.md, aiplans/archived/p519/p519_4_*.md, aiplans/archived/p519/p519_5_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan — t519_6: TUI switcher docs + folded t494 footer label change

## Goal

Final child of t519. Three deliverables:

1. Update `website/content/docs/tuis/_index.md` to introduce all TUIs (including monitor, minimonitor from t519_4/5) and the `j` TUI switcher as the unified navigation.
2. Add a "tmux integration" section to each main TUI's how-to page (board, codebrowser, settings, brainstorm).
3. Rename the footer label on the `j` binding from "Jump TUI" to "TUI switcher" in `.aitask-scripts/lib/tui_switcher.py` (this is the folded t494 code change).

**Important:** The diffviewer TUI must **not** appear in any documentation list. It is a transitional TUI that will be merged into brainstorm at a later stage. It still appears in the switcher's `KNOWN_TUIS` for functional reasons, but docs must omit it.

## Dependencies

- All previous children (t519_1 through t519_5). `tuis/_index.md` links to `tuis/monitor/` and `tuis/minimonitor/` which are created by t519_4 and t519_5.

## Step-by-step implementation

### Step 1 — Read archived sibling plans

```bash
cat aiplans/archived/p519/p519_4_*.md
cat aiplans/archived/p519/p519_5_*.md
```

Confirm the final URL paths of the monitor/minimonitor pages (they should be `/docs/tuis/monitor/` and `/docs/tuis/minimonitor/`).

### Step 2 — Verify source of truth for the switcher

```bash
cat .aitask-scripts/lib/tui_switcher.py
```

Confirm:
- The `KNOWN_TUIS` registry (around lines 59–65).
- The `j` binding definition (around lines 471–485) — note the exact label string to rename.
- Whether the mixin is used by brainstorm too — grep for `TuiSwitcherMixin`:

```bash
grep -rn "TuiSwitcherMixin" .aitask-scripts/
```

### Step 3 — Check for brainstorm docs

```bash
ls website/content/docs/tuis/brainstorm/ 2>/dev/null
```

If the directory exists, a "tmux integration" section will be added there too. If not, note this as a pre-existing gap and skip the brainstorm doc update.

### Step 4 — Update `tuis/_index.md`

**Preserve** front-matter (title, weight, description, and **any existing `aliases:`** — critical: do NOT remove aliases, Hugo fails on duplicate aliases and existing anchors may be linked externally).

Rewrite the body:

- **H2 Intro paragraph** — what TUIs are (terminal UIs built with Textual), and how they power the tmux-based ait IDE.
- **H2 Available TUIs** — list each one with a short one-sentence description and a link to its doc page. Order:
  1. **Monitor** — `/docs/tuis/monitor/` — tmux pane orchestrator / dashboard.
  2. **Minimonitor** — `/docs/tuis/minimonitor/` — narrow sidebar variant of monitor.
  3. **Board** — `/docs/tuis/board/` — kanban task board.
  4. **Code Browser** — `/docs/tuis/codebrowser/` — code navigation + diff review.
  5. **Settings** — `/docs/tuis/settings/` — configuration editor.
  6. **Brainstorm** — `/docs/tuis/brainstorm/` if docs exist; otherwise mention it in text without a link and note "docs pending".

   **Do not list diffviewer.** (It's in `KNOWN_TUIS` but deliberately undocumented.)

- **H2 Navigating between TUIs** — introduce the `j` shortcut:
  - Press `j` in any main TUI to open the TUI switcher dialog.
  - Select the target TUI.
  - The switcher either jumps to an existing tmux window or creates a new one.
  - This only works inside tmux — link to [Terminal Setup](/docs/installation/terminal-setup/) for setup instructions.
  - HTML comment placeholder: `<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->`

- **H2 Typical workflow** — short paragraph pointing users to `/docs/workflows/tmux-ide/` for the full daily walkthrough.

### Step 5 — Add "tmux integration" section to each main TUI how-to

For each of:
- `website/content/docs/tuis/board/how-to.md`
- `website/content/docs/tuis/codebrowser/how-to.md`
- `website/content/docs/tuis/settings/how-to.md`
- `website/content/docs/tuis/brainstorm/how-to.md` (only if the directory exists)

**Append** a new H2 section at the end (do NOT modify existing headings — Docsy anchors may be linked externally):

```markdown
## tmux integration

When running inside tmux, you can jump to any other main TUI using the **TUI switcher**:

1. Press `j` to open the TUI switcher dialog.
2. Select the target TUI (Board, Monitor, Minimonitor, Code Browser, Settings, Brainstorm).
3. The switcher either jumps to an existing tmux window running that TUI or creates a new one.

<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->

For the full tmux-based workflow, see [The tmux IDE workflow](/docs/workflows/tmux-ide/). If you haven't set up tmux yet, see [Terminal Setup](/docs/installation/terminal-setup/).
```

Adapt the lead-in for each TUI's context. For example, on the codebrowser page:

> When reviewing a diff produced by a code agent, you'll typically want to return to the board or monitor afterward. Press `j` to open the TUI switcher...

### Step 6 — Rename footer label in `lib/tui_switcher.py` (folded t494 code)

1. Open `.aitask-scripts/lib/tui_switcher.py`.
2. Locate the `j` binding around line 471–485. It looks something like:
   ```python
   BINDINGS = [
       ...
       Binding("j", "open_switcher", "Jump TUI", show=True),
       ...
   ]
   ```
3. Change `"Jump TUI"` → `"TUI switcher"`.
4. Search for other user-visible instances of "Jump TUI" across the repo:
   ```bash
   grep -rn "Jump TUI" .
   ```
   Update every user-visible match. Do NOT rename code identifiers, method names, or action names (`open_switcher` stays as-is). Only rename display strings.

5. Check for snapshot tests that might assert on the footer string:
   ```bash
   grep -rn "Jump TUI" tests/ .aitask-scripts/
   ```
   Update test fixtures if any.

### Step 7 — Verification

**Code verification:**

- `ait board` in tmux → footer shows `j TUI switcher` (not "Jump TUI").
- `ait codebrowser` in tmux → same.
- `ait settings` in tmux → same.
- `ait monitor` in tmux → same.
- `ait minimonitor` in tmux → same.
- `ait brainstorm` in tmux (if it uses the mixin) → same.
- Run relevant tests under `tests/` if any reference the label string.

**Docs verification:**

```bash
cd website && hugo --gc --minify
```

- No build errors, no broken links, no missing-image warnings.

```bash
cd website && ./serve.sh
```

- `/docs/tuis/` index lists all TUIs (minus diffviewer).
- Each main TUI's `/how-to/` page has the new "tmux integration" section.
- All cross-links resolve (to monitor, minimonitor, workflow page, terminal-setup).

### Step 8 — Final plan notes

Add Final Implementation Notes before archival:
- Confirm diffviewer was excluded from all docs.
- Note which TUIs got the "tmux integration" section (list of files modified).
- Any grep hits for "Jump TUI" that were updated (for traceability).
- Any snapshot tests updated.
- If brainstorm docs don't exist, note it as a pre-existing gap (not a regression).

## Files to modify

**Docs:**
- `website/content/docs/tuis/_index.md`
- `website/content/docs/tuis/board/how-to.md`
- `website/content/docs/tuis/codebrowser/how-to.md`
- `website/content/docs/tuis/settings/how-to.md`
- `website/content/docs/tuis/brainstorm/how-to.md` (if it exists)

**Code:**
- `.aitask-scripts/lib/tui_switcher.py` (label rename)
- Any snapshot tests referencing "Jump TUI" (if any)

## Out of scope

- Documenting diffviewer (deliberate exclusion).
- Renaming code identifiers or methods — only user-visible label strings.
- Creating brainstorm TUI docs from scratch if they don't exist.
- Screenshots (follow-up task created at parent archival time).
