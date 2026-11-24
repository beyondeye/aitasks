---
priority: medium
effort: medium
depends: [1861, 2355]
issue_type: chore
status: Ready
labels: [testmap, testing]
anchor: 1852
created_at: 2026-11-24 19:32
updated_at: 2026-11-24 19:32
---

## Goal

After the M10 rollout, use real test-map runs and reported incidents to decide which parts of the system need improvement. Leave a durable record of the findings and make each resulting task traceable to the evidence and the responsible component.

## Review

- Use the t2355 troubleshooting guide and incident record. Inventory the onboarded target projects, the engine and framework versions, policy modes, and the period and sample available in each project. Draw on available selection predictions and scores, full-run and cost records, readiness and cadence decisions, runner results, and gate outputs.
- Trace missed failures, unexpected full runs or refusals, runner and discovery problems, stale or opaque evidence, and excessive runtime or manual repair. Distinguish project-map corrections from defects or trade-offs in scanners, selection, runners, scoring, policy, or framework integration. Distinguish planned cadence runs from fallback runs.
- For each material finding, record frequency with a denominator where available, impact, a representative task or run, how to reproduce or inspect it, and the owning component and repository. Record any gaps in the evidence. When a component has too little data to assess, record what evidence is needed and how to revisit it.
- Use t2131_12 for the specialized module-widening evaluation. Link its results when available and keep that evaluation under its own task.

## Acceptance

Publish a review linked from the troubleshooting guide, with the evidence window, findings by component, and links to existing or newly filed improvement tasks. File tasks in the repository that owns the finding, with a measurable outcome. Record the evidence behind decisions to leave behavior as it is.
