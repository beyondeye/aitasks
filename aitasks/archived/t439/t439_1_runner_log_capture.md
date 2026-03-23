---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 12:53
updated_at: 2026-03-23 13:20
completed_at: 2026-03-23 13:20
---

## Runner: Capture agent subprocess output to per-agent log files

### Context
The agentcrew runner spawns code agents via `subprocess.Popen()` with `stdout=subprocess.DEVNULL` and `stderr=subprocess.DEVNULL` (agentcrew_runner.py:408-413). No output is captured, making troubleshooting impossible. This child task adds log file capture at the runner level.

### Key Files to Modify
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — Main changes

### Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — `update_yaml_field()`, `read_yaml()`, agent file conventions
- Existing per-agent files follow the pattern `<agent>_<suffix>` in the crew worktree root (e.g., `_status.yaml`, `_output.md`, `_alive.yaml`)

### Implementation Plan

#### 1. Add `append_to_agent_log()` helper function (after the existing `log()` function, ~line 58)

```python
def append_to_agent_log(worktree: str, name: str, message: str) -> None:
    """Append a timestamped message to an agent's log file."""
    log_path = os.path.join(worktree, f"{name}_log.txt")
    if not os.path.isfile(log_path):
        return
    with open(log_path, "a") as f:
        f.write(f"\n=== {now_utc()} | {message} ===\n")
```

#### 2. Add module-level dict for tracking open log file handles (~line 43)

```python
_log_handles: dict[str, object] = {}
```

#### 3. Modify `launch_agent()` (lines 361-424)

Replace the `subprocess.DEVNULL` redirect with log file capture:

- Before `subprocess.Popen`, open `<worktree>/<name>_log.txt` in append mode
- Write a header: agent name, type, agent_string, timestamp, full command
- Pass the file handle as both `stdout` and `stderr`
- Store handle in `_log_handles[name]`

```python
# Replace lines 407-414 with:
log_path = os.path.join(worktree, f"{name}_log.txt")
log_fh = open(log_path, "a")
cmd = ["./ait", "codeagent", "--agent-string", agent_string,
       "invoke", "raw", "-p", work2do_content]
log_fh.write(f"=== Agent: {name} | Type: {atype} | String: {agent_string} ===\n")
log_fh.write(f"=== Started: {now_utc()} ===\n")
log_fh.write(f"=== Command: {' '.join(cmd)} ===\n")
log_fh.write(f"{'=' * 60}\n")
log_fh.flush()

proc = subprocess.Popen(cmd, cwd=worktree, stdout=log_fh, stderr=log_fh)
_log_handles[name] = log_fh
```

#### 4. Call `append_to_agent_log()` in `mark_stale_as_error()`

After setting agent status to Error for stale agents, append a stale marker to the log.

#### 5. Close log handles in `graceful_shutdown()` (~line 575)

```python
# At the end of graceful_shutdown, before the final log message:
for name, fh in _log_handles.items():
    try:
        fh.close()
    except Exception:
        pass
_log_handles.clear()
```

### Verification Steps
1. Create a test crew, add a work item, start the runner
2. Verify `<agent>_log.txt` files appear in the crew worktree alongside `_status.yaml` etc.
3. Check log files contain: header with command/timestamp, and agent stdout/stderr output
4. Verify stale agents get a stale marker appended to their log
5. Verify graceful shutdown closes file handles cleanly
