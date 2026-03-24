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
updated_at: 2026-03-24 13:19
completed_at: 2026-03-24 13:19
---

## Summary

Write an initial heartbeat to `{name}_alive.yaml` when `launch_agent()` starts an agent process, so the agent isn't immediately considered stale on the runner's next iteration.

## Problem

When the runner launches an agent via `launch_agent()` in `agentcrew_runner.py`, it transitions the agent to Running status and spawns the process, but does NOT write an initial heartbeat to `{name}_alive.yaml`. The agent process (code agent) is expected to write its own heartbeats, but if it hasn't written one by the next runner iteration (30s interval), `check_agent_alive()` in `agentcrew_utils.py:284` returns `False` immediately because `last_hb` is falsy (empty), marking the agent as stale/Error.

This means any agent that takes more than one runner interval (~30s) to write its first heartbeat (or never writes one) gets killed.

## Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_runner.py` — `launch_agent()` function (line ~430). After launching the process, write an initial heartbeat to `{name}_alive.yaml`.

## Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_runner.py` lines 254-261 — `update_runner_heartbeat()` shows how the runner writes its own heartbeat
- `.aitask-scripts/agentcrew/agentcrew_utils.py` lines 279-292 — `check_agent_alive()` shows how staleness is determined

## Implementation Plan

### Step 1: Write initial agent heartbeat at launch

In `launch_agent()`, after the `subprocess.Popen` call succeeds (line ~444), write an initial heartbeat:

```python
alive_path = os.path.join(worktree, f"{name}_alive.yaml")
update_yaml_field(alive_path, "last_heartbeat", now_utc())
```

### Step 2: Verify

1. Start the runner with a crew that has a single agent
2. Verify the agent's `_alive.yaml` has a heartbeat immediately after launch
3. Verify the agent isn't marked stale on the next iteration
