---
Task: t129_4_create_aitask_review_skill.md
Parent Task: aitasks/t129_dynamic_task_skill.md
Sibling Tasks: aitasks/t129/t129_5_*.md, aitasks/t129/t129_6_*.md
Archived Sibling Plans: aiplans/archived/p129/p129_1_extract_shared_workflow.md, aiplans/archived/p129/p129_2_create_aitask_explore_skill.md, aiplans/archived/p129/p129_3_review_modes_infrastructure.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Create aitask-review Skill (t129_4)

## Context

This task creates the `/aitask-review` Claude Code skill — a Claude-driven code review workflow that uses the review modes infrastructure (from t129_3, now at `aitasks/metadata/reviewmodes/*.md`) to perform targeted code reviews. The skill loads review mode files, auto-detects the project environment, lets the user select modes and target areas, performs the review, presents findings, and creates tasks from selected issues — then optionally hands off to the shared `task-workflow` pipeline.

The shared workflow was extracted in t129_1 (`.claude/skills/task-workflow/SKILL.md`). The sister skill `aitask-explore` (t129_2) provides the closest structural pattern to follow.

## File Created

### `.claude/skills/aitask-review/SKILL.md` (306 lines)

User-invocable skill with YAML frontmatter:
```yaml
---
name: aitask-review
description: Review code using configurable review modes, then create tasks from findings.
---
```

## Workflow Structure

### Step 0a: Select Execution Profile
- Same as aitask-pick/aitask-explore: check `aitasks/metadata/profiles/*.yaml`, auto-load if one, ask if multiple.

### Step 0c: Sync with Remote
- Same pattern: `git pull --ff-only --quiet` and lock cleanup.

### Step 1: Review Setup

**1a. Target Selection** — Three options: specific paths, recent changes (with commit selection), entire codebase.

**1b. Review Mode Selection** — Load modes from `aitasks/metadata/reviewmodes/`, auto-detect environment, sort by relevance, paginated multiSelect.

**1c. Load Review Instructions** — Read markdown body of selected modes.

### Step 2: Automated Review
- Explore target paths using each mode's instructions
- Record findings with: mode, severity, location, description, suggested fix

### Step 3: Findings Presentation
- Grouped by mode and severity, paginated multiSelect for user to choose which to address

### Step 4: Task Creation
- Single task, group by mode, or separate tasks
- Parent+children for multiple tasks using `--no-sibling-dep`

### Step 5: Decision Point
- Continue to implementation or save for later

### Handoff to task-workflow
- 9 context variables (including `folded_tasks: []`)

## Implementation Steps

- [x] Step 1: Create `.claude/skills/aitask-review/` directory and `SKILL.md` with full workflow
- [x] Step 2: Use `git add -f` to track the new file (`.gitignore` has `skills/` rule)
- [x] Step 3: Verify the skill follows patterns from aitask-pick and aitask-explore

## Key Design Decisions

1. **Three target selection options** — specific paths, recent changes, entire codebase
2. **Environment auto-detection** sorts modes by relevance but doesn't hide non-matching ones
3. **Three task creation strategies** — single, group by mode, separate
4. **Profile keys** — `review_default_modes` and `review_auto_continue`
5. **Reuse pagination pattern from aitask-pick** for mode selection and findings
6. **git add -f** for new skill file (same `.gitignore` workaround as t129_1 and t129_2)

## Final Implementation Notes
- **Actual work done:** Created `.claude/skills/aitask-review/SKILL.md` (306 lines) as a user-invocable skill. The skill has 6 workflow steps (0a, 0c, 1-5 plus handoff) following the exact same patterns as aitask-pick and aitask-explore for profile loading, remote sync, and AskUserQuestion usage. Three target selection modes (specific paths, recent changes with commit selection, entire codebase), environment auto-detection for review mode sorting, paginated multiSelect for modes and findings, and three task creation strategies.
- **Deviations from plan:** Several enhancements were added during review: (1) The "Recent changes" commit listing now filters out task-handling commits (start work, archive, add task, fold, abort, changelog, version bump, archive old tasks) to show only implementation-relevant commits. (2) Commit batches are 10 instead of 20, with a "Show 10 more commits" pagination option. (3) Each commit shows `+N/-M` line diff stats from `--shortstat`. (4) The `folded_tasks` context variable was added to the handoff (set to empty list) for consistency with aitask-explore's interface.
- **Issues encountered:** The `.gitignore` `skills/` rule blocks `.claude/skills/` for new files — used `git add -f` (same as t129_1 and t129_2). Verification found the missing `folded_tasks` context variable in the handoff — fixed immediately.
- **Key decisions:** (1) Commit filtering uses 11 patterns matching task lifecycle messages (start work, archive, add task, add child task, update tasks, fold, create child tasks, abort, add changelog, bump version, archive old tasks). (2) Review mode pagination uses the same 3+1 / 4-on-last-page pattern as aitask-pick. (3) Findings presentation includes "Select all" as first option for convenience. (4) Multiple tasks use `--no-sibling-dep` since review findings are typically independent.
- **Notes for sibling tasks:** The skill is at `.claude/skills/aitask-review/SKILL.md` with `name: aitask-review`. It introduces two new profile keys: `review_default_modes` (comma-separated mode names) and `review_auto_continue` (bool). The t129_6 (document aitask-review) task should document these profile keys, the commit filtering patterns, and the full workflow. The `.gitignore` `skills/` issue persists — new skill files need `git add -f`.
