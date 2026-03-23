---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [agentcrew]
created_at: 2026-03-23 23:08
updated_at: 2026-03-23 23:08
---

## Summary

Extract runner control functions from `agentcrew_dashboard.py` into a new shared module `agentcrew_runner_control.py`, then update the dashboard to use it.

## Context

The crew dashboard (`agentcrew_dashboard.py`) implements runner start/stop/status inline. The brainstorm TUI needs the same functionality (t447). To avoid duplication, extract these into a shared module that both TUIs can import.

## Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — **Create** new shared module
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — **Modify** to delegate to shared module

## Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_utils.py` — existing shared utilities (same import pattern)
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` lines 62-83, 192-241 — code to extract

## What to Extract from `agentcrew_dashboard.py`

1. `RUNNER_STALE_SECONDS = 120` (line 62)
2. `_elapsed_since(ts_str)` (lines 70-75) — helper using `_parse_timestamp` from `agentcrew_utils`
3. `_heartbeat_age(ts_str)` (lines 78-83) — helper using `format_elapsed` from `agentcrew_utils`
4. `get_runner_info(crew_id)` (lines 192-210 of `CrewManager`) — make standalone function
5. `start_runner(crew_id)` (lines 212-223) — make standalone function
6. `stop_runner(crew_id)` (lines 225-241) — make standalone function

## Implementation Plan

### Step 1: Create `agentcrew_runner_control.py`

- Compute `AIT_PATH` same as dashboard: `Path(__file__).resolve().parent.parent.parent / "ait"`
- Import from `agentcrew_utils`: `crew_worktree_path`, `read_yaml`, `update_yaml_field`, `_parse_timestamp`, `format_elapsed`
- Move `RUNNER_STALE_SECONDS`, `_elapsed_since()`, `_heartbeat_age()` as module-level items
- Convert `CrewManager.get_runner_info()`, `.start_runner()`, `.stop_runner()` to standalone functions taking `crew_id` as parameter

### Step 2: Update `agentcrew_dashboard.py`

- Remove `RUNNER_STALE_SECONDS`, `_elapsed_since()`, `_heartbeat_age()` (lines 62-83)
- Add import: `from agentcrew_runner_control import RUNNER_STALE_SECONDS, _elapsed_since, _heartbeat_age, get_runner_info as _get_runner_info, start_runner as _start_runner, stop_runner as _stop_runner`
- Keep `CrewManager` methods as thin wrappers calling the shared functions
- The rest of the dashboard UI code (CrewCard, CrewDetailScreen) stays unchanged since it calls through CrewManager

## Verification Steps

1. `cd .aitask-scripts && python -c "from agentcrew.agentcrew_runner_control import get_runner_info, start_runner, stop_runner; print('OK')"`
2. `cd .aitask-scripts && python -c "from agentcrew.agentcrew_dashboard import CrewManager; print('OK')"`
3. Verify no remaining references to old standalone functions in dashboard
