---
priority: medium
effort: low
depends: [t1663_2]
issue_type: feature
status: Ready
labels: [task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:19
updated_at: 2026-09-01 15:19
---

Seed `premise_baseline` at task creation when scope is derivable, and make carry-over tasks inherit their origin's baseline.

## Context

Third child of t1663. Design in `aidocs/framework/task_premise_staleness.md` ("Seeding"). With the v1 no-go on computed baselines (see the record's measured pre-phase), creation-time seeding is the ONLY organic coverage growth path — every new follow-up or file-ref-carrying task must leave creation checkable, or the mechanism is dead on arrival (the t1555 0/77 lesson).

## Key files

- `.aitask-scripts/aitask_create.sh` — after a successful `--batch --commit` creation, when the invocation carried `--followup-of` (Tier B scope will resolve) or ≥1 `--file-ref` (Tier A scope), stamp `premise_baseline` = current HEAD sha + timestamp into the new task file (same-commit, via the create serializer — mind that `create_task_file` is a second write path mirroring `write_task_file`). A task with neither flag is NOT seeded (the field would be dead weight; silent SKIP is the designed legacy behavior).
- `.aitask-scripts/aitask_archive.sh` — `create_carryover_task`: the carried-over task INHERITS the origin task's `premise_baseline` verbatim (never re-stamps to HEAD — the carried premise is as old as its source; same rule as t1555's carryover inheritance).

## Reference files for patterns

- `aidocs/framework/manual_verification_staleness.md` "Seeding — Step 8c only" + the carryover row of its baseline lifecycle table.
- `tests/test_verification_stale.sh::test_carryover_inherits_baseline` — the test shape for inheritance.

## Verification (this child owns these cases; pinned outcomes)

- Creation with `--followup-of` → seeded, value = HEAD-at-creation (sha matches `git rev-parse HEAD` in the fixture repo).
- Creation with `--file-ref` → seeded. Creation with neither → field absent.
- Carryover from a task carrying a baseline → identical value in the new task (not re-stamped); carryover from a task without one → field absent.
- Seeding must not break `--parent` child creation or draft mode (`aitasks/new/` path is not seeded — no commit exists to anchor to yet; seeding happens only on the committed path).
