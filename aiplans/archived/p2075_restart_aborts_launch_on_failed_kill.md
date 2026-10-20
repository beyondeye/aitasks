---
Task: t2075_restart_aborts_launch_on_failed_kill.md
Base branch: main
Output branch: main
---

# t2075 — Restart must not launch when the kill failed

## Context

`MonitorApp._on_restart_confirmed` (`.aitask-scripts/monitor/monitor_app.py`,
the `on_pick_result` closure, ~line 3930) kills the old agent and then always
calls `launch_in_tmux`, even when `kill_agent_pane_smart` returns `ok=False`.
A failed kill leaves the original agent alive while a replacement starts on
the same task, and the toast still says "Restarted agent for t<id>". t2065 put a
frozen/unverified re-check in front of the kill, but the live path still
ignores the kill's own result. This bug was already there before t2065.

Current branch, no worktree (profile `fast`).

## Implementation

### 1. `.aitask-scripts/monitor/monitor_app.py` — `on_pick_result` in `_on_restart_confirmed`

Replace

```python
ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
if ok:
    if self._focused_pane_id == pane_id:
        self._focused_pane_id = None
    self.notify(f"Killed {old_window_name}", markup=False)
```

with an early return on failure. The new branch follows the two "not
restarted" branches just above it: a warning toast with `markup=False`, then
`call_later(self._refresh_data)`, then `return`.

```python
ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
if not ok:
    # A failed kill leaves the old agent running; launching
    # anyway would put two agents on one task (t2075).
    self.notify(
        f"Failed to kill {old_window_name} — not restarted",
        severity="warning", markup=False)
    self.call_later(self._refresh_data)
    return
if self._focused_pane_id == pane_id:
    self._focused_pane_id = None
self.notify(f"Killed {old_window_name}", markup=False)
```

The focus stays on the old pane, which is still alive. The success path does
not change.

### 2. `tests/test_monitor_pick_launch_sites.py`

- `_Host._Monitor.kill_agent_pane_smart`: return `(host.kill_ok, "killed")`
  with `self.kill_ok = True` set in `_Host.__init__`, so the default behaviour
  stays the same.
- `RestartPickTests`: add `test_failed_kill_neither_launches_nor_reports_restart`.
  It opens the dialog, sets `host.kill_ok = False` and calls `callback(_cfg())`.
  It then asserts the exact log `[("read", "%7", "@aitask_frozen"), ("kill", "%7"),
  ("notify", "Failed to kill agent-pick-41 — not restarted"), ("call_later",)]`,
  that the note's severity is `warning`, that no `launch` or `spawn` entry
  appears, that there is no "Restarted agent" or "Killed" note, and that
  `_focused_pane_id` is still `"%7"`.
- Module docstring: the restart-path bullet gets "a failed kill also launches
  nothing (t2075)".

### 3. `tests/test_monitor_markup_literal_sinks.py`

- `toast_monitor_restart(name, frozen_read=(True, ""), kill_ok=True)` passes
  `kill_ok` through to `_FakeMonitor`.
- Add the `TOAST_SITES` entry
  `("monitor: restart kill failed, not restarted", lambda name: toast_monitor_restart(name, kill_ok=False))`.
  The failure toast names the hostile window and has to reach `notify` with
  `markup=False`. Launch is never reached, so the only toast that names the
  window is the new one.

## Verification

- `python3 tests/test_monitor_pick_launch_sites.py`
- `python3 tests/test_monitor_markup_literal_sinks.py`
- Red proof: temporarily revert step 1 in a scratch copy, or reason from the
  log assertion. The new test fails on the pre-fix code because `("launch", …)`
  and "Restarted agent for t42" appear.
- `bash tests/run_all_python_tests.sh --test-dir tests` is optional. These two
  modules are the only consumers of this callback.

## Step 9

Post-implementation: commit the code (`bug: … (t2075)`) and the plan, then
archive through `aitask_archive.sh 2075`. Current branch, so there is no merge.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** In `_on_restart_confirmed`'s `on_pick_result`, an `ok=False` result from `kill_agent_pane_smart` now shows a warning toast ("Failed to kill <window> — not restarted", `markup=False`), queues `_refresh_data` and returns before `launch_in_tmux`. Focus stays on the surviving pane. The success path is unchanged. New regression: `RestartPickTests.test_failed_kill_neither_launches_nor_reports_restart` (`_Host` gained a `kill_ok` knob that defaults to True). The new toast is pinned in `TOAST_SITES` (`toast_monitor_restart` gained `kill_ok`).
- **Deviations from plan:** None.
- **Issues encountered:** None. Red proof: in a scratch tree using HEAD's `monitor_app.py`, the new restart test fails (launch + "Restarted agent" logged), and it passes with the fix. The `TOAST_SITES` entry is a markup pin, not a red proof: pre-fix, the launch-error toast also names the window with `markup=False`.
- **Key decisions:** Severity is `warning`, matching the callback's two other "not restarted" branches (frozen / unverified) rather than `_on_kill_confirmed`'s `error`. In every case the restart is refused and the old agent is left untouched.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_app.py:3804 — _launch_pick_for_sibling ignores kill_agent_pane_smart's ok result: it clears focus and notifies "Killed <window>" even when the kill failed`
  - `.aitask-scripts/monitor/minimonitor_app.py:3370 — the minimonitor sibling-pick kill likewise ignores kill_agent_pane_smart's result and clears focus unconditionally (no failure toast)`
