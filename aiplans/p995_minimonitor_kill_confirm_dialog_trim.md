---
Task: t995_minimonitor_kill_confirm_dialog_trim.md
Worktree: current directory
Branch: current branch
Base branch: current branch
---

# Plan: Trim Minimonitor Kill Confirmation Dialog

## Summary
- Add a preview toggle to the shared `KillConfirmDialog` so the full monitor keeps its terminal preview while minimonitor opens a shorter confirmation dialog.
- Fix the shared dialog button row so `Kill` and `Cancel` stay centered and inside the dialog in narrow panes.
- Preserve unrelated existing work in `minimonitor_app.py` by changing only the kill-dialog call site.

## Implementation Steps
1. Update `.aitask-scripts/monitor/monitor_shared.py`.
   - Add `show_preview: bool = True` to `KillConfirmDialog.__init__`.
   - Store the flag on the instance.
   - Wrap preview-content calculation and yielding of `#kill-preview-label` / `#kill-preview` in `if self._show_preview:`.
   - Keep existing callers default-compatible.
2. Adjust shared dialog CSS in `KillConfirmDialog.DEFAULT_CSS`.
   - Keep the dialog at `width: 80%`.
   - Add a practical dialog minimum width.
   - Center the horizontal button row with a fixed row height.
   - Override the dialog buttons' default minimum width and margins so both buttons fit in narrow panes.
3. Update `.aitask-scripts/monitor/minimonitor_app.py`.
   - Change only `action_kill_own_agent()` so it passes `show_preview=False`.
   - Leave `.aitask-scripts/monitor/monitor_app.py` unchanged so the full monitor keeps the preview.
4. Add regression coverage in `tests/test_kill_confirm_dialog.py`.
   - Construct synthetic `TmuxPaneInfo`, `PaneSnapshot`, and `TaskInfo` fixtures.
   - Verify default dialog renders preview widgets.
   - Verify `show_preview=False` omits preview widgets but keeps the buttons.
   - Verify both buttons stay within the dialog region in a narrow Textual test viewport.
5. Complete Step 9 cleanup through the aitask workflow.
   - Commit source/test changes with a task-tagged code commit.
   - Commit this plan separately with `./ait git`.
   - Archive task 995 and push task-data changes after archival.

## Verification
- Run `python3 tests/test_kill_confirm_dialog.py`.
- Run `bash tests/test_multi_session_minimonitor.sh`.
- Run `git diff --check -- .aitask-scripts/monitor/monitor_shared.py .aitask-scripts/monitor/minimonitor_app.py tests/test_kill_confirm_dialog.py`.

## Risk

### Code-health risk: low
- The shared dialog is used by both full monitor and minimonitor, but the new constructor parameter is defaulted to preserve existing full-monitor behavior. The CSS change is scoped to `KillConfirmDialog`. · severity: low · -> mitigation: None needed

### Goal-achievement risk: low
- Textual's default button minimum width can overflow narrow containers, so the plan depends on a dialog-specific button minimum override. The regression test checks actual widget regions in a narrow viewport. · severity: low · -> mitigation: None needed

## Final Implementation Notes
- **Actual work done:** Implemented `show_preview` on `KillConfirmDialog`, skipped preview rendering for minimonitor, tightened the shared dialog button CSS, and added focused Textual regression tests for preview behavior and narrow button fit.
- **Deviations from plan:** The implementation explicitly overrides the dialog button `min-width` because Textual's default button minimum was the concrete cause of the narrow-pane overflow.
- **Issues encountered:** The first narrow regression run showed `Cancel` extending past the dialog because each `Button` defaulted to 16 columns. Setting a dialog-specific `min-width: 10` keeps labels readable and fits both buttons within the 28-column dialog minimum.
- **Key decisions:** Keep full monitor behavior unchanged through the default `show_preview=True`; make minimonitor the only opt-out caller; test the shared modal directly rather than relying on live tmux.
- **Upstream defects identified:** None
