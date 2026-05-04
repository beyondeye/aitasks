---
priority: high
effort: medium
depends: [t745_1]
issue_type: enhancement
status: Ready
labels: [ait_brainstorm]
created_at: 2026-05-04 22:22
updated_at: 2026-05-04 22:22
---

## Context

Sibling of t745. Addresses parent issue 5: there is no integration with the existing diffviewer TUI. Pressing `Shift+D` on the Compare tab today launches `subprocess.Popen(["diff", ...])` — a backgrounded process the user can't see. This task replaces that subprocess call with a properly pushed `DiffViewerScreen` Textual screen that opens inside the brainstorm app, with full color, navigation, and mode-switching.

User-confirmed design decision: push `DiffViewerScreen` inside brainstorm via `push_screen` (single tmux session model — see CLAUDE.md "Single tmux session per project"). Do NOT spawn a new tmux window.

This task is INDEPENDENT of t745_2 and t745_3 — depends only on t745_1.

## Dependency

Requires t745_1 (the `_TAB_SCOPED_ACTIONS` registry — this task adds a new entry to it).

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BrainstormApp.BINDINGS` (lines 1512–1523) — add `Binding("D", "compare_diff", "Diff")`.
  - `_TAB_SCOPED_ACTIONS` (added in t745_1) — add entry `"compare_diff": "tab_compare"`.
  - `on_key()` (lines 1778–1795) — REMOVE the existing `Shift+D` handler block. The replacement is now driven by the new Binding + action.
  - Add new method `action_compare_diff(self) -> None`.
- `.aitask-scripts/aitask_brainstorm.sh` — confirm sys.path includes `.aitask-scripts/` so `from diffviewer.diff_viewer_screen import DiffViewerScreen` works. If it does not, add the parent directory to PYTHONPATH or `sys.path` insertion in the script.

## Reference Files for Patterns

- `.aitask-scripts/diffviewer/diff_viewer_screen.py:64-78` — `DiffViewerScreen.__init__(main_path: str, other_paths: list[str], mode: str = "classical")` signature.
- `.aitask-scripts/diffviewer/diff_viewer_screen.py:67-76` — Screen BINDINGS including `Escape` to dismiss.
- `.aitask-scripts/brainstorm/brainstorm_app.py:1778-1795` — current `Shift+D` handler to be removed.

## Implementation Plan

1. Read the t745_1 archived plan to confirm the `_TAB_SCOPED_ACTIONS` registry shape and how to add an entry.
2. Remove the current `Shift+D` handler from `on_key()` (lines 1778–1795). Make sure no other handler depends on its early-return.
3. Add to `BINDINGS`: `Binding("D", "compare_diff", "Diff")`.
4. Register `"compare_diff": "tab_compare"` in `_TAB_SCOPED_ACTIONS`.
5. Add `action_compare_diff(self) -> None`:
   ```python
   def action_compare_diff(self) -> None:
       nodes = getattr(self, "_compare_nodes", None)
       if not nodes or len(nodes) < 2:
           self.notify(
               "Pick nodes to compare first (press 'r')",
               severity="warning",
           )
           return
       n1, n2 = nodes[:2]
       p1 = self.session_path / "br_proposals" / f"{n1}.md"
       p2 = self.session_path / "br_proposals" / f"{n2}.md"
       missing = [p for p in (p1, p2) if not p.is_file()]
       if missing:
           self.notify(
               f"Proposal file missing: {missing[0].name}",
               severity="warning",
           )
           return
       from diffviewer.diff_viewer_screen import DiffViewerScreen
       self.push_screen(
           DiffViewerScreen(str(p1), [str(p2)], mode="classical")
       )
   ```
6. Verify the import path: launch `aitask_brainstorm.sh 635` and press `D` after picking 2 nodes. If the import fails, fix the launcher so `.aitask-scripts/` is on sys.path. The diffviewer app currently does this in its own launcher (see `aitask_diffviewer.sh`).

## Verification Steps

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635`.
- Switch to the Compare tab. Footer should now show `D Diff` (and `r Regenerate` once t745_2 lands).
- With NO nodes picked yet, press `D` — receive a warning notification, no screen pushed.
- Pick `n000` and `n001` from the modal. Press `D` — `DiffViewerScreen` pushes onto the screen stack. The two proposal markdown files diff correctly with color.
- Inside diffviewer: mode-switch (`m`), unified view (`u`), layout toggle (`v`), navigation (`n`/`p`) all behave as expected.
- Press `Escape` — back on the Compare tab with the dimension matrix still visible.
- Switch to the Dashboard tab — `D Diff` no longer appears in the footer.
- Run shellcheck if `aitask_brainstorm.sh` was modified: `shellcheck .aitask-scripts/aitask_brainstorm.sh`.

## Notes for sibling tasks

- The pushed-screen pattern (rather than tmux window spawn) avoids breaking the single-tmux-session-per-project invariant from CLAUDE.md.
- If a future task wants to launch the standalone diffviewer TUI from brainstorm (e.g., to compare against a non-proposal file), the existing `aitask_diffviewer.sh` is still the right entry point — that's a separate concern from this in-app integration.
