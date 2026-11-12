---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, shadow, workflow_phase]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1573
followup_kind: upstream_defect
created_at: 2026-11-12 11:22
updated_at: 2026-11-12 15:41
---

## Origin

Spawned from t2283 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/workflow_phase.py` — `compose`'s ledger half reports
  `IMPLEMENT` for the whole of a **re-plan after an approved plan**. As a result,
  the followed agent's card/phase line in the monitor and minimonitor is wrong
  while the agent re-plans, and so is the advisory phase stamped onto the shadow
  (`MiniMonitorApp._restamp_shadow_phase` → `@aitask_shadow_phase`).

## Diagnostic context

From t2283, observed live on 2026-11-11 in thinking_app, window
`agent-pick-587_5`:

1. The agent is in Claude's plan-approval dialog. `compose` takes the live tier
   (`claude_plan_approval` → PLAN).
2. The user sends shadow feedback and the agent starts working. With
   `awaiting_input is not True`, `compose` suppresses the screen tiers and falls
   back to the ledger half (`GateSummaryCache.phase_for` →
   `phase_from_ledger_text`). The task's `## Gate Runs` still holds the earlier
   round's `gate:plan_approved status=pass`, so the result is
   `('IMPLEMENT', 'ledger checkpoints resolve to IMPLEMENT')`.
3. The phase stays IMPLEMENT for the entire re-plan, until the revised plan's
   dialog brings PLAN back.

t2283 fixed only the **stale banner** consumer. `_feedback_phase_retired` now
retires on a ledger-sourced phase only when the gate-run content has changed
since the feedback was bound (`GateSummaryCache.ledger_identity_for`). The
other consumers of the same signal still show IMPLEMENT during a re-plan: the
card/phase line and the shadow phase stamp.

## Suggested fix

Give the ledger half a way to recognise a re-plan in progress. Two candidates:
- treat a `plan_approved` pass followed by evidence of re-planning (for example
  a re-opened plan or a new plan-mode session) as PLAN;
- render the ledger-derived phase as "IMPLEMENT (ledger, unconfirmed)" when the
  pane is running and no live tier has confirmed it.

The phase is advisory, so any change must keep the anti-gating rule in
`aidocs/framework/shadow_agent.md` ("Phase detection (advisory)").
