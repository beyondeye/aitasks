---
priority: high
effort: medium
depends: [t519_5]
issue_type: documentation
status: Implementing
labels: [website, tmux, aitask_board, codebrowser, ait_settings, documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 15:17
updated_at: 2026-04-13 10:14
---

## Context

Part of t519 (website docs rewrite for tmux integration). This child covers two related pieces of work:

1. **Document the TUI switcher and tmux integration** across all main TUIs. The `j` shortcut opens a modal dialog (`.aitask-scripts/lib/tui_switcher.py`) that jumps between tmux windows running the known TUIs (board, monitor, minimonitor, codebrowser, settings, brainstorm). Each TUI's how-to page needs a new "tmux integration" section documenting this.

2. **Rename the footer binding label** from "Jump TUI" to "TUI switcher" in `.aitask-scripts/lib/tui_switcher.py`. This is the folded scope of t494 (which was merged into t519 during planning).

The `tuis/_index.md` overview also needs updating to introduce all the TUIs (including monitor and minimonitor added by t519_4 and t519_5) and the switcher as the unified navigation mechanism.

**Scope note:** The diffviewer TUI is **intentionally omitted** from all user-facing documentation per project direction (it will be integrated into brainstorm at a later stage). The TUI switcher currently lists diffviewer for functional reasons, but docs must not mention it.

## Key Files to Modify

**Docs:**
- `website/content/docs/tuis/_index.md` — update overview to introduce all TUIs and the switcher.
- `website/content/docs/tuis/board/how-to.md` — add "tmux integration" section.
- `website/content/docs/tuis/codebrowser/how-to.md` — add "tmux integration" section.
- `website/content/docs/tuis/settings/how-to.md` — add "tmux integration" section.
- If a `tuis/brainstorm/` docs directory exists, its how-to also gets a section. If not, note the gap for a future task.

**Code (folded t494 scope):**
- `.aitask-scripts/lib/tui_switcher.py` — rename the `j` binding's footer label from "Jump TUI" to "TUI switcher". Look around line 471-472 where the binding is defined.

## Reference Files for Patterns

- `.aitask-scripts/lib/tui_switcher.py` — the TUI switcher implementation. Read:
  - Lines 59–65: `KNOWN_TUIS` registry (board, monitor, codebrowser, settings, diffviewer — diffviewer excluded from docs).
  - Lines 199–454: modal overlay implementation.
  - Lines 426–443: switch logic (`tmux select-window` / `new-window`).
  - Lines 471–472: the `j` binding definition with the label to rename.
- `.aitask-scripts/board/aitask_board.py` line 2622 — `TuiSwitcherMixin` inheritance, example of integration.
- `.aitask-scripts/codebrowser/codebrowser_app.py` — another mixin user.
- `.aitask-scripts/settings/settings_app.py` — another mixin user.
- `website/content/docs/tuis/board/how-to.md` — structural model for the new "tmux integration" section.

## Implementation Plan

### Step 1 — Update `tuis/_index.md`

Rewrite the overview to:
- Introduce all documented TUIs: Board, Monitor, Minimonitor, CodeBrowser, Settings, Brainstorm (omit diffviewer).
- Add a section "Navigating between TUIs" explaining the `j` key and the TUI switcher dialog.
- Link each TUI to its subdirectory docs.
- Briefly mention that TUI switching requires running inside tmux, and link to `/docs/installation/terminal-setup/` for setup.
- HTML comment placeholder for the switcher dialog screenshot: `<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->`

Do **not** rename existing H2 headings on this page (if any) — Docsy auto-generates anchors that may be linked externally.

### Step 2 — Add "tmux integration" section to each TUI's how-to

For each of `tuis/board/how-to.md`, `tuis/codebrowser/how-to.md`, `tuis/settings/how-to.md`, append a new H2 section (do NOT modify existing headings):

```markdown
## tmux integration

When running inside tmux, you can jump to any other TUI (Board, Monitor, Minimonitor, CodeBrowser, Settings, Brainstorm) using the **TUI switcher**:

1. Press `j` to open the TUI switcher dialog.
2. Select the target TUI.
3. The switcher either jumps to an existing tmux window running that TUI or creates a new one.

<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->

The switcher is a built-in feature of all main TUIs (Board, Monitor, Minimonitor, CodeBrowser, Settings, Brainstorm). See [the Monitor docs](/docs/tuis/monitor/) for the full tmux-based workflow.
```

Customize the copy slightly for each TUI's context (e.g., on the codebrowser page, mention that reviewing a diff typically follows picking a task on the board and then jumping to codebrowser via `j`).

**If a `tuis/brainstorm/` docs directory exists**, add the same section there. Check with `ls website/content/docs/tuis/` during implementation. If it does not exist, note this as a gap (brainstorm docs are missing entirely — this is a separate scope outside t519).

### Step 3 — Rename footer label in `lib/tui_switcher.py` (folded t494 code change)

1. Open `.aitask-scripts/lib/tui_switcher.py`, find the `j` binding definition around line 471-472. It likely looks like:
   ```python
   Binding("j", "open_switcher", "Jump TUI", show=True),
   ```
2. Change `"Jump TUI"` to `"TUI switcher"`.
3. Grep for "Jump TUI" across the entire repo to catch any other references (snapshot tests, docs, comments):
   ```bash
   grep -rn "Jump TUI" .
   ```
   Update every match that's actually user-visible. Leave comments or historical notes alone if they're explanatory.

4. Grep for "jump_tui" (snake case) in case there's a method name or id — don't rename IDs/methods, only user-visible strings.

5. If there are snapshot tests that assert on the footer string, update the fixtures.

### Step 4 — Verification

- `ait board` in a tmux session → footer shows `j TUI switcher` (not "Jump TUI").
- `ait codebrowser` → same.
- `ait settings` → same.
- `ait monitor` → same.
- `ait minimonitor` → same.
- If brainstorm exists and uses the mixin, it also shows "TUI switcher".
- `cd website && hugo --gc --minify` builds cleanly with no broken links.
- `./serve.sh` — verify `/docs/tuis/` index renders correctly, each TUI's how-to shows the new section, links to other TUIs work.
- No grep matches remain for user-visible "Jump TUI" except in intentional historical notes.

## Notes for sibling tasks

This child runs last (auto-sibling deps → t519_6 after t519_5). It assumes t519_4 and t519_5 have created the monitor and minimonitor doc subdirectories, because `tuis/_index.md` links to them.

The diffviewer omission is deliberate and documented in the parent plan — do not add diffviewer to any doc list even though it appears in `KNOWN_TUIS`.

## Step 9 — Post-Implementation

Part of t519 — follow the shared task-workflow post-implementation flow. This is the final child of t519, so completion of this task leads directly to parent archival (which will also create the screenshot follow-up task).
