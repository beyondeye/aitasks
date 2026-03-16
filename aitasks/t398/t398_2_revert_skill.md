---
priority: medium
effort: medium
depends: [t398_1]
issue_type: feature
status: Implementing
labels: [aitask_revert]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-16 10:38
updated_at: 2026-03-16 14:48
---

Create .claude/skills/aitask-revert/SKILL.md — the complete interactive revert workflow skill.

## Context
This is child 2 of t398 (aitask-revert). Depends on t398_1 (the analysis script). This child creates the skill definition that orchestrates the entire revert experience: task discovery, analysis, revert type selection, area selection for partial reverts, revert task creation, and handoff to the task-workflow.

Also fold t38 into t398 as part of this work (t38 is already marked Folded with folded_into: 398).

## Key Files to Create
- `.claude/skills/aitask-revert/SKILL.md` — The skill definition

## Reference Files for Patterns
- `.claude/skills/aitask-explore/SKILL.md` — Primary pattern: discovery → task creation → handoff
- `.claude/skills/aitask-fold/SKILL.md` — Task selection and confirmation patterns
- `.claude/skills/user-file-select/SKILL.md` — Reusable file selection (delegated to for drill-down)
- `.claude/skills/aitask-explain/SKILL.md` — Reference for explain infrastructure integration
- `.claude/skills/task-workflow/SKILL.md` — Handoff target (Step 3 onwards)

## Implementation Plan

### Skill Workflow Steps:

**Step 0: Profile Selection** — Same pattern as aitask-explore Step 0a. Scan profiles, auto-load or ask.

**Step 1: Task Discovery** — Three paths via AskUserQuestion:
- **Direct argument** (`/aitask-revert 42`): Parse argument, validate task ID exists (check active + archived via aitask_query_files.sh or resolve_task_file), skip to Step 2
- **"Browse recent tasks"**: Call `aitask_revert_analyze.sh --recent-tasks --limit 20`, present list with AskUserQuestion pagination (3 tasks per page + Show more, same as aitask-pick Step 2c)
- **"Search by files"**: Invoke `user-file-select` skill to select files, then use `aitask_explain_extract_raw_data.sh --gather <files>` to map files → task IDs from the reference.yaml output, present discovered task list

**Step 2: Task Analysis & Confirmation**
- Read the task file (may be archived — use resolve_task_file pattern)
- Run `aitask_revert_analyze.sh --task-commits <id>` to list all commits
- Run `aitask_revert_analyze.sh --task-areas <id>` to show area breakdown
- For parent tasks: show per-child breakdown of commits
- Display summary to user with AskUserQuestion: "Confirm" / "Select different task" / "Cancel"

**Step 3: Revert Type Selection** — AskUserQuestion:
- **"Complete revert"** (description: "Revert all changes from this task")
- **"Partial revert"** (description: "Select which areas/components to revert and which to keep")

**Step 3a: Complete Revert Path** — Ask post-revert disposition:
- "Delete task and plan" (description: "Remove task/plan files entirely")
- "Keep archived" (description: "Keep archived with revert notes added")
- "Move back to Ready" (description: "Un-archive and set to Ready with revert notes")

**Step 3b: Partial Revert Path**
- Present areas from `--task-areas` output
- Use AskUserQuestion with multiSelect (checkboxes) for area selection — areas to REVERT
- Also offer free text option for more granular specification
- Show confirmation summary of what will be reverted vs kept
- AskUserQuestion: "Confirm selection" / "Adjust selection" / "Cancel"

**Step 4: Create Revert Task**
- Build detailed task description incorporating:
  - Reference to original task ID and its description summary
  - For complete revert: list of all commits to analyze for reverting
  - For partial revert: list of areas to revert (with files and commits) + areas to keep
  - Post-revert task management instructions (disposition from Step 3a)
  - Instructions for handling the original task file (archive notes, un-archive, or delete)
- Create via `aitask_create.sh --batch --name "revert_t<id>" --type refactor`

**Step 5: Decision Point** — AskUserQuestion (same as aitask-explore):
- "Continue to implementation" → set context variables, handoff to task-workflow Step 3
- "Save for later" → inform user of task file location, end workflow

**Step 6: Handoff** — Set context variables (task_file, task_id, task_name, etc.) and follow task-workflow SKILL.md from Step 3.

### Skill registration:
- Add `aitask-revert` to `.claude/settings.local.json` allowedTools if needed
- The skill is user-invocable as `/aitask-revert` or `/aitask-revert <task_id>`

## Verification Steps
- `/aitask-revert` launches and shows 3 discovery options
- `/aitask-revert <known_id>` skips discovery and shows task analysis
- Browse recent tasks shows paginated list from analysis script
- File drill-down correctly maps files → tasks
- Complete revert path asks for disposition and creates task with correct instructions
- Partial revert path shows area checkboxes and creates targeted task
- Handoff to task-workflow works correctly
- SKILL.md frontmatter is correct (name, description, user-invocable: true)
