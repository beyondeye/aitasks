---
Task: t452_reset_errored_agents_on_runner_restart.md
Worktree: (current directory)
Branch: main
Base branch: main
---

# Plan: Reset Errored Agents on Runner Restart (t452)

## Context

When an agent errors (e.g., heartbeat timeout), the runner stops because all agents are terminal. Restarting the runner finds agents still in Error state, triggers `all_terminal` check (line 758-762), and stops again after ~1 second. No way to retry without manually editing YAML files.

Two mechanisms needed: (1) CLI `--reset-errors` flag for bulk reset at runner startup, (2) per-agent reset button in the TUI dashboard for targeted resets.

## Implementation

### Step 1: Allow Error → Waiting transition (`agentcrew_utils.py`)

**File:** `.aitask-scripts/agentcrew/agentcrew_utils.py` line 31

Change `"Error": []` to `"Error": ["Waiting"]` in `AGENT_TRANSITIONS`.

### Step 2: Add `--reset-errors` CLI flag (`agentcrew_runner.py`)

**File:** `.aitask-scripts/agentcrew/agentcrew_runner.py`

Add after the `--force` argument (line 816):
```python
parser.add_argument("--reset-errors", action="store_true",
                    help="Reset Error agents back to Waiting before starting")
```

Pass the flag to `run_loop()` at line 852.

### Step 3: Add reset logic in `run_loop()` (`agentcrew_runner.py`)

Add `reset_errors: bool = False` parameter to `run_loop()`.

Add reset logic after the initial `write_runner_alive` block (after line 683), before the main loop. Runs once at startup.

### Step 4: Add `reset` to valid commands (`aitask_crew_command.sh`)

**File:** `.aitask-scripts/aitask_crew_command.sh` line 23

### Step 5: Handle `reset` command in runner (`agentcrew_runner.py`)

In `process_pending_commands()`, add elif branch for `reset` command on Error agents.

### Step 6: Add per-agent reset button in TUI dashboard (`agentcrew_dashboard.py`)

Add `w` keybinding for "Reset to Waiting" and `action_reset_agent()` method in `CrewDetailScreen`.

### Step 7: Add tests (`tests/test_crew_runner.sh`)

5 new tests: reset-errors flag, ALL_TERMINAL without flag, reset command via shell, process_pending_commands handling, transition validation.

## Final Implementation Notes

**All steps completed successfully.** Files modified:
1. `.aitask-scripts/agentcrew/agentcrew_utils.py` — Added `Error → Waiting` transition
2. `.aitask-scripts/agentcrew/agentcrew_runner.py` — `--reset-errors` CLI flag, startup reset logic, `reset` command handling in `process_pending_commands()`, batch output (`RESET:`, `RESET_DRY:`, `CMD_RESET:`)
3. `.aitask-scripts/aitask_crew_command.sh` — Added `reset` to `VALID_COMMANDS`
4. `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — `w` keybinding + `action_reset_agent()` for per-agent Error→Waiting reset
5. `tests/test_crew_runner.sh` — 5 new tests (Tests 11-15), all passing. 31 total tests pass.

**Design decisions:**
- Reset in dry-run mode logs `RESET_DRY:<name>` without modifying files
- Reset in non-dry-run mode logs `RESET:<name>` and modifies files
- Command-based reset logs `CMD_RESET:<name>` for batch consumers
- TUI reset only allowed for Error state agents (clear guard in `action_reset_agent`)
