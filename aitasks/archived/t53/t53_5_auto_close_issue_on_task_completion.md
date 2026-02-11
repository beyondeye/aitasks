---
priority: medium
effort: low
depends: [t53_1, t53_6]
issue_type: feature
status: Done
labels: [scripting, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 16:19
updated_at: 2026-02-10 22:45
completed_at: 2026-02-10 22:45
---

## Context

This is child task 5 of t53 (import GitHub issues as tasks). This task updates the aitask-pick skill's post-implementation workflow (Step 9) to automatically update/close the associated GitHub issue when a task is archived.

It depends on:
- **t53_1** which adds the `issue` metadata field to task files
- **t53_6** which provides the `aitask_issue_update.sh` script that handles all GitHub issue interaction (commenting, closing, commit auto-detection, plan notes extraction)

The `issue` field stores a full URL (e.g., `https://github.com/owner/repo/issues/123`). The `aitask_issue_update.sh` script handles platform abstraction with extension points for GitLab/Bitbucket support later.

## Key Files to Modify

1. **`.claude/skills/aitask-pick/SKILL.md`** - Add issue update/close logic to Step 9

## Reference Files for Patterns

- `.claude/skills/aitask-pick/SKILL.md` - Current Step 9 workflow
- `aitask_issue_update.sh` - Script to call for issue updates (created by t53_6)
- The skill uses bash commands in code blocks that Claude Code executes during the workflow

## Implementation Plan

### Step 1: Add issue update/close sub-step to Step 9

In the SKILL.md file, add a new sub-step in Step 9 that runs AFTER file archival but BEFORE the final git commit. This applies to both child tasks and parent tasks.

The new sub-step should be inserted:
- For **child tasks**: After "Archive the child plan file" and before "Check if all children complete"
- For **parent tasks**: After "Archive the plan file" and before "Commit archived files to git"

### Step 2: Issue update/close logic (to add to SKILL.md)

Add this section to both child task and parent task workflows in Step 9:

```markdown
**Update/close associated issue (if linked):**

- Read the `issue` field from the task file's frontmatter (before or after archival - the field persists)
- If the `issue` field is present:
  - Use `AskUserQuestion`:
    - Question: "Task has a linked issue: <issue_url>. Update/close it?"
    - Header: "Issue update"
    - Options:
      - "Close with implementation notes" (description: "Post implementation notes + commits as comment and close the issue")
      - "Post comment only" (description: "Post implementation notes but leave issue open")
      - "Close without comment" (description: "Close the issue silently")
      - "Skip" (description: "Don't touch the issue")

  - If user selects "Close with implementation notes":
    ```bash
    ./aitask_issue_update.sh --close <task_num>
    ```

  - If "Post comment only":
    ```bash
    ./aitask_issue_update.sh <task_num>
    ```

  - If "Close without comment":
    ```bash
    ./aitask_issue_update.sh --close --no-comment <task_num>
    ```

  - If "Skip": skip

- If no `issue` field: skip silently
```

### Step 3: Update Notes section

Add a note to the Notes section at the bottom of SKILL.md:

```markdown
- When archiving a task with an `issue` field, the workflow will offer to update/close the associated issue using `aitask_issue_update.sh`. The script auto-detects commits from git history and includes "Final Implementation Notes" from the archived plan file.
```

## Verification Steps

1. Create a test task with an `issue` field pointing to a real GitHub issue (use a test repo)
2. Run `/aitask-pick` on the task and go through to Step 9
3. Verify the update/close prompt appears with the correct issue URL
4. Test "Close with implementation notes" - verify `aitask_issue_update.sh --close` is called
5. Test "Skip" - verify issue remains unchanged
6. Test with a task without an `issue` field - verify the step is skipped silently
