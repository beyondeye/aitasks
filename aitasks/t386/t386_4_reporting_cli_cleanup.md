---
priority: medium
effort: medium
depends: [t386_3, 1, 2, 3]
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-15 10:51
updated_at: 2026-03-17 10:24
---

## Reporting, CLI Integration & Cleanup

### Context
This child task adds comprehensive reporting, cleanup functionality, and full CLI integration for the AgentCrew infrastructure. It depends on t386_1, t386_2, and t386_3.

### Goal
Implement status reports with output aggregation (Python core), agentcrew cleanup (bash), and finalize the `ait crew` CLI with complete help text.

### Key Files to Create
- `.aitask-scripts/agentcrew/agentcrew_report.py` — Python core: sub-commands `summary`, `detail`, `output`, `list`
- `.aitask-scripts/aitask_crew_report.sh` — Thin bash wrapper
- `.aitask-scripts/aitask_crew_cleanup.sh` — Bash-only: `--crew <id>` or `--all-completed`. Validates terminal state (Completed/Error/Aborted), `git worktree remove`, optionally `git branch -D`, `git worktree prune`
- `tests/test_crew_report.sh` — Tests for report formats, cleanup

### Report Formats

**Summary** (interactive):
```
Crew: my-feature (Running)
Created: 2026-03-15 10:00 | Elapsed: 45m | Progress: 66%

Agents:
  agent-a    Completed   100%  (12m)
  agent-b    Running      45%  (20m, heartbeat: 30s ago)
  agent-c    Waiting       0%  (blocked by: agent-b)
```

**Batch output:**
```
CREW_ID:my-feature
CREW_STATUS:Running
CREW_PROGRESS:66
AGENT:agent-a STATUS:Completed PROGRESS:100 ELAPSED:720
AGENT:agent-b STATUS:Running PROGRESS:45 ELAPSED:1200
AGENT:agent-c STATUS:Waiting PROGRESS:0 BLOCKED_BY:agent-b
```

**Output aggregation:** Concatenate all `*_output.md` files in dependency order with agent name headers.

### CLI Integration
- Update `ait` dispatcher help text with agentcrew commands section
- `list_crews()` in `agentcrew_utils.py`: scan `.aitask-crews/` + git branches for `crew-*`

### Reference Files for Patterns
- `.aitask-scripts/board/task_yaml.py` — YAML handling
- `.aitask-scripts/aitask_ls.sh` — Tabular output
- `.aitask-scripts/aitask_board.sh` — Python launcher

### Verification
- `bash tests/test_crew_report.sh`
- `python -m py_compile .aitask-scripts/agentcrew/agentcrew_report.py`
- `shellcheck .aitask-scripts/aitask_crew_cleanup.sh`
