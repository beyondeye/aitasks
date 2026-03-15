---
priority: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [aitask_contribute, website]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-12 22:50
updated_at: 2026-03-15 09:50
---

## Context

The `/aitask-contribution-review` skill currently has no website documentation page. Other skills like `/aitask-fold`, `/aitask-explore`, and `/aitask-contribute` all have dedicated pages under `website/content/docs/skills/`. This task creates the missing documentation and updates the contribution workflow page to reference it.

## Key Files to Modify

- **Create:** `website/content/docs/skills/aitask-contribution-review.md` — New skill documentation page
- **Modify:** `website/content/docs/workflows/contribute-and-manage.md` — Add contribution-review to the workflow

## Reference Files for Patterns

- `website/content/docs/skills/aitask-fold.md` — Pattern for skill documentation page (frontmatter, sections)
- `website/content/docs/skills/aitask-contribute.md` — Related skill page
- `website/content/docs/workflows/contribute-and-manage.md` — Current "Three Paths" lifecycle page
- `.claude/skills/aitask-contribution-review/SKILL.md` — Source of truth for the skill's workflow

## Implementation Plan

### Step 1: Create the skill documentation page

Create `website/content/docs/skills/aitask-contribution-review.md` with:
- Hugo frontmatter (title, linkTitle, weight, description) following the pattern of sibling pages
- Overview of what the skill does: analyze contribution issues, find related issues, check for overlapping tasks, import or merge
- Usage: `/aitask-contribution-review <issue_number>`
- Workflow summary (Steps 1-6b from SKILL.md, summarized for users)
- Key features: overlap detection (issues), overlap detection (existing tasks), fold, update existing
- Notes on platform support (GitHub, GitLab, Bitbucket)

### Step 2: Update the contribute-and-manage workflow page

In `website/content/docs/workflows/contribute-and-manage.md`:
- Rename "The Three Paths" → "The Four Paths" (or keep as "The Paths")
- Add a new subsection for `/aitask-contribution-review`:
  - **Who uses it:** Maintainers reviewing incoming contribution issues (created via `/aitask-contribute`)
  - **Flow:** `Contribution issue → /aitask-contribution-review → Analysis → Check overlaps → Import or fold or update existing`
  - Link to the new skill page
- Update the lifecycle diagram to include the review step between contribution issue creation and `ait issue-import`

## Verification Steps

1. Build the website: `cd website && hugo build --gc --minify`
2. Verify the new page renders correctly in the local dev server: `cd website && ./serve.sh`
3. Verify cross-links from the workflow page to the new skill page work
4. Check that the _index.md for skills lists the new page (it should auto-discover)
