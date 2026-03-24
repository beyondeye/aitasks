---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ui, agentcrew]
children_to_implement: [t447_4, t447_5]
created_at: 2026-03-23 19:35
updated_at: 2026-03-24 10:57
---

## Summary

Add crew runner start/stop/status control to the brainstorm TUI, matching the functionality already available in the crew dashboard TUI.

## Problem

The brainstorm TUI (`brainstorm_app.py`) can register work for the agent crew via `brainstorm_crew.py` → `ait crew addwork`, and it has a Status tab (t423_7) for monitoring agents/groups. However, there is no way to start, stop, or monitor the crew runner process from within the brainstorm TUI. Users must separately open the crew dashboard to manage the runner.

## Requirements

### Runner Control UI
- Add runner start/stop buttons to the brainstorm TUI (likely in the Status tab or Actions tab)
- Display runner status: running, stopped, stale (heartbeat > 120s)
- Show heartbeat age and hostname
- Prevent starting a runner if one is already active (single-instance enforcement)

### Refactor Common Code
The crew dashboard (`agentcrew_dashboard.py`) already implements:
- `start_runner()` — launches runner via `subprocess.Popen(..., start_new_session=True)` (lines 212-223)
- `stop_runner()` — sends kill command + sets `requested_action: "stop"` (lines 225-241)
- `get_runner_info()` — reads `_runner_alive.yaml`, calculates staleness (lines 192-210)
- `RUNNER_STALE_SECONDS = 120` constant

This code should be extracted into a shared module (e.g., extend `agentcrew_utils.py` or create a new `agentcrew_runner_control.py`) so both the crew dashboard and brainstorm TUI can reuse it without duplication.

### Integration Points
- `agentcrew_runner.py` already handles single-instance enforcement via alive file + PID + hostname checks — no changes needed there
- The brainstorm Status tab already refreshes on a timer and reads agent status — runner status display should integrate into this existing refresh cycle
- The crew worktree path is already available via `brainstorm_session.py`

## Implementation Notes
- Key files: `agentcrew_dashboard.py` (source of runner control code), `brainstorm_app.py` (target TUI), `agentcrew_utils.py` (shared utilities)
- After refactoring, update `agentcrew_dashboard.py` to use the shared module instead of its inline implementation
- Consider auto-starting the runner when the first work item is added (optional enhancement)
