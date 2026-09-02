---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: documentation
status: Done
labels: [task-workflow, verification]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1538
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-09-01 18:08
updated_at: 2026-09-02 12:32
completed_at: 2026-09-02 12:32
---

## Origin

Risk-mitigation ("before") for t1663_1, created at Step 7 from the approved plan's risk evaluation.

## Risk addressed

goal-achievement — Tier B structurally near-unreachable in v1.

Verbatim from `aiplans/p1663/p1663_1_premise_core_engine_and_producer.md` `## Risk`:

> **Tier B is structurally near-unreachable in v1.** Measured on this corpus
> just now: 107 of the 108 active tasks carrying `verifies:` are
> `issue_type: manual_verification`, and task-workflow Step 3 Check 3 routes
> those away *before* the premise check runs. `exact` quality requires
> `verifies:` — `followup_origin.py`'s rule 1 makes `anchor` "never an exact
> origin" by contract, and `--followup-of` writes only `anchor:`. So the
> derived-scope half ships correct but dormant, and t1663_3's `--followup-of`
> seeding trigger would stamp baselines that can never resolve a scope ·
> severity: high

## Goal

The t1561 decision record (`aidocs/framework/task_premise_staleness.md`) builds its
organic-coverage story on two claims that do not hold together:

- **Tier B scope** resolves an origin via `lib/followup_origin.py` at **`exact`
  quality only** ("`topic` and `unknown` refuse to claim causation").
- **Seeding** stamps `premise_baseline` at creation "when the new task has a
  derivable scope — `--followup-of` (Tier B will resolve an origin) or
  `--file-ref` (Tier A)".

But `--followup-of` does not produce an `exact` origin. `aitask_create.sh`'s
`resolve_anchor()` turns it into an `anchor:` field, and `followup_origin.py`'s
load-bearing rule 1 states `anchor` is **never** an exact origin ("Reporting it
as `exact` would claim direct causation the data does not support"). `exact`
comes only from `verifies:`, which on this corpus is carried by 107 of 108
tasks that are `issue_type: manual_verification` — and Step 3 Check 3 routes
manual-verification tasks away before the premise check would ever run.

Net effect if left uncorrected: every task t1663_3 seeds on the `--followup-of`
trigger carries a `premise_baseline` whose scope can never resolve, so the check
reads a silent `SKIP` forever. That is dead weight of exactly the kind the record
says it wants to avoid ("A task with no derivable scope is not seeded; the field
would be dead weight"), and it defeats the tree's only coverage-growth path.

This task must:

1. **Correct the record.** Amend `aidocs/framework/task_premise_staleness.md` —
   the "Scope and baseline are orthogonal axes" and "Seeding" sections, and the
   baseline-lifecycle table row for `--followup-of` — so the stated seeding
   trigger matches what Tier B can actually resolve. Record the measurement
   (107/108, and the `anchor`-is-never-exact contract) as the evidence.
2. **Decide the seeding rule** and write it into the record: either
   (a) narrow the seeding trigger to `--file-ref` / `verifies:` only, or
   (b) widen Tier B to accept an `anchor`-derived origin — which the record and
   `followup_origin.py` currently forbid, so choosing it requires overturning
   rule 1 explicitly rather than by omission, or
   (c) something else the record argues for. Do not leave both halves as written.
3. **Fix `t1663_3`'s task file** (`aitasks/t1663/t1663_3_creation_time_seeding_and_carryover.md`)
   so its "Key files" and "Verification" sections state the corrected criterion
   instead of "Creation with `--followup-of` → seeded".
4. **Wire the enforcing dependency:** add this task to `t1663_3`'s `depends:`
   so it cannot be picked against the uncorrected criterion.
5. **Notify `t1663_6`** (the retrospective child, which owns the deferred
   dispositions) that Tier-B reachability is now a measured input to its
   evaluation.

## Verification

- The record no longer claims `--followup-of` yields a Tier-B-resolvable scope,
  and states the chosen seeding rule with its rationale.
- `t1663_3`'s description and its Verification bullets match the chosen rule.
- **Dependency wired** (`resolve` takes parent ids only and rejects `1663_3`;
  `child-file` is the child lookup, and the id must be asserted in the file it
  returns rather than inferred from the lookup succeeding):
  ```bash
  f=$(./.aitask-scripts/aitask_query_files.sh child-file 1663 3 | sed 's/^CHILD_FILE://')
  command grep -n '^depends:' "$f"           # must list BOTH t1663_2 and 1673
  ./ait ls -v --children 1663 99             # t1663_3 shows "Blocked (by t1663_2,1673)"
  ```
  The second command is the real assertion: `--deps` replaces the whole list, so
  the check must prove `t1663_2` survived, not merely that `1673` arrived.
- A grep for `--followup-of` across `aidocs/framework/task_premise_staleness.md`
  and the t1663 tree returns no remaining claim that it produces an `exact` origin.
- **The `--verifies` contract surfaces carry the new wording and not the old.**
  A substring search for "manual-verification tasks" cannot show this — the
  corrected text contains that phrase too ("usually manual-verification tasks,
  but any issue_type may carry a verifies list"), so it passes on both correct
  and incorrect content. Assert the two arms separately, per surface: the exact
  old **exclusive** phrase absent, and the new **non-exclusive** phrase present.
  | file | old phrase (must be ABSENT) | new phrase (must be PRESENT) |
  |---|---|---|
  | `.aitask-scripts/aitask_create.sh` | `(for issue_type: manual_verification)` | `but not restricted to one` |
  | `.aitask-scripts/aitask_update.sh` | `Verifies options (batch mode, for manual-verification tasks):` | `issue_type may carry a verifies list` |
  | `website/content/docs/commands/task-management.md` | ``this task verifies (for `manual_verification` tasks)`` | `but any issue type may carry it` |

  Use `grep -qF` (fixed-string) on each. Negative control: run the same two arms
  against `git show <pre-edit-rev>:<file>` — every surface must fail **both**
  arms, which is what proves the check is not vacuous.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-02T07:02:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-02T09:31:21Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-02T09:32:37Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:b5c6384aa2914b8c

> **✅ gate:risk_evaluated** run=2026-09-02T09:32:37Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1673/risk_evaluated_2026-09-02T09:32:37Z-risk_evaluated-a1.log`
