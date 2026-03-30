---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ui, tmux]
created_at: 2026-03-30 11:41
updated_at: 2026-03-30 11:41
---

Fix `launch_in_tmux()` in `agent_launch_utils.py` silently failing when the tmux session name matches a window name.

## Root Cause

`tmux new-window -t <session>` uses the `target-window` specifier. When the session name (e.g., "aitasks") matches a window name (e.g., "aitasks" at index 3), tmux resolves it as the **window** and tries to create a new window at that same index — failing with "create window failed: index N in use". Since `subprocess.Popen` has no error handling, the failure is completely silent.

The same issue affects the `split-window` path (line 139-142). The `new-session` path is unaffected (uses `-s` flag).

## Fix

Append `:` to the session name in the `-t` target to unambiguously specify the session:
- `new-window -t session:` — creates window in session, auto-assigns next index
- `split-window -t session:window` — the `:` separates session from window name, preventing ambiguity

### Key Changes

**`.aitask-scripts/lib/agent_launch_utils.py` — `launch_in_tmux()`:**

1. **`new_window` path (line 129-134):** Change `-t config.session` to `-t f"{config.session}:"`
2. **`split_window` path (line 139-142):** The target is already `f"{config.session}:{config.window}"` which includes `:`, but verify the window value is correctly resolved (index vs name)
3. **Add basic error handling:** Capture stderr from Popen, log or notify on failure so tmux errors don't disappear silently

## Verification

1. Run `ait board` in a tmux session that has a window with the same name as the session
2. Pick a task and select "Run in tmux" → new window
3. Verify the new window is created successfully
4. Test split-window path as well
