---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, framework, skill]
children_to_implement: [t583_4, t583_5, t583_6, t583_7, t583_8]
created_at: 2026-04-17 11:20
updated_at: 2026-04-19 12:49
boardidx: 20
---

## Context

Many tasks — especially TUI work, end-to-end integrations, and anything whose behavior can only be inspected by a human at a running terminal — cannot be fully validated by automated tests. Today this work gets one of two fates: the implementer pastes a checklist into the plan's "Verification" section (which tends to be ignored after archival) or into the task body (which bloats the task file and is still easy to skip).

The immediate motivating example is t571 (Structured Brainstorming Sections): t571_4 and t571_5 both produce UI behavior that cannot be covered headlessly beyond a point. An ad-hoc aggregate sibling task `t571_7_manual_verification_*` was created to hold the in-person checklist for the whole family — see that task for the pattern in action.

This task formalizes that pattern into a first-class module of the `/aitask-pick` workflow.

## Goals

1. **Recognize manual-verification tasks.** A picked task that declares itself a manual-verification target (either via `issue_type: manual_verification` or a frontmatter flag like `requires_manual_verification: true`) enters a dedicated branch of the workflow instead of Step 6 (plan) + Step 7 (implement).

2. **Interactive checklist runner.** The module reads the task body (or a structured `verification:` frontmatter list — design decision during implementation) and drives the user through each item one at a time:
   - Render the item's prose in the terminal
   - Ask: `Pass` / `Fail` / `Skip (with reason)` / `Defer`
   - Persist the per-item state to the task file under `verification_state:` frontmatter (or an inline checklist with machine-parseable markers)
   - Refuse to archive until every item has a terminal state (pass / fail / skip) — no orphan unchecked items

3. **Auto follow-up on failure.** When an item is marked Fail, the module offers to create a follow-up bug task with the following pre-populated:
   - Origin: the feature task whose behavior failed (the task that introduced the code under test). For aggregate tasks like t571_7, the user picks which feature sibling the failure belongs to (a first-class `verifies: [t571_4, t571_5]` frontmatter enumerates the candidates).
   - Commit references: the commits that introduced the failing code (resolved from the feature task's archived plan's commit list)
   - Source-file references: files touched by those commits, with line-level context where available
   - The exact verification step prose that failed, copy-pasted into the bug task description
   - A `related: [origin_task_id]` field on the bug task, and a back-reference note appended to the origin feature task's archived plan's Final Implementation Notes

4. **Aggregate-task support.** Recognize `verifies: [task_id, ...]` frontmatter that lists the feature siblings this aggregate covers. Route the Fail → follow-up prompt through those candidates instead of defaulting to the aggregate task itself.

5. **Defer handling.** A `Defer` item stays unchecked across archival (the task can be re-picked later) — but the module refuses to archive while any item is deferred, unless explicitly told "archive with deferred items" (creates a "verification carry-over" task automatically).

## Out of Scope (explicit)

- Automated Pilot/TUI test orchestration — that belongs in `aitask-qa`. This module is for live human checks only.
- Replacing the existing plan → implement flow. Manual-verification tasks coexist with feature tasks; they are not a substitute for engineering the code under test.

## Design Questions (resolve at plan time)

- **State format.** Frontmatter `verification_state:` dict vs. inline markdown checkboxes parsed with regex? (Frontmatter is cleaner but requires CLAUDE.md's "Adding a New Frontmatter Field" 3-layer update: create/update scripts, fold_mark union, board `TaskDetailScreen` widget.)
- **Checklist source of truth.** Frontmatter `verification:` list vs. body-embedded markdown list? Frontmatter is machine-friendly; markdown is human-friendly. Decide or support both.
- **Skill vs. module.** Implement as a dedicated skill (`/aitask-verify`) that the current `/aitask-pick` delegates to when the task is manual-verification — or as an in-line branch of Step 6/7 inside `task-workflow/SKILL.md`? Per `feedback_agent_specific_procedures`, a dedicated procedure file is cleaner; this likely lives under `.claude/skills/task-workflow/manual-verification.md` with conditional referencing from `SKILL.md`.
- **Follow-up task creation.** Reuse `aitask_create.sh --batch` or a dedicated `aitask_create_followup.sh` with commit-resolution baked in? Leaning toward a new helper script that takes `--from-failed-verification <task_id> --item <N>` and derives the rest.

## Deliverables

1. New procedure file under `.claude/skills/task-workflow/` describing the manual-verification workflow branch.
2. Updated `task-workflow/SKILL.md` that detects the manual-verification condition in Step 3 (right after status checks) and branches to the new procedure instead of Step 6.
3. Helper script(s) under `.aitask-scripts/` for per-item state persistence, follow-up task creation with commit/file resolution, and the `verifies:` frontmatter lookup.
4. If frontmatter is the chosen state format: 3-layer propagation per CLAUDE.md (create/update, fold_mark, board TaskDetailScreen).
5. Unit tests for the state persistence helpers and follow-up generation.
6. Manual verification of the module itself (meta) — captured in its own entry in whatever aggregate task is appropriate at that point.
7. Documentation updates: a new page under `website/content/docs/workflows/` plus a mention in the aitask-pick skill docs.

## References

- Plan that motivated this task: `aiplans/p571/p571_4_section_selection_brainstorm_tui_wizard.md` (Pre-Implementation section)
- Example aggregate task: `aitasks/t571/t571_7_manual_verification_structured_brainstorming.md`
- Shared-procedure pattern: `.claude/skills/task-workflow/*.md` (e.g., `planning.md`, `satisfaction-feedback.md`)
- CLAUDE.md → "Adding a New Frontmatter Field" (3-layer propagation rule)
- CLAUDE.md → "WORKING ON SKILLS / CUSTOM COMMANDS" (Claude Code is source of truth; mirror into Gemini/Codex/OpenCode after design settles)
