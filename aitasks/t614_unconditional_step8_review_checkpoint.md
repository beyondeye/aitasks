---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_workflow]
created_at: 2026-04-21 12:28
updated_at: 2026-04-21 12:28
---

Update `.claude/skills/task-workflow/SKILL.md` Step 8 so the "Implementation complete, please review and test" review checkpoint fires **unconditionally**, regardless of profile (including `fast` and auto mode), plan-approval state, or satisfaction-feedback answers.

## Context & motivation

This task was created during t612 (consolidation of Claude Code auto-memory into durable docs). The memory entry `feedback_await_review_checkpoint.md` recorded the following incident on t586:

> I committed the refactor, archived, pushed, and even applied a follow-up fix to main after the user's satisfaction-feedback answer — all while the user was still reviewing the initial change. The user flagged this: plan approval is scoped to the plan, satisfaction feedback is not a review sign-off, and the `fast` profile's `skip_task_confirmation` only skips the *task selection* confirmation at the front of the workflow, not the Step 8 review gate at the end.

The rule belongs in `task-workflow/SKILL.md` (not CLAUDE.md) because it is workflow-internal — it should port to `.opencode/`, `.gemini/`, `.codex/`, `.agents/` via the normal skill-mirroring procedure, so all code agents behave consistently.

## Required changes

1. In `task-workflow/SKILL.md` Step 8, add an explicit pre-amble stating:
   - Step 8 is unconditional. Even under `fast` / auto mode, surface the "Commit changes / Need more changes / Abort" AskUserQuestion and wait.
   - Plan approval (via ExitPlanMode) covers the plan ONLY — not commit/archive/push.
   - Satisfaction-feedback answers are review INPUT, not approval. Apply them and re-surface Step 8 — do not interpret them as "and now proceed through archive/push."
   - No profile key currently legitimately skips Step 8. If tempted to skip because the profile "feels autonomous," stop and ask instead.
2. Audit other profile keys (`skip_task_confirmation`, `post_plan_action`, `post_plan_action_for_child`, `qa_mode`) to ensure the description of each is clear about what it gates and what it does NOT gate. Specifically, `skip_task_confirmation` should be noted as scoping only the task-selection confirmation at the start of the workflow.

## Follow-up aitasks (create during implementation)

Create sibling/follow-up aitasks to mirror the Step 8 unconditionality clarification into the ported trees once the Claude-Code version lands:

- `.opencode/skills/task-workflow/SKILL.md`
- `.gemini/skills/task-workflow/SKILL.md` (and/or `.gemini/commands/` if applicable)
- `.codex/prompts/` and `.agents/skills/task-workflow/SKILL.md`

## Acceptance

- [ ] `task-workflow/SKILL.md` Step 8 includes the unconditionality pre-amble
- [ ] Profile-key descriptions distinguish "gates task-selection" from "gates commit"
- [ ] Follow-up aitasks exist for each non-Claude agent tree

## Origin

Extracted from `~/.claude/projects/-home-ddt-Work-aitasks/memory/feedback_await_review_checkpoint.md` during t612 (the memory file has since been deleted).
