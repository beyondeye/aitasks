---
Task: t981_fix_failed_verification_t979_item2.md
Worktree: (none - profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Fix minimonitor pane re-pin race (t981)

## Summary

Fix `t981` by keeping `resize-pane` owned by the Python tmux gateway, but
routing the minimonitor's width re-pin through the gateway's subprocess path
instead of the live `tmux -C` control client. The archived `t979` verification
proved the immediate subprocess command sticks during terminal growth, while the
immediate control-mode command loses the tmux reflow race.

## Key Changes

- Update `TmuxMonitor.resize_pane` in `.aitask-scripts/monitor/monitor_core.py`
  to call `self._tmux.resize_pane(...)` without passing `self._backend`, so this
  pane-geometry operation uses direct subprocess execution.
- Keep `TmuxClient.resize_pane(..., backend=...)` behavior intact for callers
  that explicitly request control-mode dispatch; do not change global
  `tmux_run` or control-client behavior.
- Update docstrings/comments around `TmuxMonitor.resize_pane` to document the
  intentional subprocess path and the terminal-growth race.
- Leave `MiniMonitorApp._maybe_pin_width()` behavior unchanged; it already
  checks `self.size.width > self._target_width` and calls the monitor resize
  helper.

## Public/Internal API Notes

- No external CLI or config changes.
- Internal behavior change: `TmuxMonitor.resize_pane()` becomes a direct
  subprocess resize helper, unlike `TmuxMonitor.tmux_run()`.
- `TmuxClient.resize_pane()` remains the single owner of `resize-pane` argv
  construction and still supports backend dispatch when called directly with
  `backend`.

## Test Plan

- Add or update a focused unit test asserting `TmuxMonitor.resize_pane()` calls
  `TmuxClient.resize_pane(..., backend=None)` even when `_backend` is set.
- Keep existing `tests/test_tmux_exec.py::TestResizePane` gateway argv tests;
  adjust only comments if they imply minimonitor should use control mode.
- Run:
  - `python tests/test_tmux_exec.py`
  - `bash tests/test_multi_session_minimonitor.sh`
  - `bash tests/test_no_raw_tmux.sh`
- Manual verification: spawn minimonitor, detach tmux, resize terminal much
  wider, reattach, and confirm the companion pane snaps back to the configured
  width.

## Final Implementation Notes

- **Actual work done:** Implemented the planned narrow transport fix. `TmuxMonitor.resize_pane()` now still delegates to `TmuxClient.resize_pane()` but intentionally omits the control backend, forcing the subprocess path for monitor-level pane geometry. Added a monitor-level regression test in `tests/test_tmux_exec.py` while preserving the direct gateway test that proves explicit backend dispatch still works.
- **Deviations from plan:** None.
- **Issues encountered:** No implementation blockers. The active plan file did not exist because planning happened in chat; this file was created before committing so archival has a complete implementation record.
- **Key decisions:** The fix chooses the immediate subprocess path over delay/retry because the `t979` diagnosis showed it sticks during the exact tmux window-growth race and avoids timing guesses. Global control-mode dispatch remains unchanged for other monitor commands.
- **Upstream defects identified:** None.
- **Verification:** `python tests/test_tmux_exec.py` (42 passed), `bash tests/test_multi_session_minimonitor.sh` (39/39 passed), `bash tests/test_no_raw_tmux.sh` (5/5 passed), and `python -m py_compile .aitask-scripts/monitor/monitor_core.py tests/test_tmux_exec.py` all passed. The detach -> resize wider -> reattach scenario remains the manual acceptance check.
