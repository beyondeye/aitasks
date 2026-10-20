---
Task: t2078_sibling_pick_honours_failed_kill.md
Base branch: main
Output branch: main
---

# t2078 — Sibling-pick kill paths honour a failed `kill_agent_pane_smart`

## Context

t2075 fixed the monitor restart path so a failed kill no longer proceeds. While
auditing every `kill_agent_pane_smart` call site it found two sibling-pick sites
that still drop the `(ok, …)` result:

- `MonitorApp._launch_pick_for_sibling` (`.aitask-scripts/monitor/monitor_app.py:3803-3806`)
  — kills before opening the pick dialog, then always clears focus and toasts
  `Killed <window>`, even when the kill failed.
- `MiniMonitorApp._launch_pick` `on_pick_result` (`.aitask-scripts/monitor/minimonitor_app.py:3369-3371`)
  — kills after a successful launch, always clears focus, never reports a failure.

Result: a kill that never happened is reported (monitor) or silently ignored
(minimonitor), and the still-running pane loses focus. The reference shape is the
kill-confirm callbacks (`monitor_app.py:3690-3698`, `minimonitor_app.py:3209-3223`):
on `ok=False`, `notify(f"Failed to kill {name}", severity="error", markup=False)`
and leave focus alone.

Work on the current branch (profile `fast`).

## Implementation

1. **`monitor_app.py` `_launch_pick_for_sibling`** — replace the live branch:
   ```python
   if state == "live":
       ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
       if ok:
           self._focused_pane_id = None
           self.notify(f"Killed {old_name}", markup=False)
       else:
           self.notify(f"Failed to kill {old_name}", severity="error",
                       markup=False)
   ```
   The pick dialog still opens either way (same as the frozen / unverified
   branches — the outgoing task is a different, normally finished, one, so
   nothing is duplicated). Update the method docstring's kill sentence to say a
   failed kill is reported and leaves focus.

2. **`minimonitor_app.py` `_launch_pick` `on_pick_result`** — replace the live branch:
   ```python
   if state == "live":
       ok, _ = self._monitor.kill_agent_pane_smart(kill_pane_id)
       if ok:
           self._focused_pane_id = None
       else:
           snap = self._snapshots.get(kill_pane_id)
           name = snap.pane.window_name if snap else kill_pane_id
           # Window names are tmux-side input; unstyled (t2017).
           self.notify(f"Failed to kill {name}", severity="error",
                       markup=False)
   ```
   No success toast is added (behaviour unchanged on success; a collapsed window
   tears this app down anyway). Add one sentence to the `_launch_pick` docstring
   noting a failed kill is reported and focus kept.

3. **`tests/test_monitor_pick_launch_sites.py` `SiblingPickTests`** — add
   `test_failed_kill_reports_failure_keeps_focus_and_still_opens_the_dialog`:
   `_Host("41_2", _info("41_2","Done"))`, `host.kill_ok = False`, run
   `_launch_pick_for_sibling`; assert log ==
   `[("read","%7","@aitask_frozen"), ("kill","%7"), ("notify","Failed to kill agent-pick-41"), ("push",)]`,
   the note severity is `"error"`, `host._focused_pane_id == "%7"`, and no
   `"Killed agent-pick-41"` note. The existing
   `test_parent_archived_and_done_are_killed_before_the_dialog` is the
   success control. Update the module docstring's sibling bullet ("a failed kill
   is reported and keeps focus (t2078)").

4. **`tests/test_minimonitor_pick_by_number.py` `KillTimeFrozenRecheckTests`** —
   give `_FakeMonitor` a `kill_ok = True` attribute returned by
   `kill_agent_pane_smart` (`return (self.kill_ok, False)`). Add:
   - `test_failed_kill_after_launch_reports_and_keeps_focus` (`p` route):
     `app._focused_pane_id = "%own"`, `app._monitor.kill_ok = False`,
     `_p_with_kill_ticked(app)`; assert launched, `killed == ["%own"]`,
     `("Failed to kill agent-pick-77", "error")` in `spy_notify`, focus still
     `"%own"`, and that kwargs of that notify carry `markup=False`.
   - `test_n_failed_kill_reports_and_keeps_focus` (`n` route), same assertions.
   - Control: the existing `test_live_followed_agent_with_kill_ticked_is_killed`
     gains `assertIsNone(app._focused_pane_id)` after setting focus to `"%own"`
     first (proves the success branch still clears focus).

5. **`tests/test_monitor_markup_literal_sinks.py`** — make
   `toast_monitor_sibling_launch(name, frozen_read=(True, ""), kill_ok=True)`
   pass `kill_ok` to `_FakeMonitor`; add a minimonitor driver
   `toast_mini_launch_kill(name, kill_ok)` that focuses `name` via `_focused`
   and runs `app._launch_pick("42", Path("."), "%1")`. Add TOAST_SITES rows:
   - `("monitor: sibling pick kill failed", lambda name: toast_monitor_sibling_launch(name, kill_ok=False))`
   - `("minimonitor: launch then kill failed", lambda name: toast_mini_launch_kill(name, False))`
   (The minimonitor launch-fail error returns before the kill, so the driver
   must let the launch succeed: patch `launch_in_tmux` to `(1, None)` in this
   driver rather than reusing `_launch`'s error result — implement it with its
   own small patch block mirroring `_launch`.)

## Verification

- `python3 tests/test_monitor_pick_launch_sites.py`
- `python3 tests/test_minimonitor_pick_by_number.py`
- `python3 tests/test_monitor_markup_literal_sinks.py`
- `python3 tests/test_textual_markup_colours.py` (repo-wide markup scanner)
- Red proof: temporarily revert each source edit locally (in-memory reasoning /
  `git diff` check, not `git stash`) — the new tests must fail against the old
  `kill_agent_pane_smart(...)`-ignoring code (they assert the error toast and
  retained focus that old code never produces).
- Then Step 9 (Post-Implementation): gates run, archival.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
