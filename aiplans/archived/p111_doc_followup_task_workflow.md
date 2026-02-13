---
Task: t111_doc_followup_task_workflow.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t111 asks to document the workflow of creating follow-up tasks during or after implementing a task via `/aitask-pick`. The README.md already has a "Typical Workflows" section with several subsections. We need to add a new subsection there.

## Plan

### 1. Add "Creating Follow-Up Tasks During Implementation" subsection to README.md

**File:** `README.md` (after the "Monitoring While Implementing" subsection)

Add a new subsection under "Typical Workflows" covering:

- Context: When working via `/aitask-pick`, Claude has full implementation context
- During implementation: User asks Claude to create follow-up tasks
- After implementation: During review step, realize follow-up work is needed
- Key advantages over standalone `ait create`

### 2. Update Table of Contents

Add the new subsection link under the "Typical Workflows" ToC entries.

## Verification

- [x] ToC link matches the heading anchor
- [x] Content follows the same style as other Typical Workflows subsections

## Final Implementation Notes
- **Actual work done:** Added a new "Creating Follow-Up Tasks During Implementation" subsection to the Typical Workflows section in README.md, plus updated the Table of Contents. The subsection covers during-implementation and after-implementation scenarios, with example prompts and key advantages.
- **Deviations from plan:** None — straightforward documentation addition.
- **Issues encountered:** None.
- **Key decisions:** Placed the new subsection at the end of Typical Workflows (after "Monitoring While Implementing") as it's a natural continuation of the implementation workflow.
