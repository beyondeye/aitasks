---
Task: t745_4_diffviewer_screen_integration.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_5_manual_verification_improve_node_comparator.md
Archived Sibling Plans: aiplans/archived/p745/p745_1_context_aware_footer.md, aiplans/archived/p745/p745_2_compare_regenerate_shortcut.md, aiplans/archived/p745/p745_3_compact_equal_and_inline_diff.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-05 01:09
---

# Plan — t745_4: Replace subprocess diff with pushed DiffViewerScreen

## Context

Issue 5 from parent task t745: there is no real diffviewer integration in
brainstorm. Today, on the Compare tab, pressing `Shift+D` runs
`subprocess.Popen(["diff", "--color=always", str(p1), str(p2)])` — a
backgrounded process the user can never see while inside the TUI (single
tmux session model — see CLAUDE.md "Single tmux session per project").

This task replaces that subprocess call with `self.push_screen(DiffViewerScreen(...))`,
opening the existing diffviewer Textual screen inside the brainstorm app
stack. Pressing `Escape` returns to the Compare tab via
`DiffViewerScreen.action_back()` which calls `self.app.pop_screen()`
(`.aitask-scripts/diffviewer/diff_viewer_screen.py:262-263`).

User-confirmed design decision: push DiffViewerScreen inside brainstorm; do
NOT spawn a new tmux window.

## Verification of plan (2026-05-05)

The siblings t745_1, t745_2, t745_3 have been merged. Notable changes since
the original plan was written:

- `BINDINGS` block has shifted to **lines 1589–1601** (was 1512–1523).
- `_TAB_SCOPED_ACTIONS` registry was added by t745_1 and is at **lines 1606–1608**;
  t745_2 already populated it with `"compare_regenerate": "tab_compare"`.
- The `Shift+D` handler is now at **lines 1875–1892** (was 1778–1795), inside
  `BrainstormApp.on_key()` which starts at line 1713.
- The brainstorm launcher is named **`aitask_brainstorm_tui.sh`** (not
  `aitask_brainstorm.sh` as the original plan stated).
- `brainstorm_app.py:11-13` already inserts `.aitask-scripts/` onto
  `sys.path` (`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`),
  so `from diffviewer.diff_viewer_screen import DiffViewerScreen` resolves
  with no launcher modification needed.

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BINDINGS` (lines 1589–1601) — add `Binding("D", "compare_diff", "Diff")`.
  - `_TAB_SCOPED_ACTIONS` (lines 1606–1608) — add `"compare_diff": "tab_compare"`.
  - `on_key()` lines 1875–1892 — REMOVE the existing `Shift+D` block and the
    preceding comment line "Shift+D: diff proposals on Compare tab ..."
    (line 1875).
  - New: `action_compare_diff()` method, placed alongside
    `action_compare_regenerate` (currently line 2042) for symmetry with the
    other compare-tab action.
- No changes needed to `.aitask-scripts/aitask_brainstorm_tui.sh` — sys.path
  is already correct.

## Reference

- `.aitask-scripts/diffviewer/diff_viewer_screen.py:78` —
  `DiffViewerScreen.__init__(main_path: str, other_paths: list[str], mode: str = "classical")`.
- `.aitask-scripts/diffviewer/diff_viewer_screen.py:67-76` — Screen BINDINGS
  including `Binding("escape", "back", "Back")`.
- `.aitask-scripts/diffviewer/diff_viewer_screen.py:262-263` — `action_back`
  pops the screen.
- `.aitask-scripts/brainstorm/brainstorm_app.py:2042-2045` —
  `action_compare_regenerate` pattern to mirror, including
  `isinstance(self.screen, ModalScreen)` early return.
- `.aitask-scripts/brainstorm/brainstorm_app.py:11-13` — existing sys.path
  setup that already exposes the `diffviewer` package.

## Implementation steps

1. **Remove old handler.** Delete lines 1875–1892 of `brainstorm_app.py`
   (the comment line at 1875 plus the `if event.key == "D":` block at
   1876–1892). Confirm no surrounding logic depends on its early-return —
   the next handler (`if event.key == "b":` at line 1895) starts immediately
   after, so the deletion is contiguous.

   Note: `subprocess` import stays — many other call sites in the file use
   it (lines 1949, 2680, 3863, 3894, 3911, 4014, 4022).

2. **Add binding** in `BINDINGS` (after the `compare_regenerate` binding
   currently at line 1597):
   ```python
   Binding("D", "compare_diff", "Diff"),
   ```

3. **Register in registry** at lines 1606–1608:
   ```python
   _TAB_SCOPED_ACTIONS: dict[str, str] = {
       "compare_regenerate": "tab_compare",
       "compare_diff": "tab_compare",
   }
   ```

4. **Add action method** alongside `action_compare_regenerate`:
   ```python
   def action_compare_diff(self) -> None:
       if isinstance(self.screen, ModalScreen):
           return
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

   The `isinstance(self.screen, ModalScreen)` early return mirrors
   `action_compare_regenerate` — prevents pushing the diff screen on top of
   any open modal (e.g., the compare-select modal opened by `r`).

   The `from diffviewer.diff_viewer_screen import DiffViewerScreen` is kept
   inside the action body (deferred import) to avoid loading diffviewer's
   transitive imports (merge_engine, plan_loader, etc.) at brainstorm app
   startup.

## Verification

- Launch `./.aitask-scripts/aitask_brainstorm_tui.sh 635`.
- Switch to the Compare tab. Footer shows `D Diff` adjacent to `r Regenerate`.
- With NO nodes picked yet, press `D` — receive a warning notification, no
  screen pushed.
- Open the compare-select modal (`r`), then press `D` while the modal is
  open — no screen pushed (modal guard works).
- Pick `n000` and `n001` from the modal. Press `D` — `DiffViewerScreen`
  pushes onto the screen stack. The two proposal markdown files diff with
  full color.
- Inside diffviewer: mode-switch (`m`), unified view (`u`), layout toggle
  (`v`), navigation (`n`/`p`) all behave as expected.
- Press `Escape` — `DiffViewerScreen.action_back` calls `pop_screen()`,
  returning to the Compare tab with the dimension matrix still visible.
- Switch to the Dashboard tab — `D Diff` no longer appears in the footer
  (verifies `_TAB_SCOPED_ACTIONS` filter works for the new binding).
- No shellcheck run needed (no `.sh` file modified). Optional sanity:
  `python3 -c "import ast; ast.parse(open('.aitask-scripts/brainstorm/brainstorm_app.py').read())"`.

## Out of scope

- Spawning diffviewer in a separate tmux window (architecturally rejected —
  see CLAUDE.md single-tmux-session rule).
- Diffing more than two proposals; `_compare_nodes[:2]` is sufficient
  because the brainstorm Compare tab itself is two-node-oriented.
- Merge mode launch from within brainstorm (`e` inside diffviewer is still
  available, but evaluating its safety against brainstorm's session state
  is its own follow-up if needed).

## Final Implementation Notes

(to be filled in at Step 8)
