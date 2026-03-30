---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [board, tmux]
created_at: 2026-03-30 10:14
updated_at: 2026-03-30 10:14
---

## Bug: tmux execution path drops task argument from claude command

When launching `aitask-pick` from the board TUI via tmux, the task argument (e.g., `475_4`) is lost. Claude opens with only `/aitask-pick` instead of `/aitask-pick 475_4`. The direct terminal path works correctly.

### Root Cause

The dry-run output in `aitask_codeagent.sh` (line 608) uses `${CMD[*]}` to flatten the CMD array into a string, which loses element boundaries:

1. **Line 523:** `CMD+=("/aitask-pick ${args[*]}")` — creates a single array element with slash command + args
2. **Line 608:** `echo "DRY_RUN: ${CMD[*]}"` — flattens array, quoting around `/aitask-pick 475_4` is lost
3. **Python `resolve_dry_run_command()`** (`agent_launch_utils.py:66`) returns the flat string
4. **`launch_in_tmux()`** (`agent_launch_utils.py:120/132/141`) passes this flat string to tmux
5. tmux's shell splits `/aitask-pick 475_4` into two separate arguments for `claude`
6. `claude` receives `/aitask-pick` as the slash command without `475_4`

### Why the direct path works

`aitask_board.py:3409` uses `subprocess.Popen([terminal, "--", wrapper, "invoke", "pick", num])` — calls the wrapper directly with proper argument separation, bypassing the dry-run string.

### Fix

Make the dry-run output shell-safe by properly quoting CMD array elements that contain spaces. Use `printf '%q'` or similar to preserve argument boundaries when the command is later executed by a shell (as tmux does).

### Files involved

- `.aitask-scripts/aitask_codeagent.sh` — line 608 (dry-run output), line 523 (CMD construction)
- `.aitask-scripts/lib/agent_launch_utils.py` — `resolve_dry_run_command()`, `launch_in_tmux()`
- `.aitask-scripts/board/aitask_board.py` — `_resolve_pick_command()`, tmux launch path
