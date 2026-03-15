---
priority: medium
effort: medium
depends: [t386_3, 1, 2, 3]
issue_type: feature
status: Ready
labels: [subagents]
created_at: 2026-03-15 10:51
updated_at: 2026-03-15 10:51
---

## Reporting, CLI Integration & Cleanup

### Context
This child task adds comprehensive reporting, cleanup functionality, and full CLI integration for the AgentSet infrastructure. It depends on t386_1, t386_2, and t386_3.

### Goal
Implement status reports with output aggregation (Python core), agentset cleanup (bash), and finalize the `ait agentset` CLI with complete help text.

### Key Files to Create
- `.aitask-scripts/agentset/agentset_report.py` — Python core: sub-commands `summary`, `detail`, `output`, `list`
- `.aitask-scripts/aitask_agentset_report.sh` — Thin bash wrapper
- `.aitask-scripts/aitask_agentset_cleanup.sh` — Bash-only: `--agentset <id>` or `--all-completed`. Validates terminal state (Completed/Error/Aborted), `git worktree remove`, optionally `git branch -D`, `git worktree prune`
- `tests/test_agentset_report.sh` — Tests for report formats, cleanup

### Report Formats

**Summary** (interactive):
```
AgentSet: my-feature (Running)
Created: 2026-03-15 10:00 | Elapsed: 45m | Progress: 66%

Agents:
  agent-a    Completed   100%  (12m)
  agent-b    Running      45%  (20m, heartbeat: 30s ago)
  agent-c    Waiting       0%  (blocked by: agent-b)
```

**Batch output:**
```
AGENTSET_ID:my-feature
AGENTSET_STATUS:Running
AGENTSET_PROGRESS:66
AGENT:agent-a STATUS:Completed PROGRESS:100 ELAPSED:720
AGENT:agent-b STATUS:Running PROGRESS:45 ELAPSED:1200
AGENT:agent-c STATUS:Waiting PROGRESS:0 BLOCKED_BY:agent-b
```

**Output aggregation:** Concatenate all `*_output.md` files in dependency order with agent name headers.

### CLI Integration
- Update `ait` dispatcher help text with agentset commands section
- `list_agentsets()` in `agentset_utils.py`: scan `.aitask-agentsets/` + git branches for `agentset-*`

### Reference Files for Patterns
- `.aitask-scripts/board/task_yaml.py` — YAML handling
- `.aitask-scripts/aitask_ls.sh` — Tabular output
- `.aitask-scripts/aitask_board.sh` — Python launcher

### Verification
- `bash tests/test_agentset_report.sh`
- `python -m py_compile .aitask-scripts/agentset/agentset_report.py`
- `shellcheck .aitask-scripts/aitask_agentset_cleanup.sh`
