---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [gates]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1605
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-26 00:07
updated_at: 2026-08-26 11:11
completed_at: 2026-08-26 11:11
---

## Origin

Upstream-defect follow-up for t1610, recorded at Step 8b. Pre-existing; t1610 did
not introduce it and deliberately did not widen scope to fix it.

## The defect

Two skill files capture the gate orchestrator's exit status with a shape that
does not survive `set -e`:

- `.claude/skills/task-workflow/SKILL.md:806` (Step 9 gate dispatch)
- `.claude/skills/aitask-pickrem/SKILL.md.j2:368` (pickrem's equivalent)

```bash
gates_out="$(./ait gates run <task_id> 2>&1)"; gates_rc=$?
```

Those are **two separate simple commands**. The assignment inherits the command
substitution's exit status; under `set -e` errexit fires there and the shell
exits *before* `gates_rc=$?` ever runs. The branch that exists to diagnose a
nonzero `gates_rc` is therefore unreachable in a strict shell — the session dies
instead of reporting the infrastructure failure.

Verified empirically during t1610 against the identical shape:

```
$ bash -c 'set -euo pipefail; out="$(sh -c "exit 2")"; rc=$?; echo REACHED'
$ echo $?   # 2 — "REACHED" never printed
```

## Why t1610 fixed its own copy but not these

t1610 introduced `aitask_run_project_command.sh`, where exit `1` and `2` are
**ordinary verdicts**, so the same shape would have defeated that task's entire
purpose. Its procedure (`build-verification.md`) therefore documents and pins the
working form, and `tests/test_run_project_command.sh` carries a negative control
proving the rejected shape really does die on a skip.

These two call sites are less harmful — every nonzero status from `ait gates run`
*is* an abort-worthy infrastructure failure the branch would stop on anyway, so
the practical difference is "dies with a bare exit code" rather than "dies with a
diagnosis". That is why it was left alone rather than folded into t1610's diff,
which would have churned the Step 9 goldens for a case that task does not own.

## The fix

Replace both with the form t1610 already documents and tests:

```bash
if gates_out="$(./ait gates run <task_id> 2>&1)"; then
  gates_rc=0
else
  gates_rc=$?
fi
```

errexit is suspended inside an `if` condition, so `$?` in the `else` branch is
the condition's status.

## Scope of the sweep

Do not stop at the two sites named above. Grep the whole skill surface for the
`x="$(...)"; y=$?` shape — other procedures may capture a helper's status the
same way, and the ones where a nonzero status is a *normal* outcome are the
dangerous ones. Classify each hit: an ordinary-outcome capture is a real bug, an
abort-worthy-only capture is cosmetic.

## Acceptance

- Both named call sites use a capture form that survives `set -euo pipefail`,
  demonstrated by a test that runs the rendered snippet in a strict shell and
  asserts it reaches the line after the capture.
- The sweep is done and its result recorded — every remaining `; rc=$?` capture
  in the skill surface is either fixed or explicitly classified as
  abort-worthy-only, with the reason.
- Goldens regenerated in the same commit as any SKILL.md / `.md.j2` edit, and
  `./.aitask-scripts/aitask_skill_verify.sh` plus
  `bash tests/test_skill_render_task_workflow.sh` pass.

## Reference

- t1610 — fixed the same class of defect in `aitask_run_project_command.sh`;
  `.claude/skills/task-workflow/build-verification.md` documents the working
  form, and `tests/test_run_project_command.sh` (`flow(negative control)`) pins
  that the rejected form fails.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-26T08:04:37Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-26T08:04:39Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-26T08:11:39Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:e56bfdb96df480b2

> **✅ gate:risk_evaluated** run=2026-08-26T08:11:39Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1621/risk_evaluated_2026-08-26T08:11:39Z-risk_evaluated-a1.log`
