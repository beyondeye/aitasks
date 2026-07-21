---
priority: medium
effort: medium
depends: [1200]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1200]
created_at: 2026-07-21 12:24
updated_at: 2026-07-21 12:24
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1200

## Verification Checklist

- [ ] [t1200] Run a Default-tier shadow implementation review from minimonitor against a task whose plan has an explicitly ACCEPTED risk. Confirm the accepted risk appears as an `informational` finding with the plan's acceptance rationale named, instead of vanishing from the output entirely (the reported t1200 symptom).
- [ ] [t1200] Ask the shadow for an unqualified "adversarial review". Confirm it announces the inferred tier before starting, e.g. "Running Default (the legacy three-axis review) — Advanced is the recommended tier; say 'advanced review' for it." A user must never have to infer the tier from the output.
- [ ] [t1200] Confirm a Default-tier review now surfaces candidates it is unsure about (the anti-drop rule) rather than returning few or no concerns. Compare against pre-t1200 behavior on a comparable diff — this is the core "I very rarely get concerns" symptom and can only be judged on live output.
- [ ] [t1200] Confirm the emitted concern block still parses in minimonitor's picker: the auto-offer fires, items appear in blocking -> follow-up -> informational order, and forwarding an informational item to the followed agent preserves its "Disposition: informational." trailer verbatim.
- [ ] [t1200] Confirm the no-silent-omission disclosure actually fires: run an Advanced or Deep review on a diff large enough to hit the findings cap and check for an explicit trailing line such as "cap: 3 follow-up and 2 informational findings omitted".
- [ ] [t1200] Confirm an `informational` concern region stays short (<= ~30 chars, e.g. `accepted risk` or `basename.ext:LINE`) in real output, so the `[priority | region]` marker never wraps and stays parseable.
