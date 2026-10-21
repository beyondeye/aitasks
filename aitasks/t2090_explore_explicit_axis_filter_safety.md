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

After t1853_4 lands, explore whether explicit axis filtering can be made easier to understand and safer with incomplete declarations while retaining useful control over test-run size. Deliver an evidence-backed design recommendation; this task does not preselect or implement a new policy.

## Context to re-verify

Requested by the user after a shadow discussion of t1853_4's draft plan on 2026-10-21. The draft proposes that automatic selection retains undeclared variant values when their axis is affected, but an explicit forced facet drops variants on that axis unless their declarations prove a match. Other axes and unclaimed ordinary tests pass. These are proposed behaviors, not confirmed implementation facts.

## Exploration

1. Read t1853_4's final implementation notes, landed code and tests; record the baseline commit and actual behavior. Locate the current M4.1 selector work under t1855. Evaluate the library directly if the selector is not implemented yet, and distinguish tested behavior from future integration assumptions.
2. Exercise declared matches and mismatches, undeclared values, missing axes, multiple forced facets, contradictory requests, plain tests with and without claims, and unrelated axes. Show selected and excluded test IDs and explain why each survives or disappears.
3. Compare the landed policy with retaining unknown variants, refusing ambiguous filtering, and reporting exclusions or uncertainty without changing selection. Assess missed-test risk, run size, predictability, automation, compatibility and implementation cost. These alternatives come from the discussion, not an assertion that the original author considered them.
4. Recommend the smallest worthwhile improvement, or justify retaining the current behavior. Define concrete examples, diagnostic/exit behavior and migration implications. Coordinate proposed selector-contract changes with its owning task; do not assume this task owns the selector implementation.

## Deliverables / acceptance

- A durable decision record with reproducible examples, a behavior matrix, pros and cons, and a clear recommendation.
- Keep automatic selection's conservative coverage guarantee explicit; do not silently weaken it to implement a user-requested filter.
- Identify narrowly scoped implementation work and acceptance checks if a change is worthwhile. No production behavior changes are required for this exploration.

## Starting references

- aiplans/p1853/p1853_4_m2_4_axes_and_variants.md (or its archived successor)
- goengines/internal/testmap/axes/
- aidocs/testing_engine/n014_explorer_006_proposal.md
- aitasks/t1855_testmap_m4_selection_freshness_and_feedback.md (resolve current task path by ID if renamed)
