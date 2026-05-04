---
Task: t745_4_diffviewer_screen_integration.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_1_context_aware_footer.md, aitasks/t745/t745_2_compare_regenerate_shortcut.md, aitasks/t745/t745_3_compact_equal_and_inline_diff.md
Archived Sibling Plans: aiplans/archived/p745/p745_*_*.md
Worktree: aiwork/t745_4_diffviewer_screen_integration
Branch: aitask/t745_4_diffviewer_screen_integration
Base branch: main
---

# Plan — t745_4: Replace subprocess diff with pushed DiffViewerScreen

## Context

Issue 5 from the parent: there is no real diffviewer integration. Today, `Shift+D` on the Compare tab calls `subprocess.Popen(["diff", "--color=always", str(p1), str(p2)])` — a backgrounded process that the user can never see while inside the TUI.

This task replaces that subprocess call with `self.push_screen(DiffViewerScreen(...))`, opening the existing diffviewer Textual screen inside the brainstorm app stack. Pressing `Escape` returns to the Compare tab.

User-confirmed: push DiffViewerScreen inside brainstorm; do **not** spawn a new tmux window (single-tmux-session-per-project, per CLAUDE.md).

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BINDINGS` — add `Binding("D", "compare_diff", "Diff")`.
  - `_TAB_SCOPED_ACTIONS` — add `"compare_diff": "tab_compare"`.
  - `on_key()` lines 1778–1795 — REMOVE the existing `Shift+D` block.
  - New: `action_compare_diff()`.
- `.aitask-scripts/aitask_brainstorm.sh` — confirm `.aitask-scripts/` is on the Python path (so `from diffviewer.diff_viewer_screen import DiffViewerScreen` resolves at runtime). Adjust if needed.

## Reference

- `.aitask-scripts/diffviewer/diff_viewer_screen.py:64-78` — `DiffViewerScreen.__init__(main_path, other_paths, mode="classical")` signature.
- `.aitask-scripts/diffviewer/diff_viewer_screen.py:67-76` — Screen BINDINGS including `Escape` to dismiss.
- `.aitask-scripts/aitask_diffviewer.sh` — the existing launcher; reference for any sys.path setup that the brainstorm launcher might also need.

## Implementation steps

1. **Read t745_1's archived plan** for the `_TAB_SCOPED_ACTIONS` shape.

2. **Remove old handler.** Delete lines 1778–1795 of `brainstorm_app.py` (the `if event.key == "D":` block in `on_key()`). Confirm no surrounding logic depends on its early-return.

3. **Add binding** in `BINDINGS`:
   ```python
   Binding("D", "compare_diff", "Diff"),
   ```

4. **Register in registry** alongside any other compare-tab entries:
   ```python
   _TAB_SCOPED_ACTIONS: dict[str, str] = {
       "compare_diff": "tab_compare",
       # ... other entries from sibling tasks
   }
   ```

5. **Add action method**:
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

6. **Verify import path.** Launch and press `D`. If `ModuleNotFoundError: diffviewer`, edit `aitask_brainstorm.sh` so that `.aitask-scripts/` is on `PYTHONPATH` (or insert `sys.path.insert(0, ...)` at the top of `brainstorm_app.py` matching the diffviewer launcher). Confirm the diffviewer TUI still launches via its own script after any sys.path change.

## Verification

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635`.
- Switch to Compare. Footer shows `D Diff`.
- With NO nodes picked, press `D` — warning notification, no screen pushed.
- Pick `n000` and `n001`. Press `D` — `DiffViewerScreen` pushes; the two markdown proposals diff with full color.
- Inside diffviewer: `m` toggles mode, `u` toggles unified view, `v` toggles layout, `n`/`p` cycle comparisons. All work.
- Press `Escape` — back on Compare with the dimension matrix still visible.
- Switch to Dashboard — `D Diff` no longer appears in the footer.
- `shellcheck .aitask-scripts/aitask_brainstorm.sh` if launcher was edited.

## Out of scope

- Spawning diffviewer in a separate tmux window (architecturally rejected — see CLAUDE.md single-tmux-session rule).
- Diffing more than two proposals; `_compare_nodes[:2]` is sufficient because the brainstorm Compare tab itself is two-node-oriented.

## Final Implementation Notes

(to be filled in at Step 8)
