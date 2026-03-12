---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [testing]
created_at: 2026-03-12 23:31
updated_at: 2026-03-12 23:31
---

## Context

Task t376_1 extracted the "Related Task Discovery" logic from aitask-explore (Step 2b) and aitask-fold (Step 1) into a shared procedure at `.claude/skills/task-workflow/related-task-discovery.md`. Both calling skills now reference this shared procedure instead of inlining the logic.

## What Was Implemented

- **Created:** `.claude/skills/task-workflow/related-task-discovery.md` — Parameterized 5-step procedure (list, filter, assess relevance, present, return)
- **Modified:** `.claude/skills/aitask-explore/SKILL.md` — Step 2b replaced with reference to shared procedure (ai_filtered mode, min_eligible=1)
- **Modified:** `.claude/skills/aitask-fold/SKILL.md` — Step 1 replaced with reference to shared procedure (all mode, min_eligible=2)

No code files were modified — this is a skill documentation refactor only.

## Test Ideas

Since these are skill definition files (markdown instructions for the AI agent), traditional unit tests don't apply. However, the following functional verification approaches should be considered:

1. **Skill execution smoke test (aitask-explore):** Run `/aitask-explore`, proceed through exploration, select "Create a task", and verify that Step 2b correctly invokes the shared procedure — lists pending tasks, filters them, applies AI relevance matching, and presents the AskUserQuestion with multiSelect.

2. **Skill execution smoke test (aitask-fold):** Run `/aitask-fold` without arguments and verify that Step 1 correctly invokes the shared procedure — lists all eligible tasks (not AI-filtered), enforces min_eligible=2, and presents pagination.

3. **Parameter correctness verification:** Read the shared procedure and verify each caller passes the correct parameters:
   - aitask-explore: matching_context=exploration findings, purpose_text includes "folded in and deleted", min_eligible=1, selection_mode=ai_filtered
   - aitask-fold: matching_context not used, purpose_text includes "minimum 2", min_eligible=2, selection_mode=all

4. **Edge case: fewer than min_eligible tasks:** Test with 0 and 1 eligible tasks for both callers to verify appropriate user messaging.

5. **Pagination consistency:** Verify both callers get pagination (page_size=3) when there are >3 eligible tasks, which was previously only in fold.

## Existing Test Patterns

Tests in this project are bash scripts in `tests/` that use `assert_eq`/`assert_contains` helpers. However, skill definition files are not typically tested via bash scripts — they are verified by manual execution of the skill workflow.
