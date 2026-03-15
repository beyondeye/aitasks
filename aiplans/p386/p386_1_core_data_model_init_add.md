---
Task: t386_1_core_data_model_init_add.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_2_*.md through t386_7_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Core Data Model & AgentSet Init/Add Scripts

## Step 1: Create `lib/agentset_utils.sh`

Create `.aitask-scripts/lib/agentset_utils.sh` with:

1. Guard variable: `_AIT_AGENTSET_UTILS_LOADED`
2. Source `terminal_compat.sh` and `task_utils.sh`
3. Constants:
   - `AGENTSET_BRANCH_PREFIX="agentset-"`
   - `AGENTSET_DIR=".aitask-agentsets"`
4. Helper functions:
   - `agentset_branch_name()` — `agentset-<id>`
   - `agentset_worktree_path()` — `.aitask-agentsets/agentset-<id>`
   - `validate_agentset_id()` — Enforce `[a-z0-9_-]+`
   - `validate_agent_name()` — Enforce `[a-z0-9_]+`
   - `resolve_agentset()` — Check worktree exists, return path
   - `read_yaml_field()` — Extract field from YAML file (grep/sed)
   - `write_yaml_file()` — Write YAML via heredoc
   - `detect_circular_deps()` — DFS cycle detection reading all `*_status.yaml` files, building adjacency from `depends_on` fields

## Step 2: Create `aitask_agentset_init.sh`

Create `.aitask-scripts/aitask_agentset_init.sh`:

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
   - `mkdir -p .aitask-agentsets`
   - `git branch agentset-<id>` from current HEAD
   - `git worktree add .aitask-agentsets/agentset-<id> agentset-<id>`
   - Write `_agentset_meta.yaml` with agent_types from `--add-type` flags
   - Write `_agentset_status.yaml` with `status: Initializing`
   - `cd` to worktree, `git add`, `git commit`
   - Output: `CREATED:<id>`

## Step 3: Create `aitask_agentset_add.sh`

Create `.aitask-scripts/aitask_agentset_add.sh`:

1. Standard header
2. Argument parsing:
   - `--agentset <id>` (required)
   - `--name <agent_name>` (required)
   - `--work2do <file_path>` (required, or `-` for stdin)
   - `--depends <agent1,agent2>` (optional)
   - `--type <agent_type_id>` (required)
   - `--batch`
3. Implementation:
   - Resolve agentset worktree path
   - Validate agent name uniqueness (check no existing `<name>_status.yaml`)
   - Validate type exists in `_agentset_meta.yaml`
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
   - Update `_agentset_meta.yaml` agents list
   - Output: `ADDED:<name>`

## Step 4: Add `agentset` to `ait` dispatcher

Edit `ait`:
- Add case in the main command dispatcher:
  ```bash
  agentset)
      shift
      subcmd="${1:-}"
      shift || true
      case "$subcmd" in
          init)    exec "$SCRIPTS_DIR/aitask_agentset_init.sh" "$@" ;;
          add)     exec "$SCRIPTS_DIR/aitask_agentset_add.sh" "$@" ;;
          # ... more subcommands added by later child tasks
          *)       die "Unknown agentset subcommand: $subcmd" ;;
      esac
      ;;
  ```

## Step 5: Add `.aitask-agentsets` to `.gitignore`

Append `.aitask-agentsets` to `.gitignore`.

## Step 6: Write tests

Create `tests/test_agentset_init.sh`:
- Test init creates branch and worktree
- Test init with `--add-type` creates agent_types in meta
- Test add creates all 7 agent files
- Test add validates agent name uniqueness
- Test add validates type exists
- Test circular dependency detection rejects cycles
- Test DAG validation accepts valid graphs

## Step 7: Verify

- `bash tests/test_agentset_init.sh`
- `shellcheck .aitask-scripts/aitask_agentset_init.sh .aitask-scripts/aitask_agentset_add.sh .aitask-scripts/lib/agentset_utils.sh`

## Step 8: Post-Implementation (Step 9)

Archive task, update parent, push.
