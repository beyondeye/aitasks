---
Task: t483_fix_tmux_session_target_ambiguity.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

`launch_in_tmux()` in `agent_launch_utils.py` silently fails when the tmux session name matches a window name. The `new-window` path passes `config.session` as `-t` target, but tmux's `-t` for `new-window` is `target-window`. When "aitasks" matches both session and window name, tmux resolves it as the window and tries to create at that index — failing with "index in use". The `split-window` path's target already includes `:` so it's correct.

## Plan

### 1. Fix session target in `new-window` path

**File:** `.aitask-scripts/lib/agent_launch_utils.py` (line 130)

Change:
```python
"tmux", "new-window", "-t", config.session,
```
To:
```python
"tmux", "new-window", "-t", f"{config.session}:",
```

The trailing `:` tells tmux to interpret the target as a session (not a window) and auto-assign the next available window index.

### 2. Add basic error handling

In the `new_window` branch (lines 128-134), capture the result and log errors instead of silently failing:

```python
elif config.new_window:
    tmux_cmd = [
        "tmux", "new-window", "-t", f"{config.session}:",
        "-n", config.window,
        command,
    ]
    proc = subprocess.Popen(tmux_cmd, stderr=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        print(f"tmux new-window failed: {stderr}", file=sys.stderr)
    return proc
```

Same for the `split-window` branch (lines 135-143):

```python
else:
    split_flag = "-h" if config.split_direction == "horizontal" else "-v"
    target = f"{config.session}:{config.window}"
    tmux_cmd = [
        "tmux", "split-window", split_flag, "-t", target,
        command,
    ]
    proc = subprocess.Popen(tmux_cmd, stderr=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        print(f"tmux split-window failed: {stderr}", file=sys.stderr)
    return proc
```

Add `import sys` if not already imported (it's not currently imported).

## Verification

1. Run `ait board` in the "aitasks" tmux session (which has a window also named "aitasks")
2. Pick a task → select tmux tab → Run in tmux (new window)
3. Verify a new window is created at the next available index
4. Test split-window path as well (select existing window instead of new window)

## Final Implementation Notes
- **Actual work done:** Fixed `new-window` target by appending `:` to session name, added `import sys`, added error handling with stderr capture and logging to both `new_window` and `split_window` paths
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** Used `proc.wait()` + stderr check pattern (consistent with existing `new_session` path which already calls `proc.wait()`)

## Step 9 Reference

Post-implementation: archive task, push changes per task-workflow Step 9.
