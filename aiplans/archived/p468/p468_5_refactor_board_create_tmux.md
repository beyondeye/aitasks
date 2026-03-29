---
Task: t468_5_refactor_board_create_tmux.md
Parent Task: aitasks/t468_better_codeagent_launching.md
Sibling Tasks: aitasks/t468/t468_6_update_docs_tmux_integration.md, aitasks/t468/t468_7_auto_launch_tuis_in_tmux.md
Archived Sibling Plans: aiplans/archived/p468/p468_1_*.md, aiplans/archived/p468/p468_2_*.md, aiplans/archived/p468/p468_3_*.md, aiplans/archived/p468/p468_4_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Refactor Board Create Task with Tmux Support (t468_5)

## Overview

Add `AgentCommandScreen` dialog to board's `action_create_task()`, matching the pick command pattern. Users can choose to run task creation in a terminal window or tmux pane.

## Steps

### Step 1: Add `CREATE_SCRIPT` constant

Added `CREATE_SCRIPT = Path(".aitask-scripts") / "aitask_create.sh"` alongside existing `CODEAGENT_SCRIPT` constant at top of file.

### Step 2: Refactor `action_create_task()` to show dialog

Replaced direct Popen/suspend launch with `AgentCommandScreen` push:
- Title: "Create Task"
- Full command: `./{CREATE_SCRIPT}`
- Prompt: "ait create"
- Default window name: "create-task"
- Callback handles `"run"` (terminal), `TmuxLaunchConfig` (tmux), and reload/refresh

### Step 3: Extract `_run_create_in_terminal()` helper

Moved existing terminal/suspend launch logic into `@work(exclusive=True)` async helper (mirrors `run_aitask_pick()` pattern).

### Step 4: Fix `prefer_tmux` tab pre-selection (in agent_command_screen.py)

Pre-existing bug: `AgentCommandScreen` loaded `prefer_tmux` from config but never used it. Added tab switch in `on_mount()` to pre-select tmux tab when `prefer_tmux` is enabled. Fixes all dialogs (pick, explain, qa, create).

## Final Implementation Notes

- **Actual work done:** Refactored `action_create_task()` to use `AgentCommandScreen` dialog with Direct/Tmux tabs. Fixed `prefer_tmux` tab pre-selection bug in `agent_command_screen.py`.
- **Deviations from plan:** Original task described using `tmux.use_for_create` setting, but p468_4 replaced that with `prefer_tmux` (pre-selects tmux tab in all dialogs). The implementation follows the updated approach. Also discovered and fixed the pre-existing `prefer_tmux` bug.
- **Issues encountered:** None.
- **Key decisions:**
  - Used `CREATE_SCRIPT` constant at file top (matching `CODEAGENT_SCRIPT` pattern) rather than hardcoded paths
  - No dry-run resolution needed for create (static command, not a code agent invocation)
  - Dialog shows `ait create` as the "prompt" string (user-friendly CLI alias)
- **Notes for sibling tasks:**
  - t474 (create tmux support) is a duplicate of this task and should be folded/closed
  - t468_7 (auto-launch TUIs in tmux): The `prefer_tmux` fix in `agent_command_screen.py` is now working — tmux tab pre-selected when enabled
  - t468_6 (docs): Document that the create dialog now matches the pick dialog pattern with Direct/Tmux tabs
