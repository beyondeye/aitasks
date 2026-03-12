---
Task: t376_4_website_docs_contribution_review.md
Parent Task: aitasks/t376_check_for_existing_tasks_in_aitaskcontribute.md
Sibling Tasks: aitasks/t376/t376_1_*.md, aitasks/t376/t376_2_*.md, aitasks/t376/t376_3_*.md
Archived Sibling Plans: aiplans/archived/p376/p376_1_*.md, aiplans/archived/p376/p376_2_*.md, aiplans/archived/p376/p376_3_*.md
Worktree: (none - current branch)
Branch: (current branch)
Base branch: main
---

## Goal

Create website documentation for the `/aitask-contribution-review` skill and update the contribution workflow page.

## Steps

### 1. Create `website/content/docs/skills/aitask-contribution-review.md`

Follow the pattern of `website/content/docs/skills/aitask-fold.md`. Include:

**Frontmatter:**
```yaml
---
title: "/aitask-contribution-review"
linkTitle: "Contribution Review"
weight: 48
description: "Analyze contribution issues, find related issues and tasks, and import as grouped or single task"
---
```

**Content sections:**
- **Overview:** What the skill does — analyzes contribution issues created via `/aitask-contribute`, finds related issues and overlapping tasks, offers merge/fold/update options
- **Usage:** `/aitask-contribution-review <issue_number>`
- **Workflow:** Summary of Steps 1-6b (from SKILL.md):
  1. Fetch and validate contribution issue (metadata check)
  2. Find related contribution issues (fingerprint + linked refs)
  3. Fetch related issue details
  4. AI analysis of code modifications
  5. Present merge proposal
  5b. Check for overlapping existing tasks (fold or update)
  6. Execute import (or update existing)
- **Key Features:**
  - Issue overlap detection (fingerprint-based)
  - Existing task overlap detection (AI semantic matching)
  - Fold existing tasks into imported task
  - Update existing tasks with contribution content
  - Multi-platform support (GitHub, GitLab, Bitbucket)
- **Related Skills:** Link to `/aitask-contribute`, `/aitask-fold`, `/aitask-explore`

### 2. Update `website/content/docs/workflows/contribute-and-manage.md`

**Changes:**
- Update "The Three Paths" → "The Paths" or "Four Paths"
- Add new subsection after "Issue to Task" for contribution review:
  ```markdown
  ### Review Contributions — `/aitask-contribution-review`

  Analyze a contribution issue in depth: find related contributions, check for overlapping existing tasks, and import as a single or merged task — or update an existing task directly.

  **Who uses it:** Maintainers reviewing contribution issues.

  **Flow:**
  ```
  Contribution issue → /aitask-contribution-review → Find overlaps (issues + tasks)
      → Import/Merge/Fold/Update → Task ready for implementation
  ```

  See the [Contribution Review skill](../../skills/aitask-contribution-review/) for full details.
  ```
- Update lifecycle diagram to show the review step

## Verification

1. `cd website && hugo build --gc --minify` — should succeed
2. `cd website && ./serve.sh` — verify new page renders, cross-links work
3. Check `_index.md` doesn't need manual update (Hugo auto-discovers pages)

## Step 9: Post-Implementation

Archive child task. If all siblings done, archive parent t376.
