---
Task: t1357_1_event_schema_stamp_spool_helper.md
Parent Task: aitasks/t1357_task_workflow_step_stats_and_drift.md
Sibling Tasks: aitasks/t1357/t1357_2_*.md … t1357_7_*.md
Archived Sibling Plans: aiplans/archived/p1357/p1357_*_*.md
Worktree: aiwork/t1357_1_event_schema_stamp_spool_helper
Branch: aitask/t1357_1_event_schema_stamp_spool_helper
Base branch: main
Output branch: main
---

# Plan: t1357_1 — Event schema, stamp/spool helper, capture verb, tests

The task file carries the full deliverable spec (schema, verbs, layouts) —
it is the PINNED contract. Parent plan
`aiplans/p1357_task_workflow_step_stats_and_drift.md` § Architecture is the
authority on the schema; do not diverge without updating both.

## Implementation steps

1. **Read first:** `aidocs/framework/shell_conventions.md`,
   `aidocs/framework/aitasks_extension_points.md` (new helper script + setup
   edit + new frontmatter-adjacent state), `.aitask-scripts/aitask_gate_record.sh`
   (best-effort commit pattern), `.aitask-scripts/aitask_lock.sh` ~204–213
   (pid + pid_starttime liveness).
2. **`lib/stats_step_lib.sh`**: constants (step vocabulary, schema version),
   `stats_root()` (repo-root `.aitask-stats`), `stats_events_dir()` (data-branch
   `aitasks/metadata/stats/events`), `emit_event_json()` (build one JSON line
   with python3 fallback to printf-escaping — prefer
   `python3 -c 'import json,...'` for correct escaping; sanitize delimiters at
   the write site), manifest read/write (flat YAML: key: value lines only),
   `mint_run_id()`, `pid_starttime()` (read `/proc/<pid>/stat` field 22;
   platform-guard for macOS via `ps -o lstart=`).
3. **`aitask_stats_step.sh`**: dispatcher over verbs per the task spec. The
   fail-safe shape: `main()` runs inside `( set -euo pipefail; ... )` subshell;
   top level catches nonzero, prints `STATS_ERROR:<reason>` to stdout, warns
   stderr, `exit 0`. Structured single-line stdout per verb
   (`STAMPED:` / `CAPTURED:<path>` / `NOOP:<reason>` / `STATS_ERROR:<reason>`).
4. **capture**: read manifest → stamp `run/end` → rewrite spool lines merging
   dims (python3 one-pass) → move to
   `aitasks/metadata/stats/events/<YYYY-MM>/t<id>_<run_id>.jsonl` (month from
   run start) → `./ait git add <path> && ./ait git commit -m "ait: Record step
   stats for t<id>"` best-effort → rm spool dir. `--sweep-orphans`: for each
   `runs/t*/manifest.yaml` whose pid is dead (starttime mismatch or gone),
   capture with `--outcome orphaned`.
5. **Ignore entries**: `.gitignore` + `aitask_setup.sh` gitignore-population
   block (pattern: the `.aitask-gates` entry).
6. **`ait` dispatcher**: add `stats-step` case → exec the helper.
7. **Tests** `tests/test_stats_step.sh`: per the task's Verification section;
   scratch repo fixture with a minimal `.aitask-data`-style layout; negative
   control = unwritable spool dir → exit 0 + `STATS_ERROR:`; prove the
   harness can fail (temporarily break the trap in a subtest copy).
8. `shellcheck` both new scripts.

## Verification

- `bash tests/test_stats_step.sh` → PASS summary.
- `shellcheck .aitask-scripts/aitask_stats_step.sh .aitask-scripts/lib/stats_step_lib.sh`
- Manual: `./ait stats-step begin-run 9999 --skill test && ./ait stats-step
  stamp 9999 implement begin && ./ait stats-step capture 9999 --outcome done`
  → one committed events file; then revert the test commit.

## Step 9

Standard task-workflow Step 9 (commit via Step 8, merge/archive). Parent
archives only after all siblings complete.
