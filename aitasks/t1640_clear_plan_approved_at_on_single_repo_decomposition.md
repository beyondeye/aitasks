---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow, task_metadata]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: upstream_defect
created_at: 2026-08-30 17:06
updated_at: 2026-08-30 17:17
---

## Origin

Spawned from t1603_1 during Step 8b review.

## Upstream defect

- `.claude/skills/task-workflow/planning.md:281` — the single-repo decomposition
  cleanup reverts the parent with `--status Ready --assigned-to ""` but omits the
  `--plan-approved-at ""` that its cross-repo twin
  (`cross-repo-child-assignment.md:115`) performs. A task that was
  approved-and-stopped, then re-picked and decomposed into children, keeps a
  `plan_approved_at` marker its single-task plan no longer justifies.

The cross-repo site's own comment says it is mirroring "the single-repo
decomposition cleanup", so the two sites disagree by their own description —
one of them is wrong, and the cross-repo rationale (`:119`, "this task's
single-task plan no longer describes implementable work") argues that the
single-repo site is the one missing the clear.

## Diagnostic context

Found while implementing t1603_1 (board card badge + detail row for
`plan_approved_at`). That task's card badge is suppressed for a parent with
implementing children, and the qualifier deliberately survives suppression, so
the question "can a parent carry a marker *and* have an implementing child?"
had to be answered rather than assumed. It can, via exactly this path:

1. pick a task, plan it, choose "Approve and stop here" → marker set, status
   `Ready`;
2. re-pick it; on the verify path planning re-enters §6.1 and the task is
   assessed as complex → children created;
3. the decomposition cleanup at `planning.md:281` reverts the parent **without**
   clearing the marker;
4. pick a child → the parent now renders `📋 Planned` on the board while its
   plan describes work that was replaced by children.

t1603_1 renders that state deliberately — the board is a read-only mirror, and
showing the marker is what makes the staleness visible — and covers it with
`test_a_parent_with_an_implementing_child_still_surfaces_planned` in
`tests/test_board_plan_approved_marker.py`. Fixing the workflow was explicitly
out of scope there: t1603_1 is a read-only board surface, and this is a
task-workflow change.

## Suggested fix

Add `--plan-approved-at ""` to the `aitask_update.sh` call at
`planning.md:281`, matching `cross-repo-child-assignment.md:115`, and state the
shared rationale at both sites so a future reader does not "fix" one back.

Note the deliberate **non**-clear at `SKILL.md:553` (the risk-mitigation
"before" stop keeps the marker, because the plan is blocked rather than
invalidated) — that site must not be swept up in the same change; it already
carries a comment saying so.

Regenerate the rendered `task-workflow-<profile>-` variants for every profile
after editing the canonical `.claude/skills/task-workflow/planning.md`, and
consider a test pinning that decomposition clears the marker while the
"before" stop retains it — both directions, since a one-directional test passes
on a version that clears it everywhere.
