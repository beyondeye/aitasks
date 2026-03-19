---
priority: medium
effort: medium
depends: [t419_3, 1, 3]
issue_type: feature
status: Implementing
labels: [brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-18 14:58
updated_at: 2026-03-19 10:20
---

## Context
The brainstorm engine (t419) needs CLI commands accessible via the ait dispatcher. These scripts wrap the Python DAG library (t419_3) and integrate with AgentCrew for crew management.

## Key Files to Read
- aidocs/brainstorming/brainstorm_engine_architecture.md — session lifecycle (created by t419_1)
- .aitask-scripts/brainstorm/brainstorm_session.py — Python session management (created by t419_3)
- .aitask-scripts/brainstorm/brainstorm_dag.py — Python DAG operations (created by t419_3)
- ait — main dispatcher, see the crew subcommand pattern for reference

## Reference Files for Patterns
- .aitask-scripts/aitask_crew_init.sh — crew initialization pattern (creates branch + worktree)
- .aitask-scripts/aitask_crew_cleanup.sh — cleanup pattern
- ait — dispatcher routing for crew subcommands (lines 165-194)

## Deliverable

### aitask_brainstorm.sh — Sub-dispatcher
Routes ait brainstorm subcommands:
- ait brainstorm init task_num — calls aitask_brainstorm_init.sh
- ait brainstorm status task_num — calls aitask_brainstorm_status.sh
- ait brainstorm archive task_num — calls aitask_brainstorm_archive.sh
- ait brainstorm list — calls aitask_brainstorm_status.sh --list
- ait brainstorm task_num — launches TUI (aitask_brainstorm_tui.sh)

### aitask_brainstorm_init.sh
- Accepts --task task_num (required)
- Creates .aitask-brainstorm/task_num/ directory structure via brainstorm_session.py
- Creates AgentCrew crew brainstorm-task_num via ait crew init
- Reads task file for initial context
- Output: INITIALIZED:task_num

### aitask_brainstorm_status.sh
- Accepts --task task_num or --list
- --list mode: lists all .aitask-brainstorm/*/session.yaml with status summary
- --task mode: displays session details (HEAD node, node count, crew status)
- Output: structured YAML or formatted text

### aitask_brainstorm_archive.sh
- Accepts --task task_num
- Copies HEAD node plan to aiplans/p_task_num_name.md
- Marks session as completed/archived
- Cleans up crew via ait crew cleanup
- Output: ARCHIVED:task_num, PLAN:aiplans/path

### Dispatcher Integration
- Add brainstorm to ait help text
- Add brainstorm routing in ait dispatcher (follows crew pattern)

## Verification
- ait brainstorm init 999 creates directory structure and crew
- ait brainstorm status 999 shows session info
- ait brainstorm list shows the session
- ait brainstorm archive 999 produces aiplan and cleans up
- shellcheck passes on all new scripts
