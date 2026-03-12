---
Task: t376_3_add_update_existing_task_path.md
Parent Task: aitasks/t376_check_for_existing_tasks_in_aitaskcontribute.md
Sibling Tasks: aitasks/t376/t376_1_*.md, aitasks/t376/t376_2_*.md, aitasks/t376/t376_4_*.md
Archived Sibling Plans: aiplans/archived/p376/p376_1_*.md, aiplans/archived/p376/p376_2_*.md
Worktree: (none - current branch)
Branch: (current branch)
Base branch: main
---

## Goal

Implement the "Update existing task instead" path in Step 6b of contribution-review SKILL.md. When a contribution overlaps an existing task, the user can choose to update the existing task rather than creating a new one.

## Steps

### 1. Replace Step 6b placeholder in `.claude/skills/aitask-contribution-review/SKILL.md`

Replace the placeholder (added by t376_2) with full implementation:

```markdown
### Step 6b: Update Existing Task with Contribution (Alternative)

This step is reached when the user chose "Update existing task instead" in Step 5b.

**Select target task:** If multiple overlapping tasks were selected in Step 5b, use AskUserQuestion:
- Question: "Which existing task should be updated with this contribution?"
- Options: Each selected task (filename + brief summary)

**Append contribution content:**
1. Read the existing task file
2. Append a new section:
   ```markdown
   ## Contribution from <contributor_name> (Issue #<N>)

   **Areas:** <areas from Step 1>
   **Files:** <file_paths from Step 1>
   **Change type:** <change_type from Step 1>

   <contribution body text from Step 1>
   ```
3. Write the updated content back

**Update frontmatter:**
```bash
./.aitask-scripts/aitask_update.sh --batch <task_num> --contributor "<name>" --contributor-email "<email>" --issue "<issue_url>"
```

**Post notification comment on contribution issue:**
Use the contribution review script's comment posting:
```bash
./.aitask-scripts/aitask_contribution_review.sh post-comment <issue_number> "This contribution has been incorporated into existing task **t<task_num>** (<task_title>). The contributor will be credited via Co-authored-by when the task is implemented."
```

Note: Check if `post-comment` subcommand exists. If not, the skill can call the platform-specific comment function directly (the script sources platform backends).

**Commit:**
```bash
./ait git add aitasks/<task_file>
./ait git commit -m "ait: Update t<task_num> with contribution from issue #<N>"
```

**End workflow:** Display "Contribution from issue #<N> incorporated into existing task t<task_num>. No new task created."
```

### 2. Verify aitask_update.sh supports needed flags

Check that `--contributor`, `--contributor-email`, and `--issue` flags work together in a single `--batch` call. If they can't be combined, use separate calls.

### 3. Check comment posting mechanism

Look at `aitask_contribution_review.sh` to see what subcommands it supports. If `post-comment` doesn't exist, document the alternative approach (using `source_post_comment` function directly or adding the subcommand).

## Verification

1. Trace through the SKILL.md flow: contribution overlaps existing task → user selects "update existing" → task updated, issue comment posted, workflow ends
2. Verify `aitask_update.sh --batch <N> --contributor X --contributor-email Y --issue Z` works
3. Edge case: existing task already has a `contributor` field — check overwrite behavior
4. Edge case: existing task already has an `issue` field — check overwrite behavior

## Step 9: Post-Implementation

Archive child task. If all siblings done, archive parent t376.
