---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1162
implemented_with: claudecode/opus4_8
created_at: 2026-07-24 14:55
updated_at: 2026-07-26 10:02
completed_at: 2026-07-26 10:02
---

## Origin

Spawned from t1210_3 during Step 8b review.

## Upstream defect

- `aitasks/metadata/models_claudecode.json` (live task-data) — `opus4_8` carries a stats-accumulated `verified["work-report"]: 100` with no `explain` key, so `tests/test_codeagent_work_report.sh` Test 7 (t1162_2 parity rule: work-report mirrors explain, absent where explain absent) exits 1 at HEAD.

## Diagnostic context

t1210_3's verification battery ran `bash tests/test_codeagent_work_report.sh` as a regression check after registering the `trail` codeagent operation. Test 7 failed on the live `models_claudecode.json`. Comparing against the task-data branch HEAD (before any t1210_3 change) proved the violation pre-existed: the verifiedstats accumulator recorded a real work-report run score of 100 for `opus4_8`, a model whose `verified` map has no `explain` key, which the t1162_2 parity rule forbids ("work-report mirrors explain, absent where explain absent"). t1210_3's own `verified["trail"]` additions correctly left `opus4_8` untouched, and the equivalent parity test in `tests/test_codeagent_trail.sh` Test 7 passes — but it inherits the same fragility: any live-accumulated score on a model without `explain` will break it.

## Suggested fix

Decide which side owns the invariant: either relax the parity assertions in `tests/test_codeagent_work_report.sh` / `tests/test_codeagent_trail.sh` to tolerate live verifiedstats-accumulated scores (e.g. only assert parity in the seed files), or make the verified-score accumulator refrain from creating `verified` entries for operations whose parity partner (`explain`) is absent on that model.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-25T21:10:06Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-26T06:58:20Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-26T07:02:16Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:1f787916957b53a1

> **✅ gate:risk_evaluated** run=2026-07-26T07:02:16Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1232/risk_evaluated_2026-07-26T07:02:16Z-risk_evaluated-a1.log`
