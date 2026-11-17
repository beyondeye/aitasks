---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [setup, tests]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-16 22:26
updated_at: 2026-11-17 13:07
completed_at: 2026-11-17 13:07
---

## Origin

Spawned from t1912_5 during Step 8b review. It was found while baselining every
setup/install test before t1912_5 added its setup hook, so it was failing
before any t1912_5 change.

## Upstream defect

- `tests/test_setup_pip_install_guards.sh — C4 assertion "the mutation no-ops exactly the four post-repair re-checks" fails at HEAD before this change (expected 4, got 5; 107/108)`

## Diagnostic context

`bash tests/test_setup_pip_install_guards.sh`, run on main at 4766ca43a
(2026-11-16, before t1912_5 touched `aitask_setup.sh`), printed:

```
=== C. Negative controls (mutations of the real source) ===
FAIL: C4: the mutation no-ops exactly the four post-repair re-checks (expected '4', got '5')
Tests: 108  Pass: 107  Fail: 1  Skipped: 0
```

The result was identical after t1912_5's setup changes, so t1912_5 did not
cause it.

The C4 negative control counts the post-repair re-check sites its mutation
neutralises in `aitask_setup.sh`, and now finds 5 where the test pins 4.

## Suggested fix

Either `aitask_setup.sh` gained a fifth post-repair re-check that the test's
pinned count was never updated for, or the mutation's pattern now matches an
unrelated line. Find which commit added the fifth match (`git log -S` on the
mutated pattern), then update the pin or tighten the mutation.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-17T09:38:26Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-17T11:05:54Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-17T11:07:01Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:749f551ee227dda5

> **✅ gate:risk_evaluated** run=2026-11-17T11:07:01Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2321/risk_evaluated_2026-11-17T11:07:01Z-risk_evaluated-a1.log`
