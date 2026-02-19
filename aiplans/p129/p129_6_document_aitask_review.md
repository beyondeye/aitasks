---
Task: t129_6_document_aitask_review.md
Parent Task: aitasks/t129_dynamic_task_skill.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Document aitask-review (t129_6)

## Context

The task t129_6 was written when documentation lived inline in README.md. Since then, the project migrated to a Hugo/Docsy documentation website at `website/content/docs/`. The README now only links to the docs site.

**Current state of aitask-review documentation (already exists):**

- `website/content/docs/skills/aitask-review.md` — Skill reference page with workflow overview (6 steps), key capabilities, review guides section, companion skill links
- `website/content/docs/skills/aitask-reviewguide-classify.md` — Full skill reference
- `website/content/docs/skills/aitask-reviewguide-merge.md` — Full skill reference
- `website/content/docs/skills/aitask-reviewguide-import.md` — Full skill reference
- `website/content/docs/workflows/code-review.md` — Workflow guide with review cycle, managing guides, when to review
- `website/content/docs/development/review-guide-format.md` — Technical docs on file format, vocabulary files, environment detection algorithm, similarity scoring
- `website/content/docs/skills/_index.md` — Lists `/aitask-review` and all companion skills
- `docs/README.md` — Lists all review-related docs in the index table

**What's missing:** The `code-review.md` workflow guide is notably thin compared to other workflow guides (37 lines vs. 77 for `exploration-driven.md`). It lacks:
1. A **concrete walkthrough example** showing a full review session step by step (like `exploration-driven.md` has "Walkthrough: Investigating a Performance Issue")
2. **Practical tips** section (like `exploration-driven.md` has)

## Files to Modify

1. **Modify** `website/content/docs/workflows/code-review.md` — Add a concrete walkthrough and tips section

## Implementation Steps

### Step 1: Add walkthrough section to code-review.md

Insert a "Walkthrough: Reviewing a Shell Script Module" section after "The Review Cycle" section and before "Managing Review Guides". The walkthrough demonstrates a concrete review session:

1. Launch `/aitask-review`
2. Select "Specific paths" targeting `aiscripts/`
3. Auto-detection finds bash/shell environment, ranks shell-specific guides first
4. Select "Shell Scripting" and "Error Handling" guides
5. Claude reviews the code, finds 4 issues (variable quoting, missing error check, broad trap, hardcoded path)
6. User selects 3 findings to address
7. Creates a single task and continues to implementation

### Step 2: Add tips section

Add a "Tips" section at the end of `code-review.md` with practical advice:
- Start with one or two guides per review session for focus
- Use "Recent changes" to review before committing (post-implementation quality check)
- Create project-specific guides via `/aitask-reviewguide-import` for team conventions
- Use the `review_default_modes` profile key for frequently-used guide combinations

## Verification Steps

1. Verify markdown headings are correctly nested within existing structure
2. Verify the walkthrough references accurate workflow steps from the SKILL.md
3. Verify the tips reference real profile keys and skill names
4. Check that no existing content was accidentally removed

## Final Implementation Notes
- **Actual work done:** Added a "Walkthrough: Reviewing a Shell Script Module" section (~43 lines) and a "Tips" section (~5 lines) to `website/content/docs/workflows/code-review.md`. The walkthrough demonstrates a complete review session: launching the skill, target selection, auto-detection of shell environment, guide selection, findings review (with severity levels), selective finding choice, task creation, and handoff to implementation. The tips cover focused reviews, post-implementation review, project-specific guides, and profile configuration.
- **Deviations from plan:** The original task (t129_6) specified modifying `README.md` with inline documentation (TOC, integration table, /aitask-review section, Code Review Workflow subsection). However, the project migrated to a Hugo docs website since the task was written. All the core documentation (skill reference pages, workflow guide, technical format docs) already existed comprehensively. The actual gap was a concrete walkthrough example and tips section in the workflow guide, which was added instead. This follows the same adaptation pattern as sibling t129_5.
- **Issues encountered:** None. The existing workflow docs provided clear patterns to follow.
- **Key decisions:** (1) Used a shell scripting review scenario for the walkthrough since it demonstrates environment auto-detection clearly and uses a real guide from the seed templates. (2) Kept the walkthrough concise (4 numbered steps) matching the exploration-driven.md pattern. (3) Tips section kept to 4 bullets — practical and non-obvious advice rather than restating documentation.
