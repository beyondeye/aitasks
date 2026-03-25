---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-25 11:41
updated_at: 2026-03-25 12:24
---

## Hard Kill Implementation

Add a `hard_kill_agent()` function to `agentcrew_runner_control.py` that sends SIGKILL to an agent process and cleans up its status file.

### Context

The existing agent control commands (kill, pause, resume) work through a file-based command queue — the runner reads `<agent>_commands.yaml` and processes commands on its next iteration. This is graceful but requires the runner to be alive. A "hard kill" sends SIGKILL directly to the agent process via OS signal, bypassing the command queue entirely. This is needed when:
- The agent process is hung and not responding to graceful commands
- The runner itself is dead and can't process commands
- Immediate termination is required

### Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — Add `hard_kill_agent()` function

### Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — Existing `send_agent_command()`, `stop_runner()` patterns
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — Lines 158-224: PID alive check pattern, lines 632-666: graceful shutdown
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — `read_yaml()`, `write_yaml()`, `crew_worktree_path()`

### Implementation Plan

1. **Add `hard_kill_agent(crew_id: str, agent_name: str) -> dict` to `agentcrew_runner_control.py`:**

   Returns `{"success": bool, "message": str, "was_alive": bool}`

   Steps:
   a. Read `<agent>_status.yaml` from crew worktree
   b. Validate: agent must have a `pid` field and status in (Running, Paused)
   c. Read `_runner_alive.yaml` to get runner hostname
   d. **Hostname safety check:** Compare runner hostname with `socket.gethostname()`. If different, return `{"success": False, "message": "Cannot hard kill remote process on <hostname>"}`
   e. **Attempt SIGKILL:**
      - Try `os.kill(pid, signal.SIGKILL)`
      - If `ProcessLookupError`: process already dead, set `was_alive = False`
      - If `PermissionError`: return error
      - If success: set `was_alive = True`
   f. **Update status file:**
      - `status` -> `Aborted`
      - `error_message` -> `"Hard killed by user"`
      - `completed_at` -> current UTC timestamp (format: `YYYY-MM-DD HH:MM:SS`)
   g. **Clear pending commands:** Read `<agent>_commands.yaml`, set `pending_commands: []`, write back
   h. **Log the action:** Append to `<agent>_log.txt`:
      ```
      [YYYY-MM-DD HH:MM:SS] HARD_KILL: Process <pid> killed by user (was_alive: <True/False>)
      ```
   i. Return success dict

2. **Import additions at top of file:**
   - `import os, signal, socket`
   - `from datetime import datetime, timezone`

### Edge Cases

- Process already dead (exited between status read and kill): still clean up status file, return success with `was_alive: False`
- No PID field in status file: return `{"success": False, "message": "No PID recorded for agent"}`
- Agent status is not Running/Paused: return `{"success": False, "message": "Agent status is <status>, not killable"}`
- Agent status file not found: return `{"success": False, "message": "Agent not found"}`

### Verification Steps

- Call `hard_kill_agent()` on a known running process — verify process is killed and status updated
- Call on an already-dead process — verify status still updated, no error
- Call with mismatched hostname — verify safety check rejects
- Verify `<agent>_log.txt` has the HARD_KILL entry
