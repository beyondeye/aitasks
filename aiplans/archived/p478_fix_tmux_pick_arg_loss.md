---
Task: t478_fix_tmux_pick_arg_loss.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

When launching `aitask-pick` (or explain/qa) from the board TUI or codebrowser via tmux, the task argument gets lost. For example, `claude --model claude-opus-4-6 /aitask-pick 475_4` opens claude with only `/aitask-pick` — the `475_4` parameter is dropped. The direct terminal path works fine.

**Root cause:** `aitask_codeagent.sh` line 608 uses `echo "DRY_RUN: ${CMD[*]}"` which flattens the CMD array into a plain string, losing the fact that `/aitask-pick 475_4` is a single array element. When tmux's shell parses this string, it splits `/aitask-pick` and `475_4` into two separate arguments for `claude`.

## Plan

### Step 1: Fix dry-run output in `aitask_codeagent.sh`

**File:** `.aitask-scripts/aitask_codeagent.sh` (line 607-609)

Replace `echo "DRY_RUN: ${CMD[*]}"` with `printf '%q'`-based output that shell-quotes each array element, preserving argument boundaries when the string is later eval'd by tmux's shell.

### Files modified
- `.aitask-scripts/aitask_codeagent.sh` — line 608 only

### Impact
Fixes the same bug for all callers of `resolve_dry_run_command`:
- `aitask_board.py` — pick via tmux
- `codebrowser_app.py` — explain via tmux
- `history_screen.py` — qa via tmux

## Final Implementation Notes
- **Actual work done:** Changed dry-run output from `echo "DRY_RUN: ${CMD[*]}"` to `printf '%q'`-based output (3 printf calls). This is a 1-line-to-3-line change in a single file.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** The existing `test_codeagent.sh` test fails at test 2 due to a pre-existing issue (missing `archive_utils.sh` in test env setup). The specific dry-run assertions (test 11) were verified manually and all pass.
- **Key decisions:** Used `printf '%q'` (bash builtin) rather than manual quoting. This is the standard bash idiom for producing shell-safe output from arrays. It handles all special characters, not just spaces.
