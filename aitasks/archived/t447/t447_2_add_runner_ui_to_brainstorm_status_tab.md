---
priority: medium
effort: medium
depends: [t447_1]
issue_type: feature
status: Done
labels: [ui, agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 23:09
updated_at: 2026-03-24 10:50
completed_at: 2026-03-24 10:50
---

## Summary

Add runner start/stop/status control to the brainstorm TUI Status tab, using the shared `agentcrew_runner_control` module created in t447_1.

## Context

The brainstorm TUI (`brainstorm_app.py`) has a Status tab that shows operation groups and agent statuses (refreshes every 30s). This task adds a runner control section at the top of the Status tab so users can manage the crew runner without switching to the crew dashboard.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — **Modify** Status tab (main change)

## Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — shared runner functions (created in t447_1)
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` lines 512-522, 648-673 — how dashboard displays runner status (CrewCard and CrewDetailScreen)
- `.aitask-scripts/brainstorm/brainstorm_app.py` lines 958-1046 — existing `_refresh_status_tab()` method
- `.aitask-scripts/brainstorm/brainstorm_app.py` lines 74, 76-90 — AIT_PATH and color constants

## Implementation Plan

### Step 1: Add imports

In `brainstorm_app.py`, add:
```python
from agentcrew.agentcrew_runner_control import (
    get_runner_info, start_runner, stop_runner,
)
```

### Step 2: Add runner status section to `_refresh_status_tab()`

After the worktree check (line 972) and before reading groups (line 974), insert runner status:

```python
# Runner status section
crew_id = self.session_data.get("crew_id", "")
if crew_id:
    runner = get_runner_info(crew_id)
    # Mount runner status label + buttons
    ...
```

Status display with color coding:
- `status == "none"` → gray `#888888`, "No runner"
- `status == "stopping"` → orange `#FFB86C`, "Runner stopping"
- `stale == True` (and status not "none") → red `#FF5555`, "Runner stale"
- Otherwise → green `#50FA7B`, "Runner active"

Show hostname and heartbeat age on the same line.

Mount buttons in a `Horizontal` container:
- "Start Runner" button — shown when runner is not active (status "none" or stale)
- "Stop Runner" button — shown when runner is active

### Step 3: Add button handlers

```python
@on(Button.Pressed, ".btn_runner_start")
def _on_runner_start(self, event: Button.Pressed) -> None:
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and start_runner(crew_id):
        self.notify("Runner started")
    else:
        self.notify("Failed to start runner", severity="error")
    self._refresh_status_tab()

@on(Button.Pressed, ".btn_runner_stop")
def _on_runner_stop(self, event: Button.Pressed) -> None:
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and stop_runner(crew_id):
        self.notify("Runner stop requested")
    else:
        self.notify("Failed to stop runner", severity="error")
    self._refresh_status_tab()
```

### Step 4: Add CSS

In the `CSS` class variable, add:
```css
#runner_bar { height: auto; padding: 0 1; margin-bottom: 1; }
.btn_runner_start, .btn_runner_stop { margin: 0 1; }
```

## Verification Steps

1. Launch brainstorm TUI: `cd .aitask-scripts && python -m brainstorm.brainstorm_app <task_num>`
2. Navigate to Status tab (press 5)
3. Verify runner status section appears at the top
4. Test Start/Stop buttons trigger runner control
5. Verify 30-second auto-refresh updates runner status
