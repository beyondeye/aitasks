---
Task: t129_2_create_aitask_explore_skill.md
Parent Task: aitasks/t129_dynamic_task_skill.md
Sibling Tasks: aitasks/t129/t129_3_*.md, aitasks/t129/t129_4_*.md, aitasks/t129/t129_5_*.md, aitasks/t129/t129_6_*.md
Archived Sibling Plans: aiplans/archived/p129/p129_1_extract_shared_workflow.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Create aitask-explore Skill (t129_2)

## Context

This task creates the `/aitask-explore` skill — a user-driven exploration workflow for cases where the developer doesn't have a specific task defined in advance. Instead of the traditional "define task → pick task" flow, the user starts by exploring the codebase with Claude's help, and when ready, crystallizes findings into a task that hands off to the shared `task-workflow` pipeline.

The shared workflow was extracted in t129_1 (`.claude/skills/task-workflow/SKILL.md`). This skill follows the same patterns as `aitask-pick` for profile loading, remote sync, and AskUserQuestion usage, then hands off to task-workflow after task creation.

## Files to Create/Modify

- **Create** `.claude/skills/aitask-explore/SKILL.md` — user-invocable skill with full exploration workflow
- **Modify** `aitasks/metadata/profiles/fast.yaml` — add `explore_auto_continue: false`

## Implementation Steps

### Step 1: Create skill directory and SKILL.md

Create `.claude/skills/aitask-explore/SKILL.md` with:

**YAML frontmatter:**
```yaml
---
name: aitask-explore
description: Explore the codebase interactively, then create a task for implementation.
---
```

**Workflow structure** (following aitask-pick patterns):

#### Step 0a: Select Execution Profile
- Same pattern as aitask-pick: check `aitasks/metadata/profiles/*.yaml`, auto-load if one, ask if multiple
- Reuse existing profile keys, plus support new optional key `explore_auto_continue` (if true, skip the "continue to implementation vs save for later" question)

#### Step 0c: Sync with Remote
- Same as aitask-pick: `git pull --ff-only --quiet` and lock cleanup

#### Step 1: Exploration Setup
- AskUserQuestion: "What would you like to explore?"
- Options (3 + "Other" for free text):
  - "Investigate a problem" — debugging/perf issues
  - "Explore codebase area" — understanding a module
  - "Scope an idea" — have an idea but need to discover what code is affected

**Each option triggers a tailored follow-up and sets exploration context:**

| Option | Follow-up question | Exploration strategy | Task defaults |
|--------|-------------------|---------------------|---------------|
| Investigate a problem | "Describe the symptom and where you notice it" | Trace data flow, check error handling, find root cause candidates | `issue_type: bug`, priority: high |
| Explore codebase area | "Which module or directory should we focus on?" | Map file structure, key classes, dependencies, architectural patterns | `issue_type: feature`, priority: medium |
| Scope an idea | "Describe the idea briefly" | Find all touchpoints that would need changes, estimate blast radius | `issue_type: feature`, priority: medium |

#### Step 2: Iterative Exploration
- Claude explores using Read, Glob, Grep, Task (Explore agents), guided by the exploration strategy from Step 1
- After each exploration round, present a brief summary of findings so far
- Then AskUserQuestion:
  - "Continue exploring" — keep going, user may redirect focus
  - "I have enough, create a task" — proceed to Step 3
  - "Abort exploration" — stop without creating a task
- Track findings mentally (no file writes during exploration)

#### Step 3: Task Creation
- Summarize exploration findings for the user
- Propose task metadata using defaults from Step 1 table: title, priority, effort, labels, issue_type, description
- AskUserQuestion to confirm or modify the proposed metadata
- Create task using:
  ```bash
  ./aiscripts/aitask_create.sh --batch --commit --name "<name>" --desc-file - --priority <p> --effort <e> --type <issue_type> --labels <l> <<< "<description>"
  ```
- Read back the created task file to get the assigned task ID

#### Step 4: Decision Point
- Profile check: if `explore_auto_continue` is `true`, skip question and go to implementation
- Default when `explore_auto_continue` is not defined: `false` (always ask the user)
- When asking, AskUserQuestion: "Task created: t<N>. How would you like to proceed?"
  - "Continue to implementation" → set context variables, hand off to task-workflow
  - "Save for later" → inform user the task is ready for `/aitask-pick <N>`

#### Handoff to task-workflow
When continuing to implementation, set these 8 context variables:
- task_file, task_id, task_name (from created task)
- is_child: false
- parent_id: null
- parent_task_file: null
- active_profile: from Step 0a
- previous_status: Ready

Then: "read and follow `.claude/skills/task-workflow/SKILL.md` starting from **Step 3: Task Status Checks**"

### Step 2: Update fast profile

Add `explore_auto_continue: false` to `aitasks/metadata/profiles/fast.yaml` to explicitly define it. Even in fast mode, the user should decide whether to continue to implementation or save for later after exploration.

### Step 3: Git add with force flag

The `.gitignore` has `skills/` which blocks `.claude/skills/` for new files. Use `git add -f` to track the new skill file (same approach as t129_1).

## Key Design Decisions

1. **Standalone tasks only** — explore creates top-level tasks, not children
2. **No file writes during exploration** — findings tracked mentally until Step 3
3. **Reuse existing profile keys** — only one new optional key (`explore_auto_continue`)
4. **Same handoff pattern as aitask-pick** — 8 context variables → task-workflow Step 3

## Verification Steps

1. Read the created SKILL.md and verify it follows aitask-pick pattern for profile loading, remote sync, and AskUserQuestion usage
2. Verify the handoff to task-workflow uses the correct 8 context variables
3. Verify the `aitask_create.sh` invocation has `--batch --commit` and all required flags
4. Check `git add -f` is used for the new file

## Final Implementation Notes

- **Actual work done:** Created `.claude/skills/aitask-explore/SKILL.md` (215 lines) as a user-invocable skill. Added `explore_auto_continue: false` to the fast profile. The skill has 4 exploration types (investigate a problem, explore codebase area, scope an idea, explore documentation), each with tailored follow-up questions, exploration strategies, and task metadata defaults. The iterative exploration loop lets the user control when to stop and create a task. Handoff to task-workflow uses the standard 8 context variables.
- **Deviations from plan:** Added a 4th exploration option "Explore documentation" during review — not in the original plan but requested by the user. The documentation option has its own follow-up (project docs vs code docs vs both) and defaults to `issue_type: documentation`. Also created a follow-up task t132_improve_aitask_explore.md for future enhancements (persistent exploration findings, per-type user directions, module-specific hints, exploration history).
- **Issues encountered:** The `.gitignore` `skills/` rule blocks `.claude/skills/` for new files — need `git add -f` (same as t129_1).
- **Key decisions:** (1) Default `explore_auto_continue: false` even in fast profile — exploration is inherently open-ended, user should always decide what to do with the created task. (2) Removed "General exploration" option to avoid overlap with future `/aitask-review` skill (t129_4). (3) AskUserQuestion for follow-ups uses "Other" for free text input since the follow-up questions are open-ended.
- **Notes for sibling tasks:** The skill follows the exact same patterns as aitask-pick for profile loading (Step 0a) and remote sync (Step 0c). The `explore_auto_continue` profile key was added — future skills (t129_4 aitask-review) may want similar `review_auto_continue` keys. The `.gitignore` `skills/` issue persists — all new skill files need `git add -f`.
