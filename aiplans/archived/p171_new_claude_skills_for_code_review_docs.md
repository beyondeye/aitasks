---
Task: t171_new_claude_skills_for_code_review_docs.md
Worktree: (current directory)
Branch: main
Base branch: main
---

## Context

New Claude Code skills for code review and review guide management have been implemented but lack website documentation. Need to document `/aitask-review`, `/aitask-reviewguide-classify`, `/aitask-reviewguide-merge`, `/aitask-reviewguide-import` and add a code review workflow guide.

## Plan

### 1. Create 4 skill doc pages
- `website/content/docs/skills/aitask-review.md` (weight: 70)
- `website/content/docs/skills/aitask-reviewguide-classify.md` (weight: 80)
- `website/content/docs/skills/aitask-reviewguide-merge.md` (weight: 90)
- `website/content/docs/skills/aitask-reviewguide-import.md` (weight: 100)

### 2. Create workflow guide
- `website/content/docs/workflows/code-review.md` (weight: 70)

### 3. Update skills overview and docs map
- `website/content/docs/skills/_index.md`
- `docs/README.md`

## Final Implementation Notes

- **Actual work done:** Created 4 skill doc pages (aitask-review, aitask-reviewguide-classify, aitask-reviewguide-merge, aitask-reviewguide-import), 1 workflow guide (code-review), updated skills overview table, and updated docs/README.md map with 5 new entries. Added .reviewguidesignore documentation per user request.
- **Deviations from plan:** Added .reviewguidesignore documentation (not in original plan, user requested during review).
- **Issues encountered:** None.
- **Key decisions:** Followed existing skill doc patterns exactly (frontmatter, usage block, workflow overview, key capabilities). Used cross-references between all 4 review skills to show their relationships. Weight numbering continues from existing skills (70-100).

## Step 9 Reference

Post-implementation: archive task/plan, push.
