---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-24 12:27
updated_at: 2026-03-25 07:57
completed_at: 2026-03-25 07:57
---

## Summary

When the runner starts and finds all agents in terminal state (Error/Completed/Aborted), it immediately stops with "All agents in terminal state". Add a mechanism to reset errored agents back to Waiting so the runner can retry them.

## Problem

After an agent errors (e.g., heartbeat timeout), the runner stops because all agents are terminal. When the user tries to restart the runner, it starts, finds the agent still in Error state, triggers the `all_terminal` check (line 731-743 in `agentcrew_runner.py`), and stops again after ~1 second. There is no way to restart failed agents without manually editing YAML files.

## Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_runner.py` — Add logic at runner startup (after line 655) to detect and optionally reset agents in Error state back to Waiting.

## Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_runner.py` lines 676-682 — how stale agents are marked as Error (reverse this for reset)
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — `validate_agent_transition()` for valid state transitions
- `.aitask-scripts/agentcrew/agentcrew_runner.py` lines 730-743 — the `all_terminal` check that causes immediate stop

## Implementation Plan

### Step 1: Add `--reset-errors` CLI flag

Add a `--reset-errors` flag to the runner CLI. When set, at startup before the main loop, find all agents with status `Error` and reset them to `Waiting`:

```python
if reset_errors:
    for name, data in agents.items():
        if data.get("status") == "Error":
            status_file = os.path.join(worktree, f"{name}_status.yaml")
            update_yaml_field(status_file, "status", "Waiting")
            update_yaml_field(status_file, "error_message", "")
            update_yaml_field(status_file, "completed_at", "")
            agents[name]["status"] = "Waiting"
            log(f"Reset errored agent '{name}' to Waiting", batch)
```

### Step 2: Integrate with runner control

Update `start_runner()` in `agentcrew_runner_control.py` to pass `--reset-errors` when starting the runner, so the TUI Start button automatically resets errored agents.

### Step 3: Verify

1. Start runner with a crew where all agents are Error
2. With `--reset-errors`, verify agents are reset and the runner continues
3. Without `--reset-errors`, verify old behavior (immediate stop) is preserved
