---
Task: t439_1_runner_log_capture.md
Parent Task: aitasks/t439_agentcrew_logging.md
Sibling Tasks: aitasks/t439/t439_2_shared_log_utils.md, aitasks/t439/t439_3_dashboard_log_browser.md, aitasks/t439/t439_4_brainstorm_status_tab.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Plan: Runner Log Capture

### Context
`agentcrew_runner.py` spawns code agents via `subprocess.Popen()` with `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` (lines 408-413). This discards all agent output, making troubleshooting impossible.

### Changes to `.aitask-scripts/agentcrew/agentcrew_runner.py`

#### 1. Add module-level log handle tracker (after line 42, near other constants)

```python
_log_handles: dict[str, object] = {}  # agent_name → open file handle for log
```

#### 2. Add `append_to_agent_log()` helper (after `log()` function, ~line 59)

```python
def append_to_agent_log(worktree: str, name: str, message: str) -> None:
    """Append a timestamped message to an agent's log file."""
    log_path = os.path.join(worktree, f"{name}_log.txt")
    if not os.path.isfile(log_path):
        return
    with open(log_path, "a") as f:
        f.write(f"\n=== {now_utc()} | {message} ===\n")
```

#### 3. Modify `launch_agent()` (lines 405-424)

Replace:
```python
    log(f"Launching agent '{name}' (type={atype}, string={agent_string})", batch)
    try:
        proc = subprocess.Popen(
            ["./ait", "codeagent", "--agent-string", agent_string,
             "invoke", "raw", "-p", work2do_content],
            cwd=worktree,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
```

With:
```python
    log(f"Launching agent '{name}' (type={atype}, string={agent_string})", batch)
    try:
        # Capture agent stdout/stderr to a per-agent log file
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

Keep the rest of the try/except block the same (update_yaml_field for pid, batch print, OSError handling).

#### 4. Add stale marker in `mark_stale_as_error()` (after line 282)

After `agents[name]["status"] = "Error"`, add:
```python
            append_to_agent_log(worktree, name, "STALE: heartbeat timeout — marked as Error")
```

#### 5. Close log handles in `graceful_shutdown()` (before the final git commit at line 585)

```python
    # Close agent log file handles
    for name, fh in _log_handles.items():
        try:
            fh.close()
        except Exception:
            pass
    _log_handles.clear()
```

### Verification
1. The change is small and focused — modify one function's subprocess call, add a helper, add cleanup
2. Run `shellcheck` on any bash files if touched (none expected here — Python only)
3. Manual testing: create a crew, add work, start runner, verify `<agent>_log.txt` files appear with headers and agent output

## Final Implementation Notes
- **Actual work done:** All 5 planned changes implemented exactly as specified — module-level `_log_handles` dict, `append_to_agent_log()` helper, `launch_agent()` log file capture replacing DEVNULL, stale marker in `mark_stale_as_error()`, and handle cleanup in `graceful_shutdown()`
- **Deviations from plan:** None — implementation matched the plan precisely
- **Issues encountered:** None
- **Key decisions:** Log files use append mode (`"a"`) so re-launches of the same agent append to the existing log rather than overwriting
- **Notes for sibling tasks:** Log files follow the existing per-agent file convention: `<agent_name>_log.txt` in the crew worktree root. The `_log_handles` dict is module-level and tracks open file handles by agent name. t439_2 (shared log utils) should glob for `*_log.txt` files in the worktree. The log header format uses `===` delimiters with agent name, type, string, timestamp, and command on separate lines, followed by a `=` x 60 separator before the actual agent output begins.

### Step 9: Post-Implementation
Archive task, commit, push per standard workflow.
