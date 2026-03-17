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

## Final Implementation Notes
- **Actual work done:** Created `agentcrew_report.py` (~280 LOC) with 4 sub-commands (summary, detail, output, list) supporting both interactive and batch output modes. Added `list_crews()` and `format_elapsed()` to `agentcrew_utils.py`. Created `aitask_crew_report.sh` (thin Python wrapper following `aitask_crew_status.sh` pattern). Created `aitask_crew_cleanup.sh` (pure bash, validates terminal state before cleanup, supports `--crew`, `--all-completed`, `--delete-branch`). Updated `ait` dispatcher with `report` and `cleanup` subcommands and added AgentCrew section to help text. Wrote comprehensive test suite (11 tests, 28 assertions).
- **Deviations from plan:** The plan mentioned a `format_table(rows, headers)` function — implemented inline column-width calculation instead, which is simpler and avoids a helper for one-off use. Output aggregation uses `OUTPUT_AGENT:` / `OUTPUT_END:` delimiters in batch mode (not in original plan) for clean parsing of multi-line output content. Added `NOT_FOUND` structured output for cleanup when crew doesn't exist. `list_crews()` currently only scans `.aitask-crews/` directories (not git branches), which is sufficient since all active crews have worktrees.
- **Issues encountered:** (1) Test subshells used `local` outside functions — fixed by removing `local` keyword. (2) SC1091 shellcheck info for sourced files — expected and consistent with all other project scripts.
- **Key decisions:** Report uses argparse with subparsers (consistent with `agentcrew_status.py`). `--batch` flag is a top-level argument (before subcommand) for consistency with status CLI. Cleanup validates terminal state via `_crew_status.yaml` and uses `git worktree remove --force` with `rm -rf` fallback. `list_crews()` reads runner heartbeat data for at-a-glance runner status.
- **Notes for sibling tasks:** `list_crews()` is available in `agentcrew_utils.py` for the TUI dashboard (t386_5). `format_elapsed()` is also shared — useful for any duration display. The report CLI is at `ait crew report <summary|detail|output|list>`. The cleanup CLI is at `ait crew cleanup --crew <id>`. The full AgentCrew CLI help text is now in the `ait help` output. t386_5 (TUI) can import from `agentcrew_utils` and `agentcrew_report` for data. t386_6 should document the report output formats (both interactive and batch).
