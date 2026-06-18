---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-18 12:50
updated_at: 2026-06-18 15:38
---

## Origin

Spawned from t1016_2 (anchor doc consolidation) during Step 8b review, while
propagating the new `anchor:` field into the generated agent-instruction mirrors.

## Upstream defect

`.codex/instructions.md:1` / `.opencode/instructions.md:1` — these committed
instruction mirrors lack the `>>>aitasks`/`<<<aitasks` markers that
`setup_codex_cli` / `setup_opencode_cli` (`aitask_setup.sh` ~L1939 / ~L2090) use
via `insert_aitasks_instructions()`. Because the markers are absent, a future
`ait setup` run would **append a duplicate aitasks block** (a second
`## Task File Format`, etc.) rather than replacing the existing block in place.
AGENTS.md is unaffected — it carries the `>>>aitasks` markers and round-trips
cleanly via `update_agentsmd`.

The two mirrors instead use a markerless `<!-- Assembled from
seed/aitasks_agent_instructions.seed.md + seed/<agent>_instructions.seed.md -->`
full-file format, so today they are effectively hand-maintained (the last
schema change, commit d7a968969, propagated by hand).

## Diagnostic context

During t1016_2 the mirrors were first regenerated with
`insert_aitasks_instructions`, which appended a duplicate marked block to the
codex/opencode files (verified: produced a second `## Task File Format` and
ballooned the files from ~82 to ~176 lines). This was reverted with
`git checkout --` and the two files were hand-edited instead. AGENTS.md
regenerated cleanly via `update_agentsmd "$PWD"` (in-place marker replacement).

## Suggested fix

Pick one and make codex/opencode mirror generation consistent with AGENTS.md:
1. Add the `>>>aitasks`/`<<<aitasks` markers to `.codex/instructions.md` and
   `.opencode/instructions.md` (one-time), so `insert_aitasks_instructions`
   replaces in place on the next `ait setup`; OR
2. Switch `setup_codex_cli` / `setup_opencode_cli` to a full-file regeneration
   that owns the whole file (matching the current markerless assembled-comment
   format) instead of marker-insertion.
Add a regression check (extend `tests/test_agent_instructions.sh`) asserting a
second `setup_*` run does not duplicate the aitasks block in either mirror.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-18T12:38:28Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-18T12:38:30Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-18T12:44:54Z status=pass attempt=1 type=human
