---
Task: t419_4_session_management_cli_scripts.md
Parent Task: aitasks/t419_ait_brainstorm_architecture_design.md
Sibling Tasks: aitasks/t419/t419_1_*.md, aitasks/t419/t419_2_*.md, aitasks/t419/t419_3_*.md, aitasks/t419/t419_5_*.md, aitasks/t419/t419_6_*.md
Archived Sibling Plans: aiplans/archived/p419/p419_1_*.md, aiplans/archived/p419/p419_3_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Session Management CLI Scripts

## Context
CLI commands for brainstorm session lifecycle. Depends on t419_1 (spec) and t419_3 (DAG library). These scripts wrap the Python library and integrate with the ait dispatcher.

## Steps

### Step 1: Dispatcher Integration (ait)
Add `brainstorm` to the `ait` dispatcher, following the `crew` subcommand pattern:

```bash
brainstorm)
    shift
    subcmd="${1:-help}"; shift 2>/dev/null || true
    case "$subcmd" in
        init)    exec "$SCRIPTS_DIR/aitask_brainstorm_init.sh" "$@" ;;
        status)  exec "$SCRIPTS_DIR/aitask_brainstorm_status.sh" "$@" ;;
        archive) exec "$SCRIPTS_DIR/aitask_brainstorm_archive.sh" "$@" ;;
        list)    exec "$SCRIPTS_DIR/aitask_brainstorm_status.sh" --list "$@" ;;
        help|--help|-h)
            # show help
            ;;
        [0-9]*)
            # numeric arg = launch TUI
            exec "$SCRIPTS_DIR/aitask_brainstorm_tui.sh" "$subcmd" "$@" ;;
        *)
            echo "ait brainstorm: unknown subcommand '$subcmd'" >&2
            exit 1 ;;
    esac
    ;;
```

Also add `brainstorm` to the help text and the skip-directory-check list.

### Step 2: aitask_brainstorm_init.sh
```bash
#!/usr/bin/env bash
set -euo pipefail
# Usage: ait brainstorm init <task_num>
# Creates .aitask-brainstorm/<task_num>/ and crew brainstorm-<task_num>
# Output: INITIALIZED:<task_num>
```

Implementation:
1. Parse `<task_num>` argument (required)
2. Resolve task file via `aitask_query_files.sh resolve <task_num>`
3. Check session doesn't already exist
4. Call Python: `brainstorm_session.init_session(task_num, task_file, email, spec)`
5. Create AgentCrew crew: `ait crew init --id "brainstorm-${task_num}" --name "Brainstorm t${task_num}"`
6. Update session.yaml with crew_id
7. Output: `INITIALIZED:<task_num>`

### Step 3: aitask_brainstorm_status.sh
```bash
#!/usr/bin/env bash
set -euo pipefail
# Usage: ait brainstorm status <task_num>
#    or: ait brainstorm status --list
```

Implementation:
- `--list` mode: iterate `.aitask-brainstorm/*/session.yaml`, display table (task_num, status, HEAD node, node count, updated_at)
- `<task_num>` mode: load session, display:
  - Session status, task link, crew status
  - HEAD node details (ID, description)
  - Node count, history summary
  - Active dimensions

### Step 4: aitask_brainstorm_archive.sh
```bash
#!/usr/bin/env bash
set -euo pipefail
# Usage: ait brainstorm archive <task_num>
# Finalizes session: copies HEAD plan to aiplans/, marks completed, cleans up crew
# Output: ARCHIVED:<task_num>, PLAN:<path>
```

Implementation:
1. Parse `<task_num>` argument
2. Load session, verify status is "active" or "paused"
3. Call Python: `brainstorm_session.finalize_session(task_num)` — copies HEAD plan to aiplans/
4. Cleanup crew: `ait crew cleanup --crew "brainstorm-${task_num}"`
5. Mark session archived: `brainstorm_session.save_session(task_num, {"status": "archived"})`
6. Output: `ARCHIVED:<task_num>` and `PLAN:<path>`

### Step 5: Verify shellcheck
Run `shellcheck` on all new scripts.

## Key Files
- `ait` — main dispatcher (modify)
- `.aitask-scripts/aitask_brainstorm_init.sh` — new
- `.aitask-scripts/aitask_brainstorm_status.sh` — new
- `.aitask-scripts/aitask_brainstorm_archive.sh` — new
- `.aitask-scripts/brainstorm/brainstorm_session.py` — from t419_3

## Verification
- `ait brainstorm init 999` creates directory structure + crew
- `ait brainstorm status 999` shows session info
- `ait brainstorm list` shows the session in table format
- `ait brainstorm archive 999` produces aiplan file and cleans up
- `ait brainstorm --help` shows available subcommands
- shellcheck passes on all new scripts

## Final Implementation Notes
- **Actual work done:** Created 5 new files: `brainstorm_cli.py` (Python CLI with 6 subcommands: init, status, list, finalize, archive, exists), `aitask_brainstorm_init.sh`, `aitask_brainstorm_status.sh`, `aitask_brainstorm_archive.sh` (bash wrappers), plus 2 test files (`test_brainstorm_cli.sh` with 20 assertions, `test_brainstorm_cli_python.py` with 10 unit tests). Modified `ait` dispatcher to add brainstorm routing, help text, and update-check skip entry.
- **Deviations from plan:** (1) Added `brainstorm_cli.py` as a Python CLI entry point not in the original plan — needed because bash scripts cannot directly call Python library functions with complex arguments. (2) Changed archive flow: archive script now calls `brainstorm_cli.py archive` which sets `_crew_status.yaml` to `Completed` before crew cleanup, since `ait crew cleanup` only processes terminal-state crews. (3) Init flow reordered: crew is created first (via `ait crew init`), then Python `init_session()` populates the existing worktree — matching the t419_3 architecture where `init_session()` expects a pre-existing crew worktree.
- **Issues encountered:** None — clean implementation.
- **Key decisions:** (1) Python CLI with argparse subparsers as the bridge between bash orchestration and Python library. (2) Positional args for task_num (simpler than `--task` flags since every brainstorm command needs exactly one task number). (3) `--spec-file` flag instead of inline spec to avoid shell quoting issues with task content.
- **Notes for sibling tasks:** The brainstorm CLI entry point is at `.aitask-scripts/brainstorm/brainstorm_cli.py` and can be extended with new subcommands. The `[0-9]*)` case in the ait dispatcher routes to `aitask_brainstorm_tui.sh` which doesn't exist yet — t419_6 (TUI) needs to create it. All bash scripts follow the Python setup pattern from `aitask_crew_report.sh` (venv preferred, system python fallback).

## Post-Implementation
- Step 9: archive task, push changes
