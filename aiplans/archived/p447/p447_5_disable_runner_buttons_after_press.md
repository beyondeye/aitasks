---
Task: t447_5_disable_runner_buttons_after_press.md
Parent Task: aitasks/t447_add_crew_runner_control_to_brainstorm_tui.md
Sibling Tasks: (all archived — see Archived Sibling Plans below)
Archived Sibling Plans: aiplans/archived/p447/p447_1_extract_runner_control_shared_module.md, aiplans/archived/p447/p447_2_add_runner_ui_to_brainstorm_status_tab.md, aiplans/archived/p447/p447_3_push_crew_worktree_after_addwork.md, aiplans/archived/p447/p447_4_fix_crew_runner_import_path.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Plan: Disable runner Start/Stop buttons after press

### Context

The runner Start/Stop buttons in the brainstorm TUI Status tab (added in t447_2) can be clicked multiple times in rapid succession before the UI refreshes, spawning multiple runner processes. The existing handlers already call `_delayed_refresh_status()` which schedules a refresh after 2 seconds — but during those 2 seconds, the button remains enabled and clickable. Disable the pressed button immediately before calling the runner function, so the delayed refresh re-mounts it fresh with correct state.

### Current state

`.aitask-scripts/brainstorm/brainstorm_app.py:2163-2181` — existing handlers:

```python
@on(Button.Pressed, ".btn_runner_start")
def _on_runner_start(self, event: Button.Pressed) -> None:
    """Start the crew runner process."""
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and start_runner(crew_id):
        self.notify("Runner started")
        self._delayed_refresh_status()
    else:
        self.notify("Failed to start runner", severity="error")

@on(Button.Pressed, ".btn_runner_stop")
def _on_runner_stop(self, event: Button.Pressed) -> None:
    """Request the crew runner to stop."""
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and stop_runner(crew_id):
        self.notify("Runner stop requested")
        self._delayed_refresh_status()
    else:
        self.notify("Failed to stop runner", severity="error")
```

Note: the current code uses `_delayed_refresh_status()` (defined at line 1475), which schedules `_refresh_status_tab()` after 2 seconds via `set_timer`. The original task description referenced an older revision that called `_refresh_status_tab()` directly — the plan follows the current code.

### Step 1: Disable button at top of handlers

In both `_on_runner_start` and `_on_runner_stop`, set `event.button.disabled = True` as the very first statement, before reading `crew_id` or calling the runner function. Keep the existing `_delayed_refresh_status()` call unchanged — after 2 seconds the status tab re-mounts fresh widgets based on the runner's actual state.

### Step 2: Verify

1. Launch brainstorm TUI and open Status tab (`5`)
2. Click "Start Runner" once — the button should become visibly disabled immediately
3. Try clicking the disabled button again — nothing happens (no second runner spawn)
4. After ~2 seconds the refresh runs and the button area now shows "Stop Runner" (enabled)
5. Repeat for Stop Runner: click, it becomes disabled, wait ~2s, Start Runner reappears enabled
6. Failure path: if the runner call fails (no crew_id), the button stays disabled — status tab will re-mount on the next 30-second periodic refresh or on tab switch

### Step 3: Post-Implementation

Follow task-workflow Step 9 — commit, archive task and plan, release lock, push.

## Final Implementation Notes

- **Actual work done:** Added `event.button.disabled = True` as the first statement in both `_on_runner_start` and `_on_runner_stop` at `.aitask-scripts/brainstorm/brainstorm_app.py:2163-2181`. Nothing else was changed — the existing `_delayed_refresh_status()` 2-second timer re-mounts fresh widgets based on the runner's new state.
- **Deviations from plan:** None. The plan matched the implementation exactly.
- **Issues encountered:** The task description referenced line numbers 1724-1743 and a version of the handlers that called `_refresh_status_tab()` directly. Current code (line 2163) uses `_delayed_refresh_status()` instead (defined at line 1475), which schedules a refresh after 2s via `set_timer`. The fix still applies cleanly — disabling the button at the top of the handler works regardless of how the later refresh is triggered.
- **Key decisions:** Kept the existing `_delayed_refresh_status()` call unchanged. Setting `disabled = True` on the button widget is enough to prevent repeat clicks in the 2-second window; the subsequent refresh re-mounts the button area with fresh enabled widgets reflecting the new runner state.
- **Notes for sibling tasks:** None — this is the last remaining child task for t447 (siblings 1-4 already archived).

