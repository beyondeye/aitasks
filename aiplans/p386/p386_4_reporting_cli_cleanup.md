---
Task: t386_4_reporting_cli_cleanup.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md through t386_3_*.md, t386_5_*.md through t386_7_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md through p386_3_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Reporting, CLI Integration & Cleanup

## Step 1: Implement `agentset_report.py`

Create `.aitask-scripts/agentset/agentset_report.py`:

### Sub-commands:
1. `summary <agentset_id>` — Overview with agent statuses, progress, timing, runner status
2. `detail <agentset_id> <agent_name>` — Full agent report (work2do preview, output, status, heartbeat)
3. `output <agentset_id>` — Aggregate all `*_output.md` files in dependency order (topo sort) with agent name headers
4. `list` — List all agentsets with statuses (scan `.aitask-agentsets/` + git branches)

### Output formats:
- Interactive: colored tabular display
- Batch (`--batch`): structured `PREFIX:value` lines

### Key functions:
- `list_agentsets()` in `agentset_utils.py`: scan `.aitask-agentsets/` dirs, read `_agentset_meta.yaml` + `_agentset_status.yaml` + `_runner_alive.yaml` from each
- `format_elapsed(seconds)` — Human-readable duration
- `format_table(rows, headers)` — Tabular formatting

## Step 2: Create bash wrapper

`.aitask-scripts/aitask_agentset_report.sh` — thin wrapper.

## Step 3: Implement `aitask_agentset_cleanup.sh`

Create `.aitask-scripts/aitask_agentset_cleanup.sh` (bash only):

1. Args: `--agentset <id>` or `--all-completed`, `--delete-branch`, `--batch`
2. Validate agentset is in terminal state (Completed, Error, Aborted)
3. `git worktree remove .aitask-agentsets/agentset-<id>`
4. If `--delete-branch`: `git branch -D agentset-<id>`
5. `git worktree prune`
6. Output: `CLEANED:<id>`

## Step 4: Finalize CLI integration

Update `ait` dispatcher:
- Add all remaining subcommands: `report`, `cleanup`
- Add help text section for agentset commands

## Step 5: Write tests and verify

`tests/test_agentset_report.sh`:
- Setup agentset with known state
- Test summary output contains expected fields
- Test batch output format is parseable
- Test output aggregation concatenates in correct order
- Test cleanup removes worktree
- Test `--all-completed` only cleans terminal-state agentsets

## Step 6: Post-Implementation (Step 9)
