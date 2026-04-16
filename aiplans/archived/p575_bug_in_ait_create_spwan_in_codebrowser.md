---
Task: t575_bug_in_ait_create_spwan_in_codebrowser.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Fix stale tmux window index in codebrowser `ait create`

## Context

When spawning `ait create` from codebrowser's file detail view, the tmux window
index is captured once at app initialization (`__init__`) and cached in
`self._tmux_window`. If the user opens/closes tmux windows before invoking
"create task", the cached index becomes stale — pointing to the wrong window or
a non-existent one. The `AgentCommandScreen` dialog then pre-selects the wrong
target window for the split pane.

## Root Cause

`codebrowser_app.py:278` — `self._tmux_window` is set by calling
`_detect_tmux_window()` once during `__init__`, then passed verbatim at line
1227 when opening the `AgentCommandScreen`.

The session name (`self._tmux_session`) is fine to cache — it doesn't change
when windows are opened/closed. Only the window **index** is volatile.

## Fix

**Call `_detect_tmux_window()` fresh at action time** instead of using the
cached value. Since it's only consumed in one place, remove the cached attribute
entirely.

### Changes

**File: `.aitask-scripts/codebrowser/codebrowser_app.py`**

1. **Line 278** — Remove the `self._tmux_window` init line:
   ```python
   # DELETE:
   self._tmux_window: str | None = self._detect_tmux_window()
   ```

2. **Line 1227** — Call `_detect_tmux_window()` fresh instead of using cached value:
   ```python
   # BEFORE:
   default_tmux_window=self._tmux_window,
   # AFTER:
   default_tmux_window=self._detect_tmux_window(),
   ```

That's the complete fix. No other files need changes because:
- `AgentCommandScreen._update_window_options()` already fetches a fresh window
  list via `get_tmux_windows()` — the only issue was the stale *default* index
  passed from the caller
- The minimonitor spawn at lines 1242-1245 uses `result.window` from the
  dialog's *user selection* (which reflects the fresh list), not the cached value

## Verification

1. Launch codebrowser in a tmux session
2. Note the current window index
3. Create and close some tmux windows to shift indices
4. Use the "create task" action (select lines, press `n`)
5. Verify the `AgentCommandScreen` dialog pre-selects the **current** codebrowser
   window (or "New window" if the index lookup fails), not the stale init-time index

## Final Implementation Notes
- **Actual work done:** Removed cached `self._tmux_window` attribute from `CodeBrowserApp.__init__()` and replaced the single usage site with a fresh `self._detect_tmux_window()` call at action time, matching the dynamic resolution pattern used by `tui_switcher` and `tmux_monitor`.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Session name (`self._tmux_session`) left cached since session names are stable across window open/close operations; only window index is volatile.
