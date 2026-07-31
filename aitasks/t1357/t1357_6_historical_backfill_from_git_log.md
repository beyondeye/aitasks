---
priority: medium
effort: low
depends: [t1357_5]
issue_type: feature
status: Ready
labels: [reporting]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:58
updated_at: 2026-07-31 10:58
---

## Context

Sixth child of t1357. The instrumentation only records runs going forward;
this child seeds drift baselines for past months by mining the task-data
branch git log, which is a free second-resolution step-boundary trail.

Parent plan: `aiplans/p1357_task_workflow_step_stats_and_drift.md`
(child t1357_6 section). Depends on t1357_4 (the loader defines what a
valid event row is).

## Background facts (from exploration)

`./ait git log --format='%ad|%H|%s' --date=iso` on the data branch yields
stable, greppable step-boundary messages with task id and sometimes
agent/model, e.g.:

- `ait: Start work on t<N>: set status to Implementing`  → claim/implement start
- `ait: Add plan for t<N>` / `ait: Update plan for t<N>` → planning/externalize
- `ait: Record <gate> gate for t<N>`                     → gates points
  (gate ledger markers inside archived task files also carry `run=` UTC
  timestamps — richer than commit dates; `lib/gate_ledger.py` parses them)
- `ait: Archive completed t<N> task and plan files`      → archive
- `ait: Update usage count for <agent>/<model> <skill>`  → run end + dims
- `ait: Materialize active gates for t<N>`               → claim-adjacent

`implemented_with: <agent>/<model>` in archived task frontmatter
(`aitasks/archived/`) provides the agent dim per task.

## Deliverables

1. **`.aitask-scripts/aitask_stats_backfill.sh`** (+ optional python helper
   `lib/stats_backfill.py` for the parsing — prefer python for date math):
   - Walk the data-branch log (bounded by `--since <date>`, default: since
     the repo's first `ait: Start work` commit).
   - Group events per task; synthesize coarse event rows in the t1357_1
     schema: `src=backfill`, `effort=unknown`, `run=bf_t<id>`,
     skill=unknown, profile=unknown; agent from the archived task's
     `implemented_with` (or the usage-update commit) when resolvable.
   - Prefer gate-ledger `run=` timestamps (parse archived task files with
     `lib/gate_ledger.py`) over commit dates where both exist.
   - Write into the same monthly layout
     `aitasks/metadata/stats/events/<YYYY-MM>/` as one file per task
     (`t<id>_bf.jsonl`), commit via `./ait git` in a small number of
     batched commits.
   - **Double-backfill guard:** marker file
     `aitasks/metadata/stats/backfill_done.yaml` (records --since range +
     date); re-runs refuse unless `--force`, and `--force` first removes
     previously generated `*_bf.jsonl` files (idempotent regeneration, never
     duplication).
2. Report side needs no change (t1357_4 loader already accepts the schema);
   verify `src=backfill` rows are distinguishable (the drift section may
   optionally annotate baseline months as backfilled).

## Verification

- Bash/python test with a scratch repo containing a synthetic data-branch
  history (a few tasks with start/plan/gate/archive commits + archived task
  files with ledgers): backfill produces expected rows, timestamps prefer
  ledger `run=` over commit date, agent dim resolved from implemented_with.
- Idempotency: second run without `--force` refuses; with `--force` row
  count is unchanged (no duplication).
- `ait stats` drift over a backfilled + live mix renders without error.
