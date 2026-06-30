---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t1071_2]
issue_type: enhancement
status: Done
labels: [shadow, claudeskills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
implemented_with: claudecode/opus4_8
created_at: 2026-06-30 09:40
updated_at: 2026-06-30 12:08
completed_at: 2026-06-30 12:08
---

Increase capture depth for shadow plan-review workflows.

Problem: aitask_shadow_capture.sh defaults to SHADOW_CAPTURE_LINES=200. Because tmux -S -N captures N scrollback lines plus the visible pane, this is enough for short prompts but can truncate complex plans. Shadow plan-review capabilities such as plan-explain, plan-challenge, plan-socratic, and plan-assumptions may then analyze only the tail of a plan and miss earlier constraints, decisions, risk notes, or verification requirements.

Requested behavior: keep the normal shadow capture default cheap, but make plan-review flows use a deeper capture by default, e.g. SHADOW_CAPTURE_LINES=400, when refetching the followed pane for plan analysis.

Implementation notes:
- Update the relevant aitask-shadow plan-review sub-procedures to explicitly refetch with a deeper capture before analyzing a visible plan, or introduce an equivalent helper/documented convention for plan-review capture depth.
- Suggested target procedures: .claude/skills/aitask-shadow/plan-explain.md, plan-challenge.md, plan-socratic.md, and plan-assumptions.md.
- Avoid changing the global aitask_shadow_capture.sh default unless exploration shows that is cleaner and low-risk.
- Preserve the advisory-only shadow guardrail; this change only affects how much pane text is read.

Acceptance criteria:
- Plan-review shadow procedures document and use a deeper capture depth, with 400 scrollback lines as the expected default unless a better value is justified.
- Regular non-plan shadow capture remains at the existing default, or any global default change is explicitly justified in the plan.
- Verification demonstrates that the plan-review path can capture more than the old 200-line scrollback window.
- Documentation or comments make clear why plan review uses a deeper capture than ordinary shadow reads.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T08:48:46Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-06-30T09:07:59Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-06-30T09:08:27Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:71967352cc3b90b8

> **✅ gate:risk_evaluated** run=2026-06-30T09:08:27Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1071_3/risk_evaluated_2026-06-30T09:08:27Z-risk_evaluated-a1.log`
