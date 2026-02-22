---
Task: t196_1_implement_core_skill.md
Parent Task: aitasks/t196_aitaskwrap_skill.md
Sibling Tasks: aitasks/t196/t196_2_document_in_website.md, aitasks/t196/t196_3_workflow_and_usage_guide.md
Archived Sibling Plans: (none yet)
---

## Context

Implement the core aitask-wrap skill for Claude Code. This skill retroactively wraps uncommitted changes into the aitasks framework — creating a task file and plan file that document ad-hoc changes for traceability, even when work was done outside the normal task workflow.

## Plan

Create `.claude/skills/aitask-wrap/SKILL.md` — a single file following existing SKILL.md conventions. No shell scripts needed; the skill uses existing infrastructure (`aitask_create.sh`, `aitask_archive.sh`).

### Workflow Design

1. **Step 0**: Detect uncommitted changes via `git status --porcelain` and `git diff --stat`. Abort if no changes. Allow user to select specific files or include all.
2. **Step 1**: Analyze the diff to determine: factual summary, probable intent, suggested issue_type/name/labels/priority/effort.
3. **Step 2**: Present analysis and let user confirm or adjust metadata and descriptions.
4. **Step 3**: Final "Ready to commit?" confirmation gate — after this, everything executes without further prompts.
5. **Step 4**: Execute all-in-one: create task file → create plan file → stage and commit code changes → archive task → push.
6. **Step 5**: Display final summary.

### Key Design Decisions

- Self-contained skill (no handoff to task-workflow — work is already done)
- Single confirmation gate: all user interaction before Step 3, automated execution after
- Plan file uses "Final Implementation Notes" format (retroactive documentation)
- Single task per invocation (v1 simplicity)
- Status flow: Ready → immediately archived to Done in one shot

## Final Implementation Notes

- **Actual work done:** Created `.claude/skills/aitask-wrap/SKILL.md` (192 lines) implementing the complete workflow as designed. The skill covers: change detection, diff analysis, user confirmation with adjustment loops, final confirmation gate, and an all-in-one execute step (task create → plan create → code commit → archive → push).
- **Deviations from plan:** None — implementation followed the approved plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `--desc-file -` with heredoc for task descriptions (avoids shell escaping). Plan file metadata includes `Created by: aitask-wrap` to distinguish retroactive documentation from forward-looking plans.
- **Notes for sibling tasks:** The SKILL.md follows the same YAML frontmatter + markdown workflow structure as all other skills. The skill is auto-discovered — no registration needed. t196_2 (website docs) should document the workflow steps and when to use wrap vs create. t196_3 (usage guide) should cover the scenarios listed in its task description (quick fixes, debugging-turned-improvements, config changes, pair programming).
