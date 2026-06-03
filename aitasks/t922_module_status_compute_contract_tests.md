---
priority: medium
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-03 09:59
updated_at: 2026-06-03 10:20
boardcol: now
boardidx: 20
---

## Origin

Risk-mitigation ("after") follow-up for t756_5, created at Step 8d after the
Phase D1 status-views implementation landed.

## Risk addressed

Goal-achievement (medium) + code-health (medium) from the t756_5 plan's `## Risk`:
- The `merged` (cross-subgraph `parents` walk) and `implemented` (live-vs-archived
  task-file resolution) computations are the two states most likely to be subtly
  wrong, and both are new cross-reference logic; a mis-scoped walk or a missed
  archived-path case yields a silently-wrong badge.
- Wiring `_node_module()` into the dashboard render path (regression guard).

## Goal

t756_5 shipped `tests/test_brainstorm_module_status.py` (10 tests) covering each
of the six §4.7 states, the deferred-overlay orthogonality, the archived
`implemented` resolution, and the `module_deferred` round-trip. This follow-up
HARDENS that surface beyond the in-task unit tests — do not duplicate them:

- **Edge / combinatoric cases** not in the in-task suite: a module that is BOTH
  `deferred` AND `merged`; a multi-module session where two subgraphs have
  different statuses simultaneously; a `module_tasks` entry pointing at a task
  whose file is missing (resolver returns `(None, False)` → in_design); a
  malformed task frontmatter (no `status:` / unparseable YAML) → graceful
  in_design; `_resolve_task_state` for a parent id vs a child id.
- **`is_module_merged` precision:** confirm a HEAD that appears in a SAME-subgraph
  node's parents does NOT count as merged; confirm merge detection across more
  than two subgraphs.
- **Render-layer regression guard:** a lightweight check that
  `module_status_rows` feeds `_update_module_status` without raising for the
  umbrella-only session and for a populated multi-module session (Textual pilot
  or a direct call against a seeded session), guarding the `_node_module`
  dashboard wiring.

Reference: `aiplans/archived/p756/p756_5_*.md` (Final Implementation Notes),
`.aitask-scripts/brainstorm/brainstorm_status.py`,
`tests/test_brainstorm_module_status.py` (the seed/chdir patterns to reuse),
and t756_4's `tests/test_brainstorm_module_sync_apply_contract.py` (t913) as the
sibling precedent for this kind of contract-test follow-up.
