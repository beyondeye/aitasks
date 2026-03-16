---
Task: t386_1_core_data_model_init_add.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_2_*.md through t386_7_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Core Data Model & AgentCrew Init/Add Scripts

## Step 1: Create `lib/agentcrew_utils.sh`

Create `.aitask-scripts/lib/agentcrew_utils.sh` with:

1. Guard variable: `_AIT_AGENTCREW_UTILS_LOADED`
2. Source `terminal_compat.sh` and `task_utils.sh`
3. Constants:
   - `AGENTCREW_BRANCH_PREFIX="crew-"`
   - `AGENTCREW_DIR=".aitask-crews"`
4. Helper functions:
   - `crew_branch_name()` — `crew-<id>`
   - `agentcrew_worktree_path()` — `.aitask-crews/crew-<id>`
   - `validate_crew_id()` — Enforce `[a-z0-9_-]+`
   - `validate_agent_name()` — Enforce `[a-z0-9_]+`
   - `resolve_crew()` — Check worktree exists, return path
   - `read_yaml_field()` — Extract field from YAML file (grep/sed)
   - `write_yaml_file()` — Write YAML via heredoc
   - `detect_circular_deps()` — DFS cycle detection reading all `*_status.yaml` files, building adjacency from `depends_on` fields

## Step 2: Create `aitask_crew_init.sh`

Create `.aitask-scripts/aitask_crew_init.sh`:

1. Standard header (`#!/usr/bin/env bash`, `set -euo pipefail`, source libs)
2. Argument parsing:
   - `--id <id>` (required)
   - `--name <display_name>` (optional, defaults to id)
   - `--add-type <type_id>:<agent_string>` (repeatable)
   - `--batch`
   - `--help`
3. Implementation:
   - Validate id format
   - Check branch doesn't already exist
   - `mkdir -p .aitask-crews`
   - `git branch crew-<id>` from current HEAD
   - `git worktree add .aitask-crews/crew-<id> crew-<id>`
   - Write `_crew_meta.yaml` with agent_types from `--add-type` flags
   - Write `_crew_status.yaml` with `status: Initializing`
   - `cd` to worktree, `git add`, `git commit`
   - Output: `CREATED:<id>`

## Step 3: Create `aitask_crew_addwork.sh`

CLI command: `ait crew addwork` (renamed from `addtask` to avoid nomenclature clash with aitasks).

Create `.aitask-scripts/aitask_crew_addwork.sh`:

1. Standard header
2. Argument parsing:
   - `--crew <id>` (required)
   - `--name <agent_name>` (required)
   - `--work2do <file_path>` (required, or `-` for stdin)
   - `--depends <agent1,agent2>` (optional)
   - `--type <agent_type_id>` (required)
   - `--batch`
3. Implementation:
   - Resolve agentcrew worktree path
   - Validate agent name uniqueness (check no existing `<name>_status.yaml`)
   - Validate type exists in `_crew_meta.yaml`
   - Validate dependencies exist
   - Run `detect_circular_deps()` with proposed new agent
   - Create 7 agent files from templates:
     - `<name>_work2do.md` — Copy from `--work2do` file
     - `<name>_status.yaml` — Initial YAML with status: Waiting, depends_on, agent_type
     - `<name>_input.md` — Empty placeholder
     - `<name>_output.md` — Empty placeholder
     - `<name>_instructions.md` — Default lifecycle instructions template
     - `<name>_commands.yaml` — `pending_commands: []`
     - `<name>_alive.yaml` — Empty heartbeat
   - Update `_crew_meta.yaml` agents list
   - Output: `ADDED:<name>`

## Step 4: Add `crew` to `ait` dispatcher

Edit `ait`:
- Add case in the main command dispatcher:
  ```bash
  crew)
      shift
      subcmd="${1:-}"
      shift || true
      case "$subcmd" in
          init)      exec "$SCRIPTS_DIR/aitask_crew_init.sh" "$@" ;;
          addwork)   exec "$SCRIPTS_DIR/aitask_crew_addwork.sh" "$@" ;;
          # ... more subcommands added by later child tasks
          *)         echo "ait crew: unknown subcommand '$subcmd'" >&2; exit 1 ;;
      esac
      ;;
  ```
- Add `crew` to the update-skip list on line 129

## Step 5: Add `.aitask-crews` to `.gitignore`

Append `.aitask-crews` to `.gitignore`.

## Step 6: Write tests

Create `tests/test_crew_init.sh`:
- Test init creates branch and worktree
- Test init with `--add-type` creates agent_types in meta
- Test add creates all 7 agent files
- Test add validates agent name uniqueness
- Test add validates type exists
- Test circular dependency detection rejects cycles
- Test DAG validation accepts valid graphs

## Step 7: Verify

- `bash tests/test_crew_init.sh`
- `shellcheck .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh .aitask-scripts/lib/agentcrew_utils.sh`

## Step 8: Post-Implementation (Step 9)

Archive task, update parent, push.

## Final Implementation Notes
- **Actual work done:** Created 3 new scripts (`agentcrew_utils.sh`, `aitask_crew_init.sh`, `aitask_crew_addwork.sh`), integrated `crew` subcommand into `ait` dispatcher, added `.aitask-crews/` to `.gitignore`, and wrote comprehensive test suite (`test_crew_init.sh`, 11 tests, 32 assertions).
- **Deviations from plan:** Renamed CLI subcommand from `addtask` to `addwork` (user preference to avoid nomenclature clash with aitasks). Added `read_yaml_list()` and `append_yaml_list_item()` helper functions to `agentcrew_utils.sh` (not in original plan but needed for managing the `agents` list in `_crew_meta.yaml`). Added status constants (`AGENT_STATUS_*`, `CREW_STATUS_*`) to the utils library for use by downstream scripts. `agentcrew_utils.sh` sources only `terminal_compat.sh` (not `task_utils.sh`) since no task-utils functions were needed.
- **Issues encountered:** (1) `read_yaml_field()` failed under `pipefail` when `grep` found no match — fixed with `{ grep ... || true; }` wrapper. (2) `detect_circular_deps()` glob `*_status.yaml` matched `_crew_status.yaml` (crew-level, not agent-level) — fixed by skipping files named `_crew_status.yaml`. (3) Test counters didn't propagate from subshells — switched to file-based counter approach. (4) Shellcheck SC2034 warnings for library constants — used block-disable `{ ... }` approach.
- **Key decisions:** YAML parsing uses simple `grep+sed` (consistent with project convention). Circular dependency detection uses iterative DFS with explicit stack (avoids bash recursion limits). Each `git commit` in the worktree is done inside a `( cd ... )` subshell to avoid changing the caller's working directory.
- **Notes for sibling tasks:** The naming convention is `ait crew <subcommand>`. The utils library is at `.aitask-scripts/lib/agentcrew_utils.sh` — source it for constants and helpers. Status constants are defined there (`AGENT_STATUS_*`, `CREW_STATUS_*`). The `read_yaml_field()`, `read_yaml_list()`, and `append_yaml_list_item()` functions are available for YAML manipulation. All pipefail-safe. The `_crew_meta.yaml` `agents` field uses inline YAML list format `[a, b, c]`.
