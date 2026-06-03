---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Done
labels: [cross_repo, task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-30 23:27
updated_at: 2026-06-03 11:17
completed_at: 2026-06-03 11:17
---

## Context

Deferred follow-up from t832_5 (Done, archived). t832_5 added two
task-workflow closure procedures and wired them into the `/aitask-pick`
flow:

- `planning-cross-repo.md` — read-only cross-repo **design**, dispatched from
  `.claude/skills/task-workflow/planning.md` §6.1.
- `cross-repo-child-assignment.md` — post-approval **creation** (cross-repo
  parent + child assignment), dispatched from
  `.claude/skills/task-workflow/SKILL.md` Step 7.

This task extends the same paired-planning dispatch to `aitask-explore`,
which has its own explore → design → create surface.

## Key Files to Modify

- `.claude/skills/aitask-explore/SKILL.md.j2` — add the cross-repo **design**
  dispatch at its planning site and the post-approval **child-assignment**
  (creation) dispatch at its task-creation point.
- Reuse the two procedure files unchanged (no content port).

## Reference Files for Patterns

- `.claude/skills/task-workflow/planning.md` §6.1 — the design-only dispatch
  wire-in (metadata-only `xdeprepo` trigger; threads `cross_repo_planned`).
- `.claude/skills/task-workflow/SKILL.md` Step 7 — the post-approval
  "Cross-repo child assignment" creation hook.
- `.claude/skills/task-workflow/planning-cross-repo.md`,
  `.claude/skills/task-workflow/cross-repo-child-assignment.md` — procedures
  to dispatch.
- `aiplans/archived/p832/p832_5_parallel_cross_repo_planning_procedure.md` —
  t832_5 plan + Final Implementation Notes (design rationale).

## Implementation Plan

1. Locate aitask-explore's planning site and its post-approval creation point.
2. **Trigger-source design decision (the crux):** `/aitask-pick` reads
   `xdeprepo` from an *existing* task's frontmatter. `aitask-explore`
   *creates* the task, so there is no pre-existing `xdeprepo`. Decide how
   cross-repo intent is captured in the explore flow — e.g. explore's create
   step sets `xdeprepo` (interactively, like `aitask-create`'s
   `select_xdeprepo`), then dispatches the design procedure. Resolve this
   before wiring.
3. Dispatch `planning-cross-repo.md` (design) at the planning site; on
   `cross_repo_planned: true`, record the paired design and skip explore's
   normal single-task creation; thread `cross_repo_planned`.
4. Dispatch `cross-repo-child-assignment.md` (creation) at the post-approval
   point.
5. Re-render + verify; regenerate aitask-explore goldens in the same commit.

## Verification Steps

- `./.aitask-scripts/aitask_skill_verify.sh` PASS for aitask-explore across
  all profiles.
- Regenerate `tests/golden/skills/aitask-explore/` goldens in the same commit.
- Add/extend a test asserting the explore wire-in dispatches both procedures.

## Notes

- The two procedures are reused unchanged — purely a wire-in plus an
  explore-specific trigger-source design decision.
- Codex/OpenCode "ports" are no-ops (the task-workflow closure auto-renders
  per-agent — verified across 3 agents in t832_5); the agy wire-in folds into
  the t835 agy work.
- Builds on t832_5 (archived, Done).
