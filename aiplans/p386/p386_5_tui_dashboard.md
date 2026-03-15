---
Task: t386_5_tui_dashboard.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md through t386_4_*.md, t386_6_*.md, t386_7_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md through p386_4_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: AgentSet TUI Dashboard

## Step 1: Create bash launcher

`.aitask-scripts/aitask_agentset_dashboard.sh` following `aitask_board.sh` pattern:
- Detect Python venv
- Check textual and yaml packages
- `ait_warn_if_incapable_terminal`
- `exec "$PYTHON" "$SCRIPT_DIR/agentset/agentset_dashboard.py" "$@"`

## Step 2: Implement `agentset_dashboard.py` — Data Layer

`AgentSetManager` class:
- `list_agentsets()` — Scan dirs + branches, read meta/status/runner files
- `load_agentset(id)` — Full load of all files
- `get_runner_status(id)` — Parse `_runner_alive.yaml`, assess alive/stale/stopped
- `refresh_all()` — Reload all agentsets (called by timer)
- `send_command(id, agent, cmd)` — `subprocess.run(["aitask_agentset_command.sh", ...])`
- `start_runner(id)` — `subprocess.Popen(["ait", "agentset", "runner", "--agentset", id], start_new_session=True)`
- `stop_runner(id)` — Write `requested_action: stop` to `_runner_alive.yaml`, git commit+push

## Step 3: Implement List Screen

Main screen showing all agentsets:
- DataTable or custom widget per agentset
- Columns: ID, Name, Status, Progress, Agents (completed/total), Runner (active/stale/none + hostname)
- Keybinds: n (new), r (start runner), Enter (detail), d (delete/cleanup)
- Auto-refresh via `set_interval(5s)`

## Step 4: Implement Detail Screen

`AgentSetDetailScreen(Screen)`:
- Top bar: agentset name, status, progress bar, elapsed time, runner status
- Per-type concurrency: `implementer: 2/3 running, planner: 0/1`
- Agent list with DAG visualization (ASCII art dependency arrows)
- Agent cards: name, status (colored), progress, heartbeat age, blocked-by info
- Bottom: selected agent detail (output preview, work2do summary)

## Step 5: Agent Card Widget

`AgentCard(Static)` — focusable:
- Status coloring: Running=#50FA7B, Error=#FF5555, Waiting=#BD93F9, Completed=#6272A4, Paused=#FFB86C
- Shows: name, type, status, progress bar, heartbeat age
- Focus/blur highlighting

## Step 6: Runner Management

- Auto-detect missing runner: if agentset Running but no active runner → highlight with warning color
- Start: launch detached subprocess, confirm via next refresh
- Stop: commit+push `requested_action: stop`

## Step 7: CSS and Keybindings

- CSS as class constant following `aitask_board.py` patterns
- BINDINGS list: q, r, k, p, Enter, Escape, Tab

## Step 8: Add to `ait` dispatcher

Add `dashboard` subcommand to agentset case.

## Step 9: Verify

- `python -m py_compile .aitask-scripts/agentset/agentset_dashboard.py`
- Manual testing with created agentsets

## Step 10: Post-Implementation (Step 9)
