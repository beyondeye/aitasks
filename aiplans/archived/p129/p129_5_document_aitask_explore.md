---
Task: t129_5_document_aitask_explore.md
Parent Task: aitasks/t129_dynamic_task_skill.md
Sibling Tasks: aitasks/t129/t129_6_*.md
Archived Sibling Plans: aiplans/archived/p129/p129_1_extract_shared_workflow.md, aiplans/archived/p129/p129_2_create_aitask_explore_skill.md, aiplans/archived/p129/p129_3_review_modes_infrastructure.md, aiplans/archived/p129/p129_4_create_aitask_review_skill.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Document aitask-explore (t129_5)

## Context

The task t129_5 was written when documentation lived inline in README.md. Since then, the project migrated to a Hugo/Docsy documentation website at `website/content/docs/`. The README now only links to the docs site.

**Current state of aitask-explore documentation:**
- `website/content/docs/skills/aitask-explore.md` — Already exists with solid content (workflow overview, key capabilities, folded tasks section)
- `website/content/docs/skills/_index.md` — Already lists `/aitask-explore` in the skills overview table
- `docs/README.md` — Already has the `/aitask-explore` entry in the documentation index

**What's missing:** An "Exploration-Driven Development" workflow guide in `website/content/docs/workflows/`. The existing workflows cover capturing ideas, GitHub issues, task decomposition, follow-up tasks, parallel development, terminal setup, and code review — but there's no exploration-first workflow.

## Files to Create/Modify

1. **Create** `website/content/docs/workflows/exploration-driven.md` — New workflow guide for exploration-driven development
2. **Modify** `docs/README.md` — Add the new workflow to the documentation index table

## Implementation Steps

### Step 1: Create exploration-driven workflow guide

Create `website/content/docs/workflows/exploration-driven.md` following the pattern from existing workflows (e.g., `capturing-ideas.md`, `code-review.md`):

- Hugo frontmatter with title, linkTitle, weight 75, description
- Motivation paragraph: explain when exploration-first is better than task-first
- Concrete walkthrough example
- Reference the 4 exploration modes
- Mention folded tasks feature
- Link back to skill reference page

### Step 2: Update docs/README.md

Add a row to the documentation index table for the new workflow guide after the "Code Review" row.

## Verification Steps

1. Check that the new workflow file has valid Hugo frontmatter
2. Verify links to skill reference pages use correct relative paths
3. Verify the docs/README.md table entry has correct paths
4. Cross-reference workflow content with actual SKILL.md steps

## Final Implementation Notes

- **Actual work done:** Created `website/content/docs/workflows/exploration-driven.md` (77 lines) as a new workflow guide. Added an entry to `docs/README.md` index table. The workflow guide covers: motivation for exploration-first development, 5 use cases, a concrete walkthrough example (investigating performance issues), the 4 exploration modes with a summary table, the folded tasks feature, and practical tips.
- **Deviations from plan:** The original task (t129_5) specified modifying `README.md` with inline documentation (TOC, integration table, /aitask-explore section, Typical Workflows subsection). However, the project migrated to a Hugo docs website since the task was written. The skill reference page (`website/content/docs/skills/aitask-explore.md`) already existed with good content. The actual gap was a workflow guide, which was created instead. This is a better fit for the current documentation architecture.
- **Issues encountered:** None. The existing workflow docs (`code-review.md`, `capturing-ideas.md`) provided clear patterns to follow.
- **Key decisions:** (1) Weight 75 for the new workflow page, placing it after Code Review (70). (2) Used a performance investigation scenario for the walkthrough since it demonstrates the iterative exploration loop well. (3) Kept the guide concise and action-oriented, linking to the skill reference page for detailed capability descriptions rather than duplicating content.
- **Notes for sibling tasks:** t129_6 (document aitask-review) should follow the same approach — the skill reference page likely already exists at `website/content/docs/skills/aitask-review.md`, and a Code Review workflow guide already exists at `website/content/docs/workflows/code-review.md`. Check what's actually missing before implementing.
