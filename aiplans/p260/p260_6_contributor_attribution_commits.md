---
Task: t260_6_contributor_attribution_commits.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md through t260_7_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Contributor Attribution in Commits (t260_6)

## Overview

Modify the task-workflow skill's Step 8 (commit instructions) to include `Co-authored-by` trailers when implementing tasks that originated from external PRs.

## Steps

### 1. Modify `.claude/skills/task-workflow/SKILL.md` Step 8

In the "If 'Commit changes'" section (around line 288), add contributor attribution logic **before** the code commit command.

**Add this block:**

```markdown
- **Contributor attribution check:** Before committing code changes, check the task file's frontmatter for `contributor` and `contributor_email` fields, and the `pull_request` field:
  - If both `contributor` and `contributor_email` are present, the code commit message MUST include:
    1. A blank line after the first line
    2. A `Based on PR:` line referencing the original pull request URL
    3. A blank line
    4. A `Co-authored-by:` trailer crediting the contributor
  - The commit format:
    ```bash
    git commit -m "$(cat <<'EOF'
    <issue_type>: <description> (t<task_id>)

    Based on PR: <pull_request_url>

    Co-authored-by: <contributor> <<contributor_email>>
    EOF
    )"
    ```
  - If only `contributor` is present without `contributor_email`, skip the trailer (platforms require email for attribution linking)
  - If neither field is present, use the standard single-line commit format
```

### 2. Update the commit message example

Change the existing commit example in Step 8 to show both formats:

**Standard (no contributor):**
```bash
git commit -m "<issue_type>: <description> (t<task_id>)"
```

**With contributor attribution:**
```bash
git commit -m "$(cat <<'EOF'
feature: Add dark mode support (t42)

Based on PR: https://github.com/owner/repo/pull/15

Co-authored-by: octocat <12345+octocat@users.noreply.github.com>
EOF
)"
```

## Key Details

- `Co-authored-by` is preferred over `--author` — the contributor inspired the work but the current implementer wrote this specific code
- Email format: `<userid>+<username>@users.noreply.github.com` (GitHub) or `<userid>+<username>@noreply.gitlab.com` (GitLab)
- The `contributor_email` is pre-computed during PR import and stored in task metadata — no API call needed at commit time
- Both GitHub and GitLab display Co-authored-by contributors in the commit UI and count them as contributions

## Verification

1. Create task with contributor metadata, implement, and commit
2. `git log -1 --format="%B"` — verify Co-authored-by trailer
3. Create normal task (no PR metadata), implement, commit — verify no trailer
4. Push to GitHub/GitLab and verify contributor shows in commit UI

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_6`
