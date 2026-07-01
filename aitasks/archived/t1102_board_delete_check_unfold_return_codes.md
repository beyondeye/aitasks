---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [task_attachments]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1096
implemented_with: codex/gpt5_5
created_at: 2026-07-01 11:51
updated_at: 2026-07-01 22:08
completed_at: 2026-07-01 22:08
boardidx: 30
---

## Origin

Spawned from t1096 (Rebind folded-origin attachment refs to revived tasks on hard-delete
unfold) during Step 8b review.

## Upstream defect

`.aitask-scripts/board/aitask_board.py:6589-6594` — the `_do_delete` unfold loop runs
`aitask_update.sh --batch <fid> --status Ready --folded-into ""` per revived folded task but
**ignores the subprocess return code** (`capture_output=True` with no `returncode` check). A
failed unfold would leave a folded task un-revived (still `status: Folded`, `folded_into`
pointing at the now-deleted primary) with **no signal to the user**, while the delete proceeds
to `git rm` the primary and commit.

## Diagnostic context

Surfaced while implementing t1096 (rebind-on-unfold): the board's `_do_delete` decrefs/rebinds
attachments first (fail-closed on error), then unfolds folded tasks, then `git rm`s the primary
in a single commit. The **attachment side** is now fail-closed, but the **unfold side** is not —
inconsistent robustness in the same delete path.

Note: this is **not** an attachment data-loss risk after t1096 — the rebind gives the revived
task the ledger ref, so the blob is retained via that non-empty ref even if the task is
erroneously left `Folded` (gc's zero-refcount check does not depend on the task's non-`Folded`
frontmatter cross-check for a still-referenced blob). It is a task-state-integrity bug: a task
silently stuck `Folded` with a dangling `folded_into`.

## Suggested fix

Check each unfold subprocess `returncode`; on any non-zero, surface a `notify(..., severity=
"error")` and treat the delete as failed (mirror the attachment fail-closed early `return`
before `git rm`), OR collect and report the failed ids. Add a board/unit test for the failed-
unfold path.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T13:43:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-01T18:55:11Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-01T19:08:07Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:a12a83f4ea8019d1

> **✅ gate:risk_evaluated** run=2026-07-01T19:08:07Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1102/risk_evaluated_2026-07-01T19:08:07Z-risk_evaluated-a1.log`
