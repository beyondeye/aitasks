---
priority: medium
effort: medium
depends: [t884_4]
issue_type: enhancement
status: Implementing
labels: [task_workflow, task-planning]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 00:31
updated_at: 2026-06-01 19:04
---

## Context

Child of t884 (see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Implements the user's chosen **read-time signal at pick**: when a "before" risk-mitigation task lands (is archived), force re-verification of the original task's plan on the next pick — because the codebase changed underneath the plan. Depends on t884_1 (the `risk_mitigation_tasks` field) and t884_4 (which populates it).

Verified: `completed_at` IS written at archive (`aitask_archive.sh:145-147`), so each mitigation's completion time is readable from its archived task file. `aitask_plan_verified.sh` is already allowlisted → the new flag needs NO new permission touchpoints.

## Key Files to Modify

- `.aitask-scripts/aitask_plan_verified.sh` — add a `--force-verify` flag to the `decide` subcommand. **Pure-additive: when the flag is absent, `decide` MUST emit the byte-identical 8 `KEY:value` lines it does today** (so the existing planning.md parser is untouched). When present, short-circuit to `DECISION:VERIFY` with a distinct `DISPLAY:` line.
- `.claude/skills/task-workflow/planning.md` — add **Step 6.0a** (a SUFFIX, before the existing §6.0 profile-preference logic; do NOT renumber 6.0): read the task's `risk_mitigation_tasks`; for each, locate its archived task file and read `completed_at`; compare against the plan's most-recent `plan_verified` timestamp (via `aitask_plan_verified.sh read`/`decide`). If any mitigation completed later, pass `--force-verify` to the `decide` call. **No-op when `risk_mitigation_tasks` is absent/empty** (fall straight through to existing 6.0).
- Regenerate goldens (`tests/golden/skills/`, `tests/golden/procs/task-workflow/`) + run `aitask_skill_verify.sh` **same commit**.
- (Optional helper) If the signal logic is non-trivial, a small `.aitask-scripts/` helper is acceptable; if added, apply the 7-touchpoint allowlist (runtime + seed for claude/codex/opencode). Prefer extending `aitask_plan_verified.sh` to avoid a new script.

## Reference Files for Patterns

- `aitask_plan_verified.sh` `cmd_decide` (~186-246) — the 8-line output contract + staleness logic; `read` subcommand (~56-95) for the last-verified timestamp; portable epoch parsing (`parse_ts` ~45-52).
- `aitask_archive.sh:145-147` — `completed_at` write format.
- `aitask_query_files.sh` — resolving archived task files.
- `planning.md` §6.0 Verify Decision sub-procedure — where `decide` is currently called (the place to thread the flag).

## Implementation Plan

1. Add `--force-verify` to `aitask_plan_verified.sh decide` (additive; keep no-flag output byte-stable — add a unit test asserting this).
2. Add Step 6.0a in planning.md computing the signal and passing the flag on the verify path; no-op when field empty.
3. Regenerate variants + goldens; run `aitask_skill_verify.sh`.

## Verification Steps

- Unit: `aitask_plan_verified.sh decide <plan> 1 24` output is identical before/after this change (diff = empty); `... 1 24 --force-verify` returns `DECISION:VERIFY`.
- Simulate: task with `risk_mitigation_tasks: [<id>]` whose archived file has a `completed_at` later than the plan's last `plan_verified` → pick forces verify mode; earlier `completed_at` → normal flow; absent field → unchanged flow.
- `aitask_skill_verify.sh` passes; `shellcheck aitask_plan_verified.sh`.

## Notes for sibling tasks

Step 6.0a is a suffix — keep 6.0/6.1 numbering and the existing decide parser stable. Force-reverify is invisible plumbing; t884_6 docs it as a one-liner only.
