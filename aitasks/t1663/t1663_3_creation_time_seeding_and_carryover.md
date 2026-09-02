---
priority: medium
effort: low
depends: [t1663_2, 1673]
issue_type: feature
status: Ready
labels: [task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:19
updated_at: 2026-09-02 10:05
---

Seed `premise_baseline` at task creation when scope is derivable, and make carry-over tasks inherit their origin's baseline.

## Context

Third child of t1663. Design in `aidocs/framework/task_premise_staleness.md` ("Seeding" + "Tier B reachability"). With the v1 no-go on computed baselines (see the record's measured pre-phase), creation-time seeding is the ONLY organic coverage growth path — every new task that leaves creation with a derivable scope must leave it checkable, or the mechanism is dead on arrival (the t1555 0/77 lesson).

**The seeding trigger was corrected by t1673 — do not implement the older criterion.** The record originally named `--followup-of` as a trigger; it cannot be one. `resolve_anchor()` turns `--followup-of` into an `anchor:` field and writes nothing else, and `followup_origin.py`'s rule 1 holds that `anchor` is *never* an `exact` origin, which is what Tier B requires. A baseline stamped on `--followup-of` could never resolve a scope and would read a silent `SKIP` forever.

## Key files

- `.aitask-scripts/aitask_create.sh` — after a successful `--batch --commit` creation, when the invocation carried ≥1 `--file-ref` (Tier A scope) **or** `--verifies` (Tier B — the only input that yields an `exact` origin), stamp `premise_baseline` = current HEAD sha + timestamp into the new task file (same-commit, via the create serializer — mind that `create_task_file` is a second write path mirroring `write_task_file`). **`--followup-of` alone is NOT a trigger** (see Context for why). A task with none of these is NOT seeded (the field would be dead weight; silent SKIP is the designed legacy behavior).
- `.aitask-scripts/aitask_archive.sh` — `create_carryover_task`: the carried-over task INHERITS the origin task's `premise_baseline` verbatim (never re-stamps to HEAD — the carried premise is as old as its source; same rule as t1555's carryover inheritance).

## Reference files for patterns

- `aidocs/framework/manual_verification_staleness.md` "Seeding — Step 8c only" + the carryover row of its baseline lifecycle table.
- `tests/test_verification_stale.sh::test_carryover_inherits_baseline` — the test shape for inheritance.

## Verification (this child owns these cases; pinned outcomes)

- Creation with `--file-ref` → seeded, value = HEAD-at-creation (sha matches `git rev-parse HEAD` in the fixture repo).
- Creation with `--verifies` → seeded.
- **Creation with `--verifies`, a non-`manual_verification` `--type`, and no follow-up relation (no `--followup-of`, no `--followup-kind`) → seeded.** This is the contract fixture and it is not optional: it pins both halves of the corrected Tier-B contract at once — that `--verifies` is type-agnostic (`aitask_create.sh` parses and serializes it without consulting `issue_type`), and that Tier-B eligibility is *having an exact origin*, not *being a follow-up* (`followup_origin.py` deliberately never reads `followup_kind`). It is the shape of the live task `t583_9` (`issue_type: test`, eight-entry `verifies:`, no `anchor`/`followup_kind`), so it exercises a case the corpus already contains. It must fail if anyone type-gates `--verifies` or re-adds a follow-up gate to Tier B.
- **Creation with `--followup-of` alone → field absent.** Negative control: the trigger the record used to name must now provably NOT fire.
- Creation with none of `--file-ref` / `--verifies` / `--followup-of` → field absent.
- Carryover from a task carrying a baseline → identical value in the new task (not re-stamped); carryover from a task without one → field absent.
- Seeding must not break `--parent` child creation or draft mode (`aitasks/new/` path is not seeded — no commit exists to anchor to yet; seeding happens only on the committed path).
