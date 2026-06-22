---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t1018_1]
issue_type: bug
status: Implementing
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
anchor: 1018
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 13:54
updated_at: 2026-06-22 17:20
---

## Failed verification item from t1018_1

> [t1018_1] No retry-apply binding leaks into the footer on tabs/screens where it is irrelevant; each shows only on its owning surface.

### Source

- **Manual-verification task:** `aitasks/t1018/t1018_4_manual_verification_brainstorm_op_restart_dblclick_footer.md` (item #2)
- **Origin feature task:** t1018_1
- **Origin archived plan:** `aiplans/archived/p1018/p1018_1_footer_binding_hygiene_deliverable_keys.md`

### Commits that introduced the failing behavior

- 7a0ea5044 refactor: Scope brainstorm retry-apply actions + deliverable preview keys (t1018_1)

### Files touched by those commits

- .aitask-scripts/brainstorm/brainstorm_app.py
- tests/test_brainstorm_binding_scope.py
- tests/test_brainstorm_proposal_preview.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1018_4 item #2.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-22T14:20:16Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-22T14:20:18Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-22T14:24:35Z status=pass attempt=1 type=human
