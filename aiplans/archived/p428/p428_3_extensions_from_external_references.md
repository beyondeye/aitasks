---
Task: t428_3_extensions_from_external_references.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_1_*.md, aitasks/t428/t428_2_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Extensions from External References

## Overview

Enhance the aitask-qa skill with advanced patterns: tiered testing modes, health score, verification gate, and regression test hints. Patterns drawn from gstack-qa, superpowers/verification-before-completion, and superpowers/test-driven-development.

## Steps

### 1. Add Tiered Testing Modes

In `.claude/skills/aitask-qa/SKILL.md`, add a tier selection step after Step 1 (task selection):

**Step 1b: Select QA Tier**
- Profile check: If `qa_tier` is set, use it directly
- Otherwise, AskUserQuestion: "Select QA analysis depth:"
  - Quick: Run existing tests + lint only
  - Standard (default): Full analysis + test plan generation
  - Exhaustive: Full analysis + edge cases + verification gate

Modify subsequent steps to check the tier:
- Quick: Skip Steps 2, 3, 5 (only run Step 4: test execution)
- Standard: Full workflow as-is
- Exhaustive: Full workflow + additional sub-steps in Step 4 and Step 5

### 2. Add Health Score

After Step 4 (test execution), compute and display a health score summary:

```
QA Health Score: XX/100
  Lint:      XX/100 (N issues)
  Tests:     XX/100 (N/M passed)
  Coverage:  XX/100 (N/M changed files have tests)
  Edge cases: XX/100 (agent assessment)
```

Scoring:
- Lint (20%): 100 minus deductions per issue (errors: -10, warnings: -5, info: -2, cap at 0)
- Tests (30%): pass_count / total_count * 100
- Coverage (30%): files_with_tests / changed_source_files * 100
- Edge cases (20%): agent assessment on 0-100 scale based on test plan analysis

### 3. Add Verification Gate (Exhaustive tier only)

In Step 4 for Exhaustive tier, after running tests:
- Re-run all tests fresh (not cached)
- Read full output and verify each test result
- Map each claim to its evidence:
  - "Tests pass" → test output showing 0 failures
  - "Lint clean" → linter output showing 0 errors
  - "Bug fixed" → test reproducing the original symptom passes
- Flag any unverified claims before proceeding

### 4. Add Regression Test Hints

In Step 5 (test plan proposal), when the target task has `issue_type: bug`:
- Add a "Regression Testing" category to the test plan
- Suggest red-green verification cycle:
  1. Write a test that reproduces the bug
  2. Verify test fails without the fix (revert changes, run test)
  3. Verify test passes with the fix (restore changes, run test)
- In Exhaustive tier: prompt user to actually perform the cycle during "Implement tests now" mode

### 5. Update `profiles.md`

Add `qa_tier` row to the schema table:
- `qa_tier` | string | no | `"quick"`, `"standard"` (default), `"exhaustive"` | aitask-qa Step 1b

## Verification

1. Test Quick tier: verify only tests run (no plan generation)
2. Test Standard tier: verify full workflow + health score
3. Test Exhaustive tier: verify edge cases + verification gate
4. Test with bug task: verify regression test hints appear
5. Verify health score format and calculations

## Post-Implementation

Step 9 of task-workflow for archival.

## Final Implementation Notes

- **Actual work done:** Refactored the monolithic SKILL.md (305 lines) into a concise orchestrator (118 lines) + 6 procedure files, following the task-workflow progressive disclosure pattern. Added all 4 planned extensions: tiered testing modes (Step 1c), health score (4d), verification gate (4e), and regression test hints (5a). Updated profiles.md with `qa_tier` key.
- **Deviations from plan:**
  - **Major refactor added:** Per user feedback, the skill was refactored into procedure files before adding features (not in original plan). This follows Claude platform best practices for skills approaching 500 lines.
  - **Step numbering:** Used "Step 1c" instead of "Step 1b" since 1b was already taken by Interactive Task Selection.
  - **Tier system redesign:** Per user feedback, replaced vague "tier gate" prose with an explicit `tier` context variable (`q`/`s`/`e`) and `[Tier: ...]` annotations on every step/sub-step heading. Each annotation explicitly lists which tier values activate it.
- **Issues encountered:** None.
- **Key decisions:**
  - Procedure files follow the task-workflow pattern: each has a context header, Input/Output section, and `---` separator before the procedure body.
  - The `[Tier: ...]` annotation convention is new to this skill — placed in heading text for maximum visibility.
  - Health score uses proportional weight redistribution when a component is N/A (e.g., no lint command).
- **Notes for sibling tasks:**
  - t428_5 (website docs): The skill now has 7 files in `.claude/skills/aitask-qa/` — documentation should reflect the refactored structure. New profile key `qa_tier` needs documenting.
  - t428_7 (TUI profile keys): `qa_tier` was added to `profiles.md` with values `"quick"`, `"standard"`, `"exhaustive"`. The TUI settings should support this as a string dropdown.
  - Multi-agent wrappers (created in t428_6) need NO changes — they delegate to SKILL.md which references procedure files on demand.
