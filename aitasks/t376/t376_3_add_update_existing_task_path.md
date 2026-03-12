---
priority: medium
effort: medium
depends: [376_2]
issue_type: feature
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-12 22:48
updated_at: 2026-03-12 22:48
---

## Context

When `/aitask-contribution-review` detects that a contribution overlaps an existing task (Step 5b, added by sibling t376_2), it offers three options. This task implements the "Update existing task instead" path — where instead of importing a new task and folding, the user updates the existing task to incorporate the contribution's content and metadata directly.

This is the alternative to the fold path: no new task is created. The existing task gains the contribution's details and the contributor gets proper attribution when the task is eventually implemented.

## Key Files to Modify

- **Modify:** `.claude/skills/aitask-contribution-review/SKILL.md` — Add Step 6b for the "update existing task" branch

## Reference Files for Patterns

- `.aitask-scripts/aitask_update.sh` — Supports `--contributor`, `--contributor-email`, `--issue` flags
- `.aitask-scripts/aitask_contribution_review.sh` — Has `source_post_comment` function for posting comments on issues
- `.claude/skills/aitask-contribution-review/SKILL.md` — Step 1 shows where contribution metadata is already parsed

## Implementation Plan

### Step 1: Add Step 6b to SKILL.md

When user selects "Update existing task instead" in Step 5b:

```markdown
### Step 6b: Update Existing Task with Contribution (Alternative)

This step is reached when the user chose "Update existing task instead" in Step 5b.

**Select target task:** If multiple overlapping tasks were found, ask the user which one to update (AskUserQuestion with the overlapping tasks as options).

**Append contribution content to the existing task:**
1. Read the existing task file
2. Append a new section at the end of the body:
   ```markdown
   ## Contribution from <contributor_name> (Issue #<N>)
   
   **Areas:** <areas>
   **Files:** <file_paths>
   **Change type:** <change_type>
   
   <contribution description/body from Step 1>
   ```
3. Write the updated content back to the task file

**Update task frontmatter:**
```bash
./.aitask-scripts/aitask_update.sh --batch <task_num> --contributor "<name>" --contributor-email "<email>" --issue "<issue_url>"
```

**Post notification on the contribution issue:**
```bash
./.aitask-scripts/aitask_contribution_review.sh post-comment <issue_number> "This contribution has been incorporated into existing task **t<task_num>** (<task_title>). The contributor will be credited via Co-authored-by when the task is implemented."
```

Note: If `post-comment` subcommand doesn't exist yet, use the platform-specific comment posting directly. Check what subcommands the script supports.

**Commit changes:**
```bash
./ait git add aitasks/<task_file>
./ait git commit -m "ait: Update t<task_num> with contribution from issue #<N>"
```

**End workflow:** Display "Contribution from issue #<N> incorporated into existing task t<task_num>. No new task created."
```

## Verification Steps

1. Verify the `aitask_update.sh` flags (`--contributor`, `--contributor-email`, `--issue`) work correctly
2. Verify comment posting mechanism exists (check `aitask_contribution_review.sh` for `post-comment` or equivalent)
3. Trace through the flow: contribution with overlapping task → user selects "update existing" → task updated, no new task created, issue comment posted
4. Edge case: existing task already has a `contributor` field — verify `aitask_update.sh` handles overwrite or append correctly
