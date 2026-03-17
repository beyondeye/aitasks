---
priority: medium
effort: high
depends: [t386_4, 1, 2, 3, 4]
issue_type: feature
status: Implementing
labels: [agentcrew, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-15 10:51
updated_at: 2026-03-17 10:49
---

## AgentCrew TUI Dashboard

### Context
This child task creates the Python/Textual TUI for managing and monitoring agentcrews. It provides real-time visibility into multi-agent DAG execution with start/stop/pause controls. Depends on t386_1-t386_4.

### Goal
Build a Textual-based TUI dashboard that monitors multiple agentcrews, displays per-agent status with DAG visualization, manages runners (per-agentcrew, cross-machine aware), and shows per-type concurrency limits.

### Key Files to Create
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — Main Textual TUI application
- `.aitask-scripts/agentcrew/__init__.py` — Package init (if not created by t386_2)
- `.aitask-scripts/aitask_crew_dashboard.sh` — Bash launcher (venv detection, textual check)

### TUI Architecture

**Data layer — `CrewManager`:**
- `list_crews()` — Scan `.aitask-crews/` dirs and `crew-*` branches
- `load_crew(id)` — Read `_crew_meta.yaml`, `_crew_status.yaml`, all agent files
- `get_runner_status(id)` — Read `_runner_alive.yaml` (after git pull)
- `send_command(id, agent, cmd)` — Call `aitask_crew_command.sh` via subprocess
- `start_runner(id)` — Launch `ait crew runner --crew <id>` as detached subprocess
- `stop_runner(id)` — Commit+push `requested_action: stop` to `_runner_alive.yaml`

**List screen:**
- All agentcrews with status, progress, runner status (active/stale/no runner)
- Runner indicator: hostname, heartbeat age
- Keybinds: n (new), r (start runner), Enter (detail), d (delete)

**Detail screen:**
- Agent DAG view with ASCII visualization
- Status colors: green=Completed, yellow=Running, red=Error, dim=Waiting
- Progress bars, auto-refresh (5s via `set_interval`)
- Runner status bar at top
- Per-type concurrency display (e.g., `implementer: 2/3 running, planner: 0/1`)

**Runner management (cross-machine via git):**
- Auto-detect missing runner: if agentcrew Running but no active runner, highlight + offer to spawn
- Start (local): launch detached subprocess, confirm via next refresh
- Stop (cross-machine): commit+push `requested_action: stop`
- External runners detected transparently via `_runner_alive.yaml`

**Agent controls:** pause/resume (via command script), kill agent

### CSS & Keybindings
Follow `aitask_board.py` patterns. Status colors: Running=#50FA7B, Error=#FF5555, Waiting=#BD93F9, Completed=#6272A4, Paused=#FFB86C.
Keybinds: q (quit), r (start/restart runner), k (kill/stop runner), p (pause all), Enter (detail), Escape (back), Tab (cycle focus).

### Reference Files for Patterns
- `.aitask-scripts/board/aitask_board.py` — TaskManager, ModalScreen, timer refresh, subprocess integration, CSS styling
- `.aitask-scripts/aitask_board.sh` — Bash launcher pattern
- `.aitask-scripts/codebrowser/codebrowser_app.py` — Alternative Textual app pattern

### Verification
- `python -m py_compile .aitask-scripts/agentcrew/agentcrew_dashboard.py`
- Manual testing: create agentcrew via CLI, launch dashboard, verify display, test runner controls
