---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ui, agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-24 10:57
updated_at: 2026-04-13 13:15
---

## Summary

Disable the Start/Stop Runner buttons in the brainstorm TUI Status tab immediately after press, until the next UI refresh (30-second timer or tab switch), to prevent multiple activations.

## Context

Added in t447_2, the runner Start/Stop buttons in the brainstorm Status tab call `start_runner()`/`stop_runner()` then immediately refresh the tab. Since the runner process takes time to start and write its `_runner_alive.yaml`, the status doesn't change on immediate refresh — the button reappears enabled, allowing the user to click it repeatedly and spawn multiple runner processes.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — Modify `_on_runner_start` and `_on_runner_stop` handlers to disable the pressed button before calling the runner function, then let the next `_refresh_status_tab()` cycle re-mount fresh (enabled) buttons.

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_app.py` lines 1724-1743 — current `_on_runner_start` and `_on_runner_stop` handlers
- `.aitask-scripts/brainstorm/brainstorm_app.py` lines 978-1018 — `_refresh_status_tab()` runner section that mounts the buttons with classes `.btn_runner_start` / `.btn_runner_stop`

## Implementation Plan

### Step 1: Disable button in handlers

In both `_on_runner_start` and `_on_runner_stop`, disable the button immediately after press and before calling `start_runner()`/`stop_runner()`. Do NOT call `_refresh_status_tab()` after — let the 30-second timer or tab switch handle the next refresh. This way the button stays disabled until fresh widgets are mounted.

```python
@on(Button.Pressed, ".btn_runner_start")
def _on_runner_start(self, event: Button.Pressed) -> None:
    event.button.disabled = True
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and start_runner(crew_id):
        self.notify("Runner started")
    else:
        self.notify("Failed to start runner", severity="error")

@on(Button.Pressed, ".btn_runner_stop")
def _on_runner_stop(self, event: Button.Pressed) -> None:
    event.button.disabled = True
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and stop_runner(crew_id):
        self.notify("Runner stop requested")
    else:
        self.notify("Failed to stop runner", severity="error")
```

### Step 2: Verify

1. Launch brainstorm TUI, navigate to Status tab
2. Click Start Runner — button should become disabled
3. Wait for 30-second refresh or switch tabs — button should re-appear based on current runner state
4. Verify Stop Runner button behaves the same way
