---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_workflow, skills]
gates: [risk_evaluated]
anchor: 1913
followup_kind: upstream_defect
created_at: 2026-10-08 23:18
updated_at: 2026-10-08 23:18
---

## Origin
Spawned from t1913 during Step 8b review.

## Upstream defect
- `.claude/skills/aitask-pickrem/SKILL.md.j2:320` — any Step 8 ownership-guard
  failure triggers the **Abort Procedure**: `LOCK_FAILED`, `LOCK_LIVE_HOLDER`,
  `LOCK_UNVERIFIABLE_HOLDER`, `LOCK_ERROR`, `LOCK_INFRA_MISSING` or a script
  error. The Abort Procedure then runs:
  - `aitask_lock.sh --unlock <task_num>`;
  - a status revert with `--assigned-to ""`;
  - a commit.

  It does this even when another live session on this machine holds the task,
  so an unattended pickrem run can release a different session's lock and revert
  its task.

## Diagnostic context
t1913 wired workflow-end banners into every pickrem ending. Step 5's pre-claim
refusals were deliberately given `unchanged` banners **without** the Abort
Procedure, because that procedure "applies after the task was claimed" and must
not touch another session's task (the plan-review requirement). The Step 8
ownership guard (`aitask_pick_own.sh` re-run before implementation) still sends
every failure, including the live/unverifiable-holder refusals, through the
Abort Procedure, which mutates lock and status state it does not own.

## Suggested fix
Split the Step 8 guard's failure handling:
- a refusal where another session holds the task (`LOCK_LIVE_HOLDER`,
  `LOCK_UNVERIFIABLE_HOLDER`, `LOCK_FAILED` by another owner) ends **without** the
  Abort Procedure, and its Stopped banner's outcome is derived from the task's
  read-only state, mirroring `task-workflow/SKILL.md` Step 7's guard;
- only failures where this run still owns the claim go through Abort.

Afterwards, re-run `tests/test_workflow_end_banner_contract.sh` and regenerate
the pickrem goldens and remote prerenders.
