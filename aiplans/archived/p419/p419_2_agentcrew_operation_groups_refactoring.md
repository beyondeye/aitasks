---
Task: t419_2_agentcrew_operation_groups_refactoring.md
Parent Task: aitasks/t419_ait_brainstorm_architecture_design.md
Sibling Tasks: aitasks/t419/t419_1_*.md, aitasks/t419/t419_3_*.md, aitasks/t419/t419_4_*.md, aitasks/t419/t419_5_*.md, aitasks/t419/t419_6_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: AgentCrew Operation Groups Refactoring

## Context
AgentCrew needs a "group" concept so the brainstorm engine can run multiple operations in one persistent crew with priority scheduling and group-level control. This is a refactoring of existing AgentCrew code.

## Steps

### Step 1: Schema Changes

**Add `group` field to agent_status.yaml:**
In `.aitask-scripts/aitask_crew_addwork.sh`, add the `group` field to the generated `<agent>_status.yaml`. The field is optional — existing crews without groups continue to work.

```yaml
agent_name: explorer_1
agent_type: explorer
group: explore_001      # NEW: optional group identifier
status: Waiting
depends_on: []
```

**Create `_groups.yaml` schema:**
```yaml
groups:
  - name: explore_001
    sequence: 1
    description: "Initial exploration of 3 approaches"
    created_at: 2026-03-18 14:05
  - name: compare_001
    sequence: 2
    description: "Compare nodes n001, n002, n003"
    created_at: 2026-03-18 14:30
```

### Step 2: Update `ait crew addwork` (aitask_crew_addwork.sh)
- Add `--group <name>` flag to argument parsing
- When `--group` is provided:
  1. Write `group: <name>` to agent's `_status.yaml`
  2. Read `_groups.yaml` (create if missing)
  3. If group name not in list: append with next sequence number, current timestamp
  4. Write updated `_groups.yaml`
- When `--group` is omitted: write `group: ""` (empty string, for backwards compat)

### Step 3: Update Runner Scheduling (agentcrew_runner.py)
In `find_ready_agents()` or equivalent:
1. After finding all Ready agents, load `_groups.yaml` to get group→sequence mapping
2. Sort ready agents by: group sequence (ascending, no-group agents last) → then existing sort order
3. Apply per-type `max_parallel` limits as before
4. Apply overall `max_concurrent` limit as before

This ensures agents from earlier groups get launched first when capacity is constrained.

### Step 4: Group-Level Commands (aitask_crew_command.sh)
Add `send-group` subcommand:
```bash
ait crew command send-group --crew <id> --group <name> --command <cmd>
```
Implementation:
1. Read all agent `_status.yaml` files in crew worktree
2. Filter to agents where `group` matches
3. For each matching agent: append command to `_commands.yaml` (same logic as `send`)

### Step 5: Group-Level Queries

**agentcrew_status.py:**
- Add `--group <name>` flag
- When provided: filter agent list to those matching group before displaying

**agentcrew_report.py:**
- Add `--group <name>` flag
- When provided: filter to group agents for summary/detail/output reports

**agentcrew_utils.py — new helpers:**
```python
def get_group_agents(crew_dir: str, group_name: str) -> list[str]:
    """Return agent names belonging to the specified group."""

def get_group_status(crew_dir: str, group_name: str) -> str:
    """Return derived status for a group (Completed/Running/Error/Waiting)."""

def load_groups(crew_dir: str) -> list[dict]:
    """Load _groups.yaml, return list of group dicts sorted by sequence."""

def group_sort_key(agent_status: dict, groups: list[dict]) -> tuple:
    """Return sort key for group-priority scheduling."""
```

### Step 6: Dashboard Updates (agentcrew_dashboard.py)
- Add `Group` column to agent list table (show group name or "-" if none)
- Width: 15 chars, truncate with ellipsis if longer

### Step 7: Documentation (aidocs/agentcrew/agentcrew_architecture.md)
Add new section "Operation Groups" covering:
- Purpose and use cases (brainstorming, batch processing)
- `_groups.yaml` schema
- Group field in agent_status.yaml
- Priority scheduling behavior
- Group commands and queries

### Step 8: Tests
- Create a test crew with 4 agents: 2 in group `alpha` (sequence 1), 2 in group `beta` (sequence 2)
- Verify `--group` flag on addwork creates correct YAML and updates `_groups.yaml`
- Verify runner launches alpha agents before beta when at capacity
- Verify `send-group` sends to all agents in group
- Verify `status --group` and `report --group` filter correctly

## Key Files
- `.aitask-scripts/aitask_crew_addwork.sh` — add --group flag
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — group priority scheduling
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — group helpers
- `.aitask-scripts/agentcrew/agentcrew_status.py` — --group filter
- `.aitask-scripts/agentcrew/agentcrew_report.py` — --group filter
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — group column
- `.aitask-scripts/aitask_crew_command.sh` — send-group subcommand

## Verification
- Existing crews without groups continue to work (backwards compatible)
- `ait crew addwork --group explore_001` creates correct agent status and updates _groups.yaml
- Runner prioritizes lower-sequence groups
- `ait crew command send-group` sends to all group agents
- `ait crew status --group` and `ait crew report --group` filter correctly
- Dashboard shows group column
- shellcheck passes on modified bash scripts

## Final Implementation Notes
- **Actual work done:** Implemented all 8 plan steps: group helpers in utils, --group flag on addwork with _groups.yaml auto-management, runner group-priority scheduling, send-group command, --group filter on status and report, group display in dashboard, architecture docs, and 10 automated tests (24 assertions).
- **Deviations from plan:** (1) Fixed pipefail issue in addwork.sh — `grep 'sequence:'` needs `|| true` when _groups.yaml has no entries yet. (2) Added group filtering to READY_AGENTS/STALE_AGENTS output in status list. (3) Also updated t386_7 task with a note about the new group features for website docs.
- **Issues encountered:** `set -euo pipefail` caused `grep` returning exit 1 (no match) to abort the script. Fixed with `{ grep ... || true; }` pattern. Test suite initially missing `agentcrew_report.py` in setup — added it.
- **Key decisions:** (1) Group membership derived from agent `group` field in _status.yaml — no agents list in _groups.yaml (avoids double bookkeeping). (2) Agents without a group get sort key (999, name) — sorted last. (3) _groups.yaml auto-created on first `--group` usage, never removed.
- **Notes for sibling tasks:** The `_groups.yaml` schema (name, sequence, description, created_at) is the AgentCrew-core version. The brainstorm layer (t419_4+) should create `br_groups.yaml` with brainstorm-specific enrichments (operation, agents, head_at_creation, nodes_created) that wrap/extend this. The `group` field in agent_status.yaml is a simple string — no validation against _groups.yaml at the agent level. Helper functions `load_groups()`, `get_group_agents()`, `get_group_status()`, `group_sort_key()` are all in agentcrew_utils.py.

## Post-Implementation
- Step 9: archive task, push changes
