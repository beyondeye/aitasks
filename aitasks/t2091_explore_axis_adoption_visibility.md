---
priority: medium
effort: medium
depends: [1853_4]
issue_type: chore
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 10:07
updated_at: 2026-10-21 10:07
---

## Goal

After t1853_4 lands, explore how to expose incomplete axis adoption without disrupting existing runners or forcing projects to migrate all tests at once. Deliver an evidence-backed design recommendation, with implementation left to separately scoped work.

## Context to re-verify

Requested by the user after a shadow discussion of t1853_4's draft plan on 2026-10-21. The draft allows a runner to list test variants without declaring an axis, exempts those variants from axis-specific findings, and selects them together when their base test is selected. This preserves compatibility, but a forgotten declaration may look like intentional non-adoption and receive neither precise axis selection nor related checks. Verify what actually landed before drawing conclusions.

## Exploration

1. Read t1853_4's final notes, code and tests and record the baseline commit. Reproduce no-axis, partially adopted, fully adopted and invalid-declaration cases, including a mixed project with several runners.
2. Determine which facts can distinguish deliberate non-adoption from an omission; document cases where intent cannot be inferred. Do not infer an axis from variant names without evidence.
3. Compare the existing behavior with informational adoption summaries, opt-in diagnostics, explicit opt-out declarations and stricter validation only after project opt-in. Assess visibility, false positives, warning noise, migration effort, configuration burden, CI/automation impact and compatibility.
4. Examine existing onboarding, maintenance and automatic repair work (including t1853_7) to avoid duplicate mechanisms. Recommend an integration point and the smallest useful change, or justify leaving the behavior as-is.

## Deliverables / acceptance

- A durable comparison backed by reproducible examples showing what users and automation can currently observe.
- A recommendation with sample text/structured output, adoption behavior and clear limits on what can be inferred.
- Preserve gradual adoption and avoid adding a mandatory human acknowledgement step.
- Identify focused implementation work and acceptance checks only where evidence supports a change; this task itself need not modify production behavior.

## Starting references

- aiplans/p1853/p1853_4_m2_4_axes_and_variants.md (or its archived successor)
- goengines/internal/testmap/axes/
- goengines/internal/testmap/runner/
- goengines/cmd/ait-testmap/
- aidocs/testing_engine/n014_explorer_006_proposal.md
- t1853_7 (automatic repair), t1857 (onboarding), t1860 (maintenance/workflow integration); resolve current paths by ID
