---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: [t1210_3, t1162_4]
issue_type: feature
status: Implementing
labels: [aitask_board, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/fable5
created_at: 2026-07-22 16:16
updated_at: 2026-07-25 23:33
---

## Context

**T4** of the Implementation Trails decomposition (RFC §14 in
`aidocs/implementation_trail_design.md`; parent t1210). The dedicated By-Trail
board view (a v1 user decision — waves as columns, one active trail). RFC §9
is the spec (structure 9.1, state matrix 9.2, launch seams 9.3) plus the §15
wireframes.

**COORDINATION (load-bearing):** this child edits the board
bindings/`check_action` surface that t1162_4 (Work Report board flow) also
edits. It carries an explicit dependency on `1162_4` — do not start it while
t1162_4 is unmerged; verify t1162_4's landed state first and re-check this
task's premises against the then-current `aitask_board.py`.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — new `bytrail` base-filter value +
  binding + `refresh_board()` branch + `check_action()` gating; trail
  discovery (frontmatter scan for `artifacts:` entries with
  `kind: implementation_trail`, active + archived); selection modal; wave
  columns; detail modal; drift check on view entry via
  `aitask_trail_gather.sh drift`.
- Shortcut manifest registration for the new binding (key chosen here — the
  RFC deliberately leaves it open; check the manifest for free keys).

## Reference files for patterns

- `aidocs/framework/tui_conventions.md` — MANDATORY before editing the board.
- View-addition recipe (verified against source): `base_filter` radio at
  `aitask_board.py:4678`, `refresh_board()` per-filter branches at
  `:4866-4928`, `TopicColumn` widget model at `:1475-1505`,
  `check_action` gates at `:4685-4796` (mirror the
  `in ("inflight","bytopic")` guards), cached grouping helper pattern
  `grouped_topic_lanes` at `:527-537`. Line numbers are as of the RFC's
  traceability pass — re-verify after t1162_4 lands.
- Launch seam: `action_pick_task` at `:5750-5790`
  (`resolve_dry_run_command(Path("."), "trail", ...)` +
  `AgentCommandScreen(..., operation="trail", skill_name="trail",
  default_window_name="agent-trail-<id>")`).
- `lib/trail_schema.py` (t1210_1) for validated loading — reads fail closed
  per RFC §9.2 error states.

## Implementation plan

1. Trail discovery + selection modal (title, owner, scope kind, freshness
   badge, last updated; "also in" note on overlap) — exactly one active trail.
2. Wave columns per RFC §9.1: `W<ordinal> · <title>` headers, `TaskCard`s in
   position order, classification/confidence badges, completion
   strike-through from live task state, ghost cards for
   archived/missing/cross-repo members.
3. Detail modal rendering the full narrative projection.
4. State matrix §9.2 in full, including missing-blob / corrupt-manifest error
   cards (fail closed, offer versions fallback).
5. Contextual actions: task card + By-Topic lane header → create/refresh
   trail launches; By-Trail `r` → refresh launch. Board process stays
   read-only for trail content — every write happens in the launched skill.
6. Drift check on view entry updates rendered badges only — never the
   artifact (negative control).

## Verification

- Render-level tests: assert `widget.render().plain` for wave headers, badges,
  ghost cards, stale banner (one model + one render assertion per state).
- Pilot tests for view switch, selection modal, and launch-arg construction
  (construction spy on AgentCommandScreen args, not exit codes).
- Negative control: drift check leaves the artifact byte-identical.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-25T20:33:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-25T21:17:07Z status=pass attempt=1 type=human
