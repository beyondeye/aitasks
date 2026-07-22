---
priority: low
effort: low
depends: [t1210_5]
issue_type: documentation
status: Ready
labels: [web_site]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-07-22 16:17
updated_at: 2026-07-22 16:17
---

## Context

**T6** of the Implementation Trails decomposition (RFC §14 in
`aidocs/implementation_trail_design.md`; parent t1210). User-facing
documentation for the shipped feature.

## Key files to create/modify

- `website/content/docs/workflows/implementation-trails.md` (new) — the
  end-to-end workflow page: create from task/topic/board, the By-Trail view,
  refresh-on-drift, move-to-column → work report.
- `website/content/docs/workflows/_index.md` — **hand-curated page list: the
  new page needs its own bullet added manually** (this index is not
  generated).
- Board documentation pages — document the By-Trail view alongside the
  existing TUIs (board, monitor, minimonitor, codebrowser, settings,
  brainstorm; keep diffviewer omitted per project note).
- `aidocs/implementation_trail_design.md` — current-state sync: after the
  feature ships, prune any "proposed"/decision-history phrasing so the doc
  describes the shipped state only (documentation_conventions.md rule).

## Reference files for patterns

- `aidocs/framework/documentation_conventions.md` — MANDATORY: current-state
  prose only, no version history, genericize agent references, describe
  manual-verification auto-modes as "autonomous".
- `website/content/docs/workflows/manual-verification.md` — structure
  reference for a workflow page.
- Derive user-facing lists (drift-reason codes, classifications) from the
  canonical schema file rather than duplicating; where prose cannot be
  derived, add an inline drift-guard note referencing the schema.

## Implementation plan

1. Write the workflow page with generic example project names (never the
   author's real repos).
2. Add the `_index.md` bullet.
3. Update board docs for the new view + keybindings.
4. Sweep the RFC for stale "proposed" phrasing; re-sweep after any late
   pivots in the implementation children.

## Verification

- `cd website && hugo build --gc --minify` clean.
- Grep checks: new page linked from `_index.md`; no sibling-path references;
  no framework-internal aidocs paths cited in user-facing prose.
