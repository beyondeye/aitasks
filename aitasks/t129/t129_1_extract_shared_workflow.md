---
priority: high
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [claudeskills]
created_at: 2026-02-15 17:15
updated_at: 2026-02-15 17:15
---

## Context
This is the foundation task for the dynamic task skill initiative (t129). The current `aitask-pick` skill is a monolithic 872-line SKILL.md that handles the entire task lifecycle. To enable new skills (aitask-explore, aitask-review) to reuse the implementation pipeline without duplication, we need to extract the shared workflow steps into a separate internal skill.

The new skills will share Steps 3-9 (everything after task selection): status checks, assignment, environment setup, planning, implementation, review, and archival. Only the task identification/creation phase differs between skills.

## Key Files to Modify

1. **Create** `.claude/skills/task-workflow/SKILL.md` (~500 lines)
   - Internal skill with `user-invocable: false` in YAML frontmatter
   - Contains Steps 3-9, Task Abort Procedure, Issue Update Procedure, Lock Release Procedure
   - Contains Execution Profiles schema reference and shared Notes

2. **Modify** `.claude/skills/aitask-pick/SKILL.md` (reduce from ~872 to ~370 lines)
   - Keep Steps 0a, 0b, 0c, 1, 2 (profile loading, task selection, remote sync, label filtering, task listing)
   - Replace Steps 3-9 with a handoff section referencing the shared workflow

## Reference Files for Patterns

- `.claude/skills/aitask-pick/SKILL.md` — the source of truth; extract Steps 3-9 from here
- `.claude/skills/aitask-create/SKILL.md` — example of a skill that references aitask_create.sh
- Claude Code skill metadata: use `user-invocable: false` in YAML frontmatter to hide from /menu

## Implementation Plan

### Step 1: Create the shared workflow skill
- Create directory `.claude/skills/task-workflow/`
- Create `SKILL.md` with YAML frontmatter:
  ```yaml
  ---
  name: task-workflow
  description: Shared implementation workflow used by aitask-pick, aitask-explore, and aitask-review. Handles task assignment, environment setup, planning, implementation, review, and archival.
  user-invocable: false
  ---
  ```
- Add a **Context Requirements** section listing the variables the calling skill must provide:
  - task_file, task_id, task_name, is_child, parent_id, active_profile, previous_status
- Copy Steps 3-9 verbatim from current aitask-pick SKILL.md
- Copy Task Abort Procedure, Issue Update Procedure, Lock Release Procedure
- Copy Execution Profiles schema reference (profile keys table) and the Notes section (only parts relevant to Steps 3-9)
- Review all profile checks to ensure they reference `active_profile` consistently

### Step 2: Update aitask-pick SKILL.md
- Keep Steps 0a (profile loading), 0b (direct task selection with argument), 0c (remote sync), 1 (label filtering), 2 (list and select task with pagination and child drilling)
- After Step 2, add a **Handoff to Shared Workflow** section:
  ```
  At this point, a task has been selected. Set the following context, then read and follow
  the shared workflow in `.claude/skills/task-workflow/SKILL.md`:
  - task_file: aitasks/<selected_filename>
  - task_id: <extracted_task_number>
  - task_name: <extracted_from_filename>
  - is_child: <true if child task was selected>
  - parent_id: <parent number if child>
  - active_profile: <loaded profile from Step 0a>
  - previous_status: Ready (the status before picking)
  ```
- Keep aitask-pick-specific Notes that only apply to Steps 0-2

### Step 3: Verify
- Read both files to ensure no content was lost or duplicated
- Verify the handoff context variables match the Context Requirements
- Check that all `bash` command references are preserved correctly

## Verification Steps

1. Read the new `.claude/skills/task-workflow/SKILL.md` and verify it contains all Steps 3-9 plus procedures
2. Read the updated `.claude/skills/aitask-pick/SKILL.md` and verify it contains Steps 0-2 plus the handoff
3. Verify no step content was lost by comparing total line counts
4. Run `/aitask-pick` on a test task to verify the full workflow still functions (this would be manual testing after the refactor)
