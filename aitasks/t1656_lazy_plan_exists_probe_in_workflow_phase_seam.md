---
priority: low
effort: low
depends: []
issue_type: performance
status: Implementing
labels: [board, gates, performance]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: review_finding
created_at: 2026-08-31 22:39
updated_at: 2026-08-31 23:14
---

## Context

Confirmed at t1603_3's Step-8 review and deliberately deferred there. t1603_2's
`derive_workflow_phase` takes `plan_exists: bool` as an eagerly-evaluated
keyword, but reads it on **exactly one** branch — the no-ledger degradation
(`"derived" if plan_exists else "unknown"`). The deferred-plan-marker branch,
the `result.error` branch and the whole ledger ladder all return without
touching it.

So `_inflight_item_for` (`aitask_board.py:2299`, the call site carries a
pointer comment) pays one `Path.exists()` per admitted in-flight item, per
board refresh, and throws it away in every state except the no-ledger one. The
cost is bounded by the in-flight set rather than the whole board — the status
pre-filter rejects `Ready`-without-marker before any of this — so it is small
but avoidable, and it works against the cheap-pre-filter goal t1603_3 adopted
for exactly this path.

## Why it was not fixed in t1603_3

The obvious caller-side fix is the wrong one. Computing it conditionally —
`if not result.error and (not result.has_ledger or result.state is None)` —
restates `derive_workflow_phase`'s own branch conditions in its caller. That is
a second authority over precisely the derivation t1603_3 centralised, and it
drifts the moment the ladder's ordering changes: the caller keeps probing (or
stops probing) for a branch that no longer fires.

## The change

Move the laziness into the seam, following the pattern already in this file.
`TaskManager.gate_state_for` passes `self.code_digest_for_refresh` — the bound
method, not its value — precisely so a ~5 ms subprocess is never paid by a
board with no signed witnesses. Do the same here:

- `derive_workflow_phase(..., *, plan_exists)` accepts a **callable** returning
  `bool` (or a `bool`, if a compatible union is cheaper for the other call
  sites), and resolves it **only** inside the B1 no-ledger branch.
- `_inflight_item_for` passes a zero-arg callable closing over the task, e.g.
  `lambda: _resolve_plan_path_for_task(task, self) is not None`.
- Update every other call site (`tests/test_board_workflow_phase.py`'s
  `WorkflowPhaseTestBase._derive`, and any t1603_4 consumer that has landed by
  then) in the same commit.

## Key files

- `.aitask-scripts/board/aitask_board.py` — `derive_workflow_phase` (the
  `plan_exists` parameter and the B1 branch), and the call site at
  `_inflight_item_for` whose comment names this task.
- `tests/test_board_workflow_phase.py` — `WorkflowPhaseTestBase._derive` threads
  `plan_exists`; the seam-level tests below belong here.

## Verification

- **The probe is not called on any branch that does not read it.** Pass a
  callable that records its invocations (or raises) and assert it is never
  invoked for: a `Ready`-plus-marker task, an unreadable-ledger (`error`) task,
  and every rung of the ledger ladder. A counting spy, not a mock whose
  `assert_not_called` could pass because the argument shape changed silently.
- **Positive control:** the no-ledger branch DOES invoke it, exactly once, and
  still answers `derived` vs `unknown` correctly on both outcomes. Without this
  the assertions above pass against a seam that ignores the parameter entirely.
- The phase answers are unchanged across the existing
  `tests/test_board_workflow_phase.py` matrix — this is a laziness change, not
  a semantics change.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last line.
