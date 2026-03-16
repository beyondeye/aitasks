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

## Step 1: Implement `agentcrew_report.py`

Create `.aitask-scripts/agentcrew/agentcrew_report.py`:

### Sub-commands:
1. `summary <crew_id>` — Overview with agent statuses, progress, timing, runner status
2. `detail <crew_id> <agent_name>` — Full agent report (work2do preview, output, status, heartbeat)
3. `output <crew_id>` — Aggregate all `*_output.md` files in dependency order (topo sort) with agent name headers
4. `list` — List all agentcrews with statuses (scan `.aitask-crews/` + git branches)

### Output formats:
- Interactive: colored tabular display
- Batch (`--batch`): structured `PREFIX:value` lines

### Key functions:
- `list_crews()` in `agentcrew_utils.py`: scan `.aitask-crews/` dirs, read `_crew_meta.yaml` + `_crew_status.yaml` + `_runner_alive.yaml` from each
- `format_elapsed(seconds)` — Human-readable duration
- `format_table(rows, headers)` — Tabular formatting

## Step 2: Create bash wrapper

`.aitask-scripts/aitask_crew_report.sh` — thin wrapper.

## Step 3: Implement `aitask_crew_cleanup.sh`

Create `.aitask-scripts/aitask_crew_cleanup.sh` (bash only):

1. Args: `--crew <id>` or `--all-completed`, `--delete-branch`, `--batch`
2. Validate agentcrew is in terminal state (Completed, Error, Aborted)
3. `git worktree remove .aitask-crews/crew-<id>`
4. If `--delete-branch`: `git branch -D crew-<id>`
5. `git worktree prune`
6. Output: `CLEANED:<id>`

## Step 4: Finalize CLI integration

Update `ait` dispatcher:
- Add all remaining subcommands: `report`, `cleanup`
- Add help text section for agentcrew commands

## Step 5: Write tests and verify

`tests/test_crew_report.sh`:
- Setup agentcrew with known state
- Test summary output contains expected fields
- Test batch output format is parseable
- Test output aggregation concatenates in correct order
- Test cleanup removes worktree
- Test `--all-completed` only cleans terminal-state agentcrews

## Step 6: Post-Implementation (Step 9)
