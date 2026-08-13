---
priority: medium
effort: medium
depends: [1429]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1429]
followup_kind: manual_verification
created_at: 2026-08-05 18:07
updated_at: 2026-08-13 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1429

## Verification Checklist

- [ ] Run `/aitask-trail --refresh art:trail-shadow-review-loop` end-to-end and confirm the Step 3.3 belt-and-braces sweep is actually executed: the outgoing risk_mitigation_tasks read on each landed member AND the incoming verifies prefilter, with candidates reaching the propose-and-confirm path. This is prose an agent must follow; no automated test covers it.
- [ ] In the board's By-Trail view, open a trail whose drift includes a `risk-mitigation follow-up of ...` reason and confirm the stale badge and the drift detail modal render the new reason text legibly, including at narrow terminal widths.
- [ ] Run the verifies sweep command verbatim from the rendered skill against a real member id and confirm the documented behaviour: candidate printed on match, exit 0 when no member matches, nonzero when a listed file is unreadable.
- [ ] Confirm `art:trail-gates-framework-landing` still refreshes normally with no new-edge reasons, so the change is inert for trails that have no Step 8d follow-ups.
