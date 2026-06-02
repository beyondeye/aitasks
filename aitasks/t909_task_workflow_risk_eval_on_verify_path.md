---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow, claudeskills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-02 12:24
updated_at: 2026-06-02 12:49
---

## Problem

On the plan **verify path** of the task-workflow skill, the **Risk Evaluation
Procedure** (`risk-evaluation.md`) and the **Risk-Mitigation Follow-up**
design-in-planning step (`risk-mitigation-followup.md` Part 1) are not reliably
invoked. These two steps are described at the *end of* `planning.md` §6.1 as part
of the create-new-plan narrative ("Risk evaluation (end of planning)…"). When the
6.0 plan-preference check routes to the **verify** path (e.g. a child task whose
profile sets `plan_preference_child: verify`, or `DECISION:VERIFY`), §6.1's
verify branch says only: read the existing plan, re-check assumptions/paths,
update or confirm, then `ExitPlanMode`. It does **not** re-state that the
end-of-planning Risk Evaluation + mitigation design must still run.

Consequence: if the existing plan has no `## Risk` section, the verify path
exits plan mode without authoring one. Step 7's `--risk-code-health` /
`--risk-goal-achievement` frontmatter write and Step 8d's "after" mitigation
creation then silently no-op (they parse a `## Risk` section that was never
written). The risk-evaluation contract is silently skipped on an entire planning
path.

## Evidence

Observed during the `/aitask-pick 756_4` session on 2026-06-02 (fast profile,
child task, verify path). The Risk Evaluation step was skipped and only caught
because the user explicitly asked "did you run the risk evaluation procedure?".
It was then run manually after the fact.

## Goal

Make the Risk Evaluation Procedure and the Risk-Mitigation design-in-planning
step run on **all** planning paths that produce/confirm a plan — create-new,
verify, and the ASK_STALE → "Verify now" branch — not just the create-new
narrative.

## Scope / approach

- Source of truth is the Claude Code skill under `.claude/skills/task-workflow/`.
  The relevant procedure is profile-templated, so edit the `.j2` / closure-`.md`
  source for `planning.md` (and any shared closure), NOT the rendered variants.
- Restructure §6.1 so the "end of planning" Risk Evaluation + Risk-Mitigation
  design is a clearly **shared, NON-SKIPPABLE** terminal step reached by every
  path that calls `ExitPlanMode` (create-new AND verify AND ASK_STALE→verify),
  rather than prose attached only to the create-new flow. Prefer an explicit
  numbered step / marker over relying on the reader to infer it (see the
  `feedback_prefer_source_enforcement_over_memory` principle — enforce in source).
- Consider a guard: before the Step 6 Checkpoint, assert the plan now contains a
  `## Risk` section (or an explicit "risk evaluation skipped because…" note), so
  a missing section is caught deterministically instead of silently.
- After editing any `.md.j2` / closure `.md`: regenerate the affected goldens
  under `tests/golden/skills/` and `tests/golden/procs/`, and run
  `./.aitask-scripts/aitask_skill_verify.sh` (per CLAUDE.md "Working on Skills").

## Cross-agent note

Per CLAUDE.md, fix the Claude Code version first, then suggest sibling aitasks to
port the same fix to the Codex CLI (`.agents/skills/`) and OpenCode
(`.opencode/`) task-workflow trees.

## Verification

- Trace each planning path (create-new, verify, ASK_STALE→verify) and confirm
  every one reaches the Risk Evaluation + mitigation-design step before the
  Checkpoint.
- Dry-run a verify-path pick on a plan with no `## Risk` section and confirm the
  section is now authored (or the skip is explicitly recorded) before approval.
- `./.aitask-scripts/aitask_skill_verify.sh` passes; affected goldens regenerated.
