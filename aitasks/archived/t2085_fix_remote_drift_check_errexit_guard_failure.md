---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-20 18:40
updated_at: 2026-10-21 08:44
completed_at: 2026-10-21 08:44
---

## Origin

Spawned from t1859_1 during Step 8b review.

## Upstream defect

- `.claude/skills/task-workflow/remote-drift-check.md:27` — `tests/test_skill_errexit_capture.sh`'s errexit-unsafe `$?` guard fails on the `./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"; echo "DRIFT_RC:$?"` capture that t2061 (`c643a8390`) added. It was already failing at HEAD; it is unrelated to t1859_1.

## Diagnostic context

While verifying t1859_1 (2026-10-20, main @ `e2116c90a`), `bash tests/test_skill_errexit_capture.sh` reported `Results: 65/66 passed, 1 failed`:

```
FAIL: guard: no errexit-unsafe $? read in any authoring skill file (expected '', got '.claude/skills/task-workflow/remote-drift-check.md:27: ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"; echo "DRIFT_RC:$?"
```

t1859_1 did not touch `remote-drift-check.md` or the guard test. The last commit to touch the procedure is t2061 `c643a8390`, which introduced the `DRIFT_RC:` capture line.

## Suggested fix

Two options:

- Rewrite the documented capture into the errexit-safe `if …; then rc=0; else rc=$?; fi` form the guard enforces (the same form `build-verification.md` uses), keeping the `DRIFT_RC:<rc>` contract the procedure parses.
- Or, if `; echo "DRIFT_RC:$?"` is deliberately safe here (the agent runs it as a non-errexit one-liner), add a narrowly scoped, justified allowlist entry to the guard. Do not weaken the guard globally.

Re-render the task-workflow goldens and prerenders after the edit.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T16:09:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T16:23:57Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-21T05:44:01Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:976e3dfc48e34b64

> **✅ gate:risk_evaluated** run=2026-10-21T05:44:01Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2085/risk_evaluated_2026-10-21T05:44:01Z-risk_evaluated-a1.log`
