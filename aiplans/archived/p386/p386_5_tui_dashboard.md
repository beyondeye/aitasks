---
Task: t386_5_tui_dashboard.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md through t386_4_*.md, t386_6_*.md, t386_7_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md through p386_4_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: AgentCrew TUI Dashboard

## Step 1: Create bash launcher

`.aitask-scripts/aitask_crew_dashboard.sh` following `aitask_board.sh` pattern:
- Detect Python venv
- Check textual and yaml packages
- `ait_warn_if_incapable_terminal`
- `exec "$PYTHON" "$SCRIPT_DIR/agentcrew/agentcrew_dashboard.py" "$@"`

## Step 2: Implement `agentcrew_dashboard.py` — Data Layer

`CrewManager` class:
- `list_crews()` — Scan dirs + branches, read meta/status/runner files
- `load_crew(id)` — Full load of all files
- `get_runner_status(id)` — Parse `_runner_alive.yaml`, assess alive/stale/stopped
- `refresh_all()` — Reload all agentcrews (called by timer)
- `send_command(id, agent, cmd)` — `subprocess.run(["aitask_crew_command.sh", ...])`
- `start_runner(id)` — `subprocess.Popen(["ait", "agentcrew", "runner", "--crew", id], start_new_session=True)`
- `stop_runner(id)` — Write `requested_action: stop` to `_runner_alive.yaml`, git commit+push

## Step 3: Implement List Screen

Main screen showing all agentcrews:
- DataTable or custom widget per agentcrew
- Columns: ID, Name, Status, Progress, Agents (completed/total), Runner (active/stale/none + hostname)
- Keybinds: n (new), r (start runner), Enter (detail), d (delete/cleanup)
- Auto-refresh via `set_interval(5s)`

## Step 4: Implement Detail Screen

`CrewDetailScreen(Screen)`:
- Top bar: agentcrew name, status, progress bar, elapsed time, runner status
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

- Auto-detect missing runner: if agentcrew Running but no active runner → highlight with warning color
- Start: launch detached subprocess, confirm via next refresh
- Stop: commit+push `requested_action: stop`

## Step 7: CSS and Keybindings

- CSS as class constant following `aitask_board.py` patterns
- BINDINGS list: q, r, k, p, Enter, Escape, Tab

## Step 8: Add to `ait` dispatcher

Add `dashboard` subcommand to agentcrew case.

## Step 9: Verify

- `python -m py_compile .aitask-scripts/agentcrew/agentcrew_dashboard.py`
- Manual testing with created agentcrews

## Step 10: Post-Implementation (Step 9)

## Final Implementation Notes
- **Actual work done:** Created `agentcrew_dashboard.py` (~490 LOC) with `CrewManager` data layer (thin wrapper around existing `agentcrew_utils.py` functions), `AgentCrewDashboard` main app (list screen with auto-refresh), `CrewDetailScreen` (agent cards sorted by topo order, runner status bar, per-type concurrency display, agent detail panel), `AgentCard` and `CrewCard` focusable widgets with status-colored rendering. Created `aitask_crew_dashboard.sh` bash launcher following `aitask_board.sh` pattern. Added `dashboard` subcommand to `ait` dispatcher.
- **Deviations from plan:** Used `CrewCard` (custom Static widget) instead of DataTable for the list screen — provides richer per-crew rendering with inline progress bars and runner status. DAG visualization simplified to textual blocked-by labels rather than ASCII arrow art (cleaner in practice). `stop_runner()` sends kill command to all agents AND sets `requested_action: stop` on runner_alive.yaml (plan only mentioned one approach).
- **Issues encountered:** (1) DuplicateIds crash on auto-refresh: `remove_children()` is async in Textual — the old widgets weren't fully removed before `mount()` added new ones with the same IDs. Fixed by making `_refresh_data` async and awaiting both `remove_children()` and `mount()`. (2) `on_mount` can't directly await an async function — used `call_later()` for initial refresh.
- **Key decisions:** Imported `_parse_timestamp` directly from `agentcrew_utils` and reimplemented `_elapsed_since`/`_heartbeat_age` locally (avoids cross-module private import from `agentcrew_report.py`). Runner stale threshold set to 120s (vs 300s for agent heartbeats) since runner heartbeats are more frequent. Used `start_new_session=True` for runner subprocess to fully detach it from the TUI process.
- **Notes for sibling tasks:** The dashboard is available at `ait crew dashboard`. t386_6 (docs) should document the TUI keybindings and screens. t386_9 (crew runner config TUI) may want to integrate into the dashboard as a settings screen rather than a separate TUI. The `CrewManager` class is a good integration point for additional features.
