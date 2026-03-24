---
Task: t451_write_initial_agent_heartbeat_at_launch.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Write initial agent heartbeat at launch (t451)

## Context

When the runner launches an agent via `launch_agent()`, it transitions the agent to Running and spawns the process, but never writes an initial heartbeat to `{name}_alive.yaml`. If the agent doesn't write its own heartbeat before the next runner iteration (~30s), `check_agent_alive()` returns `False` because `last_hb` is falsy, and the agent gets marked as stale/Error.

## Implementation

### File: `.aitask-scripts/agentcrew/agentcrew_runner.py`

In `launch_agent()` (line ~447), after the `subprocess.Popen` call succeeds and the PID is recorded, write an initial heartbeat:

```python
        # Write initial heartbeat so agent isn't considered stale before it
        # writes its own first heartbeat
        alive_path = os.path.join(worktree, f"{name}_alive.yaml")
        update_yaml_field(alive_path, "last_heartbeat", now_utc())
```

Uses the same `update_yaml_field` + `now_utc()` pattern as `update_runner_heartbeat()` (line 254-261).

## Final Implementation Notes
- **Actual work done:** Added 2 lines of code (+ 2 comment lines) in `launch_agent()` to write an initial heartbeat immediately after process spawn
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** Placed the heartbeat write inside the `try` block after PID recording and before the batch print, so it only runs on successful spawn
