---
Task: t183_not_only_github.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The aitasks project added multi-platform support (GitHub, GitLab, Bitbucket) in scripts for issue import/update, platform detection, and the board UI. However, several documentation files still reference only "GitHub" where all three platforms are supported. This task updates those docs.

## Plan

### Step 1: Rename and rewrite `github-issues.md` → `issue-tracker.md`

**File:** `website/content/docs/workflows/github-issues.md`

- `git mv` to `website/content/docs/workflows/issue-tracker.md`
- Update frontmatter:
  - title: "Issue Tracker Development Workflow"
  - linkTitle: "Issue Tracker"
  - description: "Round-trip workflow between issue trackers (GitHub, GitLab, Bitbucket) and aitasks"
  - Add `aliases: ["/docs/workflows/github-issues/"]` to preserve old URLs
- Rewrite body to be platform-agnostic (replace "GitHub issues" with "issues from your tracker" etc.)

### Step 2: Update `docs/README.md` cross-reference (line 21)

Change link text, path, and description to match the renamed file.

### Step 3: Update `website/content/docs/commands/_index.md`

- Line 18: "GitHub/GitLab issues" → "GitHub/GitLab/Bitbucket issues"
- Line 19: same
- Line 34: `# Import GitHub issues` → `# Import issues from issue tracker`

### Step 4: Update `website/content/docs/commands/issue-integration.md`

- Line 23: "each GitHub label" → "each issue label"
- Line 26: "from GitHub labels" → "from issue labels"

### Step 5: Update `website/content/docs/development/task-format.md`

- Line 43: "Linked GitHub/GitLab issue" → "Linked GitHub/GitLab/Bitbucket issue"

### Step 6: Update `website/content/docs/skills/aitask-pick.md`

- Line 28: "linked GitHub issues" → "linked issues (GitHub/GitLab/Bitbucket)"
- Line 36: "the GitHub issue" → "the linked issue"

### Step 7: Update `website/content/docs/board/_index.md`

- Line 60: `"GH" in blue for GitHub issues` → `"GH" for GitHub, "GL" for GitLab, "BB" for Bitbucket`

### Step 8: Update `README.md`

- Line 7: "GitHub issue integration" → "GitHub/GitLab/Bitbucket issue integration"

## Files NOT changed (verified GitHub-only or already correct)

- `skills/aitask-reviewguide-import.md` — GitHub directory import is GitHub-only
- `.claude/skills/aitask-reviewguide-import/SKILL.md` — same
- `workflows/code-review.md` — "GitHub repositories" accurate for import skill
- `commands/setup-install.md` — "GitHub release" refers to where aitasks is hosted
- `installation/_index.md` — already documents all three platforms
- Archived files — historical records, not updated

## Verification

- Grep for remaining GitHub-only references and verify each is correct

## Final Implementation Notes
- **Actual work done:** Renamed `github-issues.md` to `issue-tracker.md` with Hugo alias for old URL. Updated 8 files total to replace GitHub-only references with multi-platform mentions (GitHub/GitLab/Bitbucket) where the underlying functionality supports all three platforms.
- **Deviations from plan:** None. All steps executed as planned.
- **Issues encountered:** None.
- **Key decisions:** Added `aliases: ["/docs/workflows/github-issues/"]` to the renamed file to preserve external links. Left `aitask-reviewguide-import` references as GitHub-only since that feature genuinely only supports GitHub directory/file import currently.
