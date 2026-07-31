---
Task: t1357_6_historical_backfill_from_git_log.md
Parent Task: aitasks/t1357_task_workflow_step_stats_and_drift.md
Sibling Tasks: aitasks/t1357/t1357_1_*.md … t1357_7_*.md
Archived Sibling Plans: aiplans/archived/p1357/p1357_*_*.md
Worktree: aiwork/t1357_6_historical_backfill_from_git_log
Branch: aitask/t1357_6_historical_backfill_from_git_log
Base branch: main
Output branch: main
---

# Plan: t1357_6 — Historical backfill from the data-branch git log

Task file's Background pins the commit-message grammar to parse. Output rows
must satisfy the v1 schema exactly as t1357_4's loader validates it (run the
loader over the output as the acceptance check — independent ground truth).

## Implementation steps

1. **Parser** `lib/stats_backfill.py` (python does the date math + grouping):
   - Input: `./ait git log --format='%ad|%H|%s' --date=iso --reverse`
     (+ `--since` bound).
   - Regexes for the message families in the task file; group by task id;
     emit synthetic events: `src=backfill`, `run=bf_t<id>`,
     `effort=unknown`, `skill=unknown`, `profile=unknown`.
   - Agent dim: from the archived task's `implemented_with` frontmatter
     (`aitasks/archived/**/t<id>_*.md`, including `t<parent>/` subdirs) or
     the nearest usage-update commit message; else `unknown`.
   - Timestamp upgrade: where the archived task file has a `## Gate Runs`
     ledger, parse `run=` stamps via `lib/gate_ledger.py` and prefer them
     over commit dates for the corresponding gate events.
2. **Driver** `aitask_stats_backfill.sh`: arg parsing (`--since`, `--force`,
   `--dry-run` printing row counts per month), invoke the python lib, write
   one `t<id>_bf.jsonl` per task into the proper `<YYYY-MM>/` dir (month of
   the task's first event), batch `./ait git add/commit` (a few commits, not
   one per task).
3. **Guard:** `aitasks/metadata/stats/backfill_done.yaml` (since-range +
   date + row count). Without `--force`, refuse when present. `--force`
   deletes all existing `*_bf.jsonl` first, then regenerates (idempotent
   regeneration — never duplication).
4. **Tests:** scratch repo with synthetic data-branch history (start/plan/
   gate/archive commits + archived task files with ledgers + one
   implemented_with): expected rows; ledger-timestamp preference; agent
   resolution; refuse-then-force idempotency (row count unchanged);
   loader-validates-output check (import `stats_step_data` and load the
   generated dir — zero malformed).
5. `shellcheck` the driver.

## Verification

Per task file. Plus: run `--dry-run` against the real repo and sanity-check
per-month counts before the real run; the real backfill run itself is part
of this task's Step 8 review (show the user the dry-run numbers first).

## Step 9

Standard Step 9.
