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

After t1853_4 lands, explore whether axis listing should use live test discovery, the committed scan, or an explicit choice between them. Recommend a clear contract balancing freshness, reproducibility, availability and cost; do not assume a new flag or cache is necessary.

## Context to re-verify

Requested by the user after a shadow discussion of t1853_4's draft plan on 2026-10-21. The coarse plan describes variant counts from the saved scan; the detailed draft proposes live discovery for axes --list, following the check command. Live discovery can provide current counts but depends on runner availability and can disagree with the committed data used by later test selection. These are draft observations, not confirmed defects.

## Exploration

1. Read t1853_4's final notes and implementation, record the baseline commit, and verify the actual inputs and side effects of axes --list, --check and --explain. Locate the current selector contract under t1855 and distinguish existing behavior from future assumptions.
2. Reproduce fresh and stale saved scans, missing scans, unavailable or failing runner discovery, excluded tests and a changed variant set. Compare listed counts with the saved selection input and measure discovery overhead on a representative fixture or available project. Record limitations if no representative project is available.
3. Compare live-only, saved-only and explicitly chosen live/saved modes; consider whether simply reporting data provenance and freshness would solve the confusion. Assess reproducibility, offline availability, latency, maintenance cost, output compatibility, and error/fallback behavior. Avoid silently mixing sources.
4. Recommend the smallest improvement, or justify retaining the existing contract. Define defaults, absent/stale-data handling, machine-readable provenance if useful, and concrete examples explaining any difference between listing and selection.

## Deliverables / acceptance

- A durable decision record with observed command outcomes, selected/listed data comparison and measured or explicitly unmeasured costs.
- A reasoned recommendation and acceptance cases for normal, stale and unavailable-discovery scenarios.
- Identify separately scoped implementation work if warranted. This exploration does not require changing production behavior or adding caching infrastructure.

## Starting references

- aiplans/p1853/p1853_4_m2_4_axes_and_variants.md (or its archived successor)
- goengines/cmd/ait-testmap/
- goengines/internal/testmap/registry/
- goengines/internal/testmap/runner/
- aidocs/testing_engine/n014_explorer_006_proposal.md
- t1855 (selection and attribution); resolve current path by ID
