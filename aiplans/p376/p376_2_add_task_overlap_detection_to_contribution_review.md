---
Task: t376_2_add_task_overlap_detection_to_contribution_review.md
Parent Task: aitasks/t376_check_for_existing_tasks_in_aitaskcontribute.md
Sibling Tasks: aitasks/t376/t376_1_*.md, aitasks/t376/t376_3_*.md, aitasks/t376/t376_4_*.md
Archived Sibling Plans: aiplans/archived/p376/p376_1_*.md
Worktree: (none - current branch)
Branch: (current branch)
Base branch: main
---

## Goal

Add Step 5b to `/aitask-contribution-review` SKILL.md that detects overlapping existing tasks using the shared Related Task Discovery Procedure and offers to fold them into the newly imported task.

## Steps

### 1. Add Step 5b to `.claude/skills/aitask-contribution-review/SKILL.md`

Insert between current Step 5 (Present Proposal) and Step 6 (Execute Import):

```markdown
### Step 5b: Check for Overlapping Existing Tasks

Execute the **Related Task Discovery Procedure** (see `.claude/skills/task-workflow/related-task-discovery.md`) with:
- **Matching context:** The contribution's title, description, areas (`<areas>` from Step 1), file paths (`<file_paths>`), and change type (`<change_type>`)
- **Purpose text:** "already cover this contribution's scope (they can be folded into the imported task or updated directly)"
- **Min eligible:** 1
- **Selection mode:** ai_filtered

**If no overlapping tasks found:** Proceed to Step 6 as normal.

**If overlapping tasks found and user selected task(s):** Use AskUserQuestion:
- Question: "How should the overlap with existing task(s) be handled?"
- Header: "Overlap"
- Options:
  - "Fold into new imported task" (description: "Import the contribution as new task and fold the overlapping existing task(s) into it")
  - "Update existing task instead" (description: "Add contribution content to the existing task — no new task created")
  - "Ignore overlap" (description: "Proceed with normal import, leave existing tasks unchanged")

Store the user's choice and the selected task IDs for use in Steps 6/6b.
```

### 2. Modify Step 6 for fold handling

After the existing Step 6 import commands, add fold logic:

```markdown
**If "Fold into new imported task" was selected in Step 5b:**

After import completes:
1. Parse import output to get the created task file path:
   - Single: look for `Created: <filepath>` in output
   - Merge: look for `Merged N issues into: <filepath>` in output
2. Extract task number from filename (e.g., `t42` from `aitasks/t42_foo.md`)
3. Read each selected overlapping task file and append a "Folded Tasks" section to the new task:
   ```markdown
   ## Folded Tasks

   The following existing tasks have been folded into this task...
   - **t<N>** (`<filename>`)
   ```
4. Update new task frontmatter:
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <new_num> --folded-tasks "<id1>,<id2>"
   ```
5. Mark each overlapping task as Folded:
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <old_num> --status Folded --folded-into <new_num>
   ```
6. Commit:
   ```bash
   ./ait git add aitasks/
   ./ait git commit -m "ait: Fold existing tasks into t<new_num>"
   ```
```

### 3. Add placeholder for Step 6b

Add after Step 6:
```markdown
### Step 6b: Update Existing Task with Contribution (Alternative)

> **See sibling task t376_3 for implementation.** This step is reached when the user chose "Update existing task instead" in Step 5b.
```

This placeholder will be filled by sibling t376_3.

## Key Script References

- `aitask_update.sh --batch <N> --folded-tasks "id1,id2"` — Update folded_tasks frontmatter
- `aitask_update.sh --batch <N> --status Folded --folded-into <M>` — Mark as folded
- `aitask_issue_import.sh` output: `Created: <path>` (line 585) or `success "Merged N issues into: <path>"` (line 804)

## Verification

1. Trace through SKILL.md for: (a) no overlap → normal import, (b) fold → import + fold, (c) ignore → normal import
2. Verify import output parsing handles both single and merge formats
3. Verify `aitask_update.sh` flags are correct

## Final Implementation Notes

- **Actual work done:** Extended scope beyond original plan. In addition to adding Step 5b/6/6b to contribution-review, extracted duplicated task folding logic into two shared procedures (`task-fold-content.md` and `task-fold-marking.md`) and updated all 3 existing callers (aitask-fold, aitask-explore, aitask-pr-import) to reference them.
- **Deviations from plan:** The original plan only modified contribution-review. During planning review, the user identified that the task folding logic was duplicated across 3 skills with bugs (aitask-explore and aitask-pr-import lacked structured `## Merged from t<N>` headers and transitive fold handling). The plan was expanded to extract shared procedures and fix these bugs.
- **Issues encountered:** None.
- **Key decisions:**
  - Split the shared procedure into two files: `task-fold-content.md` (content incorporation) and `task-fold-marking.md` (frontmatter marking) — keeps each focused and allows callers to use them independently
  - Added `handle_transitive: true` to explore and pr-import callers (previously missing — they only had it in aitask-fold)
  - The content procedure is parameterized by primary_description + folded_task_files, accommodating both "merge into existing" (fold, contribution-review) and "incorporate during creation" (explore, pr-import) flows
- **Notes for sibling tasks:**
  - t376_3 (update existing task path): Step 6b placeholder is in place in contribution-review SKILL.md, ready to be filled. The Task Fold Content Procedure can be used for incorporating contribution content into an existing task
  - t376_4 (website docs): The two new shared procedure files (task-fold-content.md, task-fold-marking.md) should be documented in the website's architecture/skills section
  - t376_5 (tests): The shared procedures are skill instructions (markdown), not shell scripts, so they can't be directly unit tested. However, the underlying `aitask_update.sh` flags they reference are testable

## Step 9: Post-Implementation

Archive child task, proceed to sibling t376_3.
