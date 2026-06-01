---
priority: medium
effort: medium
depends: [t756_5]
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstom_modules, tui]
created_at: 2026-06-01 17:30
updated_at: 2026-06-01 17:30
---

Phase D2 of the `ait brainstorm` **module decomposition** feature (parent t756).
The **ergonomics** half of the original Phase D: the polished "Fast-track this module"
wizard preset (UC-3) on top of the functional `module_decompose --link-to-task` path
that landed in Phase B2 (t756_3). Depends on Phase D1 (t756_5) for the surrounding TUI
surfaces.

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.8 UC-3 = decompose --modules=one + linked_task; §7 Phase D). **Binding
conventions:** `aiplans/p756_brainstorm_modules.md`. **TUI rules:** read
`aidocs/tui_conventions.md`.

## Context
UC-3 (fast-track) is "extract one module into a real aitask in a single user pass".
The functional path (`module_decompose --modules=one + --link-to-task`) is already
implemented in B2 (t756_3). This child adds the one-pass **wizard preset** UI so the
user does not have to drive the multi-module decompose flow for the single-module
case — a presentation/UX layer over the existing op.

## Scope (`brainstorm_app.py`)
- "Fast-track this module" wizard **preset** — a one-step entry that drives
  `module_decompose` with a single module name + `--link-to-task` in one pass
  (subgraph root + linked aitask created together).
- Surface it as an additional entry alongside the multi-module decompose path; both
  route through the same `register_module_decomposer()` call (§4.8 — no new op).

## Reuse t873 TUI helpers (do NOT reinvent)
- `FuzzyCheckList.set_grouped_items(groups)` — `brainstorm_app.py:~1654` — for any
  grouped/filterable selection in the preset UI.

## Reference Files for Patterns
- `aidocs/tui_conventions.md` (mandatory).
- B2's (t756_3) `register_module_decomposer()` `--link-to-task` path and wizard branch.
- D1's (t756_5) dashboard/badge surfaces this preset sits alongside.

## Implementation Plan
1. Add the "Fast-track this module" preset entry to the wizard.
2. Wire it to a single-module `module_decompose --link-to-task` invocation in one pass.
3. Confirm it reuses the B2 functional path (no duplicate op logic).

## Verification Steps
- The "Fast-track this module" preset creates a subgraph + linked task in a single
  pass (one user invocation).
- The preset routes through the same `register_module_decomposer()` as the
  multi-module path (no forked op logic).
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.
- (Human-observable behavior is covered by the aggregate manual-verification sibling.)
