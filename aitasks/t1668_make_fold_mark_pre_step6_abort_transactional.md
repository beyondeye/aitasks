---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, robustness, task_metadata]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1661
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-01 15:38
updated_at: 2026-09-01 17:58
---

## Origin

Spawned from t1661 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_fold_mark.sh:~390` — an abort between Steps 3 and 5b
  leaves the fold's mutations on disk, dirty and uncommitted, with **no
  rollback**. `_fold_rollback` exists, but `rollback_paths` is not assembled
  until after Step 5b, so nothing before that point has a path set to restore.

Reproduced during t1661:

```bash
# fixture with t10 present, t9999 absent
aitask_fold_mark.sh --commit-mode fresh 10 9999
# -> exit 1, stderr "No task file found for task number 9999"
# -> aitasks/t10_primary.md now carries folded_tasks: [9999], dirty, uncommitted
```

Step 3 writes the primary's `folded_tasks`, then Step 4's `aitask_update.sh` for
the missing id exits non-zero and `set -e` kills the script. The primary is left
mutated. Any id that fails to resolve — a typo, a task archived between
validation and marking — reaches this.

Two consequences:
1. The dirty task file is exactly what the next unscoped commit sweeps up — the
   failure class t1599_2 exists to prevent.
2. Under t1661's output contract the run emits **no records**, so stdout gives a
   consumer no signal that anything landed. That contract is deliberately scoped
   to Step 6 and documents the gap ("WHAT THIS DOES NOT BUY" in the script
   header and in `task-fold-marking.md`), naming the exit status as
   authoritative — but documenting a gap is not closing it.

## Diagnostic context

Surfaced while implementing t1661 (buffer the structured stdout records until
the Step 6 commit succeeds). Two Step 8 review rounds converged on scoping that
task's guarantee to Step 6 rather than broadening the output protocol, which
left this transactionality gap explicitly out of scope and documented.

The gap is **pre-existing** — before t1661 the same abort left the same files
dirty; it merely also printed the records first.

`tests/test_fold_mark.sh::test_abort_mid_mutation_emits_no_records` pins the
current behavior, including the residual (`folded_tasks: [9999]` on disk,
worktree status ` M`). That test must be updated when this task lands.

## Suggested fix

Assemble the rollback path set **before** Step 3 rather than after Step 5b, and
roll back on any abort (an `ERR`/`EXIT` trap, or explicit guards on the Step 4/5
updates). Note the constraints:

- `rollback_paths` is also the input to `task_git_commit_scoped` and to
  `_fold_amend_guard`'s `own_paths`, so hoisting it must not change what those
  two see at Step 6 (t1599_2's design).
- Attachment-meta paths (`fold_meta_relpaths`) are only discovered in Step 5b
  and would need appending as they are found.
- The primary + folded + transitive task files are all resolvable before Step 3,
  so the bulk of the set can be built early.

Consider also validating `--commit-mode` at argument-parse time; t1661 added a
`_fold_rollback` to that arm, but validating up front avoids mutating at all.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T14:58:01Z status=pass attempt=1 type=human
