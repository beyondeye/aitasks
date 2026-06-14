---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: feature
status: Done
labels: [bash_scripts, task_workflow, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 16:03
updated_at: 2026-06-14 19:03
completed_at: 2026-06-14 19:03
---

## Context

Child of t986 (shadow agent). For use case 2 — an `AskUserQuestion` shown in the
terminal **without** the source task/plan visible — the shadow needs to
auto-fetch the relevant task file + the **most recent** plan file (and optionally
sibling context) for the task the source agent is working on. This child provides
a single thin helper that wraps the existing canonical scanners.

**True deps:** none — pure-ish wrapper, parallelizable with t986_1/t986_2 (the
sequential sibling dep only orders it).

## Key Files to Modify / Create

- **Create** `.aitask-scripts/aitask_shadow_context.sh` (whitelisted helper;
  add to the helper-script whitelist used by `tests/` and the skill-bash audit).
  Given a source task id, emit structured lines: the task file path, the
  most-recent plan path, and (optionally) sibling task/plan paths.
- Add a focused unit test `tests/test_shadow_context.sh`.

## Reference Files for Patterns

- `.aitask-scripts/aitask_query_files.sh` — `task-file <N>`, `plan-file <N>`,
  `sibling-context <parent>`, `archived-task <id>`. Parent `t130` ↔ children
  `t130/t130_M_*.md`; plans `aiplans/p<N>...` / `aiplans/p<parent>/p<parent>_<child>_*`.
- `.aitask-scripts/aitask_explain_context.sh` — canonical source-files→related-
  plans scanner for **deeper** context (`--max-plans N`); the shadow uses this
  only on demand. Do NOT reinvent its cache (`.aitask-explain/codebrowser/`).
- "Most recent plan" selection: when multiple plans match, pick the latest
  (lexicographic/`ls` order, take last) — mirror how `plan-file` output is
  consumed in `task-workflow/planning.md` §6.0.

## Implementation Plan

1. Resolve the task file: `aitask_query_files.sh task-file <id>` (active first,
   then archived via `archived-task`).
2. Resolve the most-recent plan: `aitask_query_files.sh plan-file <id>`; if
   multiple, select the latest.
3. Optional sibling context (flag-gated, off by default to stay cheap):
   `aitask_query_files.sh sibling-context <parent>`.
4. Emit a stable, parseable contract (e.g. `TASK_FILE:`, `PLAN_FILE:`,
   `SIBLING:` lines, `NOT_FOUND` when absent) the shadow skill can consume.
5. Keep it a thin orchestrator over the existing scripts — no parallel cache, no
   forked scan logic.

## Verification Steps

- `bash tests/test_shadow_context.sh`: fixture tasks (parent + child, active +
  archived) → correct task/plan resolution; most-recent-plan selection when
  several plans exist; `NOT_FOUND` path.
- `shellcheck .aitask-scripts/aitask_shadow_context.sh`.
- Confirm the helper is registered in the helper-script whitelist (so the skill
  may call it without a permission prompt and the no-inline-bash audit passes).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-14T15:49:12Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-14T15:49:13Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-14T16:02:26Z status=pass attempt=1 type=human
