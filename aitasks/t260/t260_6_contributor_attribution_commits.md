---
priority: medium
effort: low
depends: [t260_5]
issue_type: feature
status: Ready
labels: [skills]
created_at: 2026-03-01 15:33
updated_at: 2026-03-01 15:33
---

## Context

This is child task 6 of the "Create aitasks from Pull Requests" feature (t260). When implementing a task that originated from a PR, the original contributor should be credited in the git commit history using `Co-authored-by` trailers.

**Why this task is needed:** External contributors deserve attribution even when their PR is not merged directly. The `Co-authored-by` trailer is the standard mechanism in open source for crediting contributors. GitHub and GitLab both recognize this trailer and display it in the commit UI, linking to the contributor's profile.

**Depends on:** t260_1 (needs `contributor` and `contributor_email` metadata fields and extraction functions)

## Key Files to Modify

1. **`.claude/skills/task-workflow/SKILL.md`** (~450 lines)
   - Modify Step 8 (User Review and Approval) commit instructions to include `Co-authored-by` trailer when task has contributor metadata

## Reference Files for Patterns

- **`.claude/skills/task-workflow/SKILL.md`** Step 8 — Current commit instructions (around line 288-304). Shows the code commit format:
  ```bash
  git add <changed_code_files>
  git commit -m "<issue_type>: <description> (t<task_id>)"
  ```
  This needs to be extended with Co-authored-by trailer.

- **`aiscripts/lib/task_utils.sh`** — `extract_contributor()` and `extract_contributor_email()` functions (added in t260_1)

## Implementation Plan

### Modify Step 8 in task-workflow/SKILL.md

In the "If 'Commit changes'" section (around line 288), add contributor attribution logic:

**Before the code commit command, add these instructions:**

```markdown
- **Contributor attribution check:** Before committing code changes, read the task file's frontmatter:
  - Extract `contributor` and `contributor_email` fields
  - Extract `pull_request` field
  - If both `contributor` and `contributor_email` are present, the commit message MUST include:
    1. A `Based on PR:` line referencing the original pull request
    2. A `Co-authored-by:` trailer crediting the contributor
  - The commit message format becomes:
    ```bash
    git commit -m "$(cat <<'EOF'
    <issue_type>: <description> (t<task_id>)

    Based on PR: <pull_request_url>

    Co-authored-by: <contributor> <<contributor_email>>
    EOF
    )"
    ```
  - Example:
    ```bash
    git commit -m "$(cat <<'EOF'
    feature: Add dark mode support (t42)

    Based on PR: https://github.com/owner/repo/pull/15

    Co-authored-by: octocat <12345+octocat@users.noreply.github.com>
    EOF
    )"
    ```
  - If only `contributor` is present but NOT `contributor_email`, skip the Co-authored-by trailer (it won't be recognized by the platform without a proper email)
  - If neither field is present, use the standard commit format without any contributor attribution
```

### Key Details

**Co-authored-by format requirements (GitHub/GitLab):**
- Must be: `Co-authored-by: Name <email>`
- Email MUST match an account on the platform for attribution to be linked
- The noreply email format `<id>+<username>@users.noreply.github.com` is preferred (privacy-safe, permanent even if username changes)
- For GitLab: `<id>+<username>@noreply.gitlab.com`
- The trailer must be at the end of the commit message, after a blank line
- Multiple trailers can appear (one per contributor)

**Why `Co-authored-by` instead of `--author`:**
- `--author` would change the commit author, misrepresenting who actually wrote the final code
- `Co-authored-by` correctly indicates the contributor inspired/contributed to the work without claiming they wrote the specific implementation
- Both GitHub and GitLab display Co-authored-by contributors in the commit UI

**Where the email comes from:**
- The `contributor_email` field is pre-computed during PR import (t260_3) by querying the platform API for the user's ID
- It's stored directly in the task metadata, so no API call is needed at commit time
- Format: `<userid>+<username>@users.noreply.github.com` (GitHub) or `<userid>+<username>@noreply.gitlab.com` (GitLab)

## Verification Steps

1. **Create a task with contributor metadata:**
   ```bash
   echo "Test contributor attribution" | ./aiscripts/aitask_create.sh --batch \
     --name "test_contributor" \
     --pull-request "https://github.com/owner/repo/pull/42" \
     --contributor "octocat" \
     --contributor-email "12345+octocat@users.noreply.github.com" \
     --desc-file - --commit
   ```

2. **Implement the task and commit:**
   - Make a code change
   - Follow the updated Step 8 workflow
   - Verify the commit message includes:
     ```
     feature: Test contributor attribution (t<N>)

     Based on PR: https://github.com/owner/repo/pull/42

     Co-authored-by: octocat <12345+octocat@users.noreply.github.com>
     ```

3. **Verify with `git log`:**
   ```bash
   git log -1 --format="%B"  # Should show full commit message with trailer
   ```

4. **Test task WITHOUT contributor metadata:**
   - Create a normal task (no PR metadata)
   - Verify commit message uses standard format without any Co-authored-by trailer
