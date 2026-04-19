---
Task: t583_9_meta_dogfood_aggregate_verification.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md .. t583_8_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_9 — Meta-Dogfood Aggregate Verification

## Context

Final child. Validates the whole manual-verification module by running the module on itself. Per `feedback_manual_verification_aggregate`, parent tasks with 2+ behavior-heavy siblings should have one aggregate manual-verification sibling rather than inline verification sections.

Depends on t583_1..t583_8 (entire module must ship first).

## Implementation

This child's deliverable IS its own task file (the content drives the dogfood). After the task file is authored per the description in `aitasks/t583/t583_9_*.md`, the implementation work consists of:

1. **Bootstrap check:** before picking this task, confirm the task file already has `issue_type: manual_verification`, `verifies: [t583_1, ..., t583_8]`, and the full `## Verification Checklist`. If missing (e.g., the task was created by a pre-module version of `aitask_create.sh`), migrate by calling `aitask_update.sh --batch <id> --set-verifies t583_1,t583_2,t583_3,t583_4,t583_5,t583_6,t583_7,t583_8` and `aitask_verification_parse.sh seed ...`. This is the "backfill" path.

2. **Run the module:** `/aitask-pick 583_9` → Step 3 Check 3 dispatches to `manual-verification.md` → iterate the checklist items interactively. Each item is an actionable in-person check listed in the task file.

3. **Fail → follow-ups:** any check that fails triggers a follow-up bug task (against the correct sibling via `verifies:`-driven origin disambiguation). These follow-ups are tracked as new work after t583 is closed.

4. **Archive:** after every item is terminal, `aitask_archive.sh` archives t583_9. Since t583_9 is the last sibling, its archival also archives the parent t583.

## Reference precedent

- `aitasks/t571/t571_7_manual_verification_structured_brainstorming.md` — the ancestor pattern this module formalizes.

## Verification

- Task file has `issue_type: manual_verification`, correct `verifies:`, and all checklist items.
- Running `/aitask-pick 583_9` invokes the module (proves Check 3 dispatch works).
- Every listed behavior is exercised at least once during the dogfood.

## Final Implementation Notes

_To be filled in during implementation._
