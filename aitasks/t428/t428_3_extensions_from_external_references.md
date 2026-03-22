---
priority: medium
effort: high
depends: [428_1]
issue_type: feature
status: Ready
labels: [testing, qa]
created_at: 2026-03-22 11:22
updated_at: 2026-03-22 11:22
---

## Context

Enhance the aitask-qa skill (t428_1) with advanced patterns from external QA frameworks: gstack-qa (tiered testing, health score), superpowers/verification-before-completion (verification gate), and superpowers/test-driven-development (regression test hints with red-green verification).

## Key Files to Modify

- **`.claude/skills/aitask-qa/SKILL.md`** — Add tiered modes, health scoring, verification gate, regression hints
- **`.claude/skills/task-workflow/profiles.md`** — Add `qa_tier` profile key

## Extensions to Implement

### 1. Tiered Testing Modes (from gstack-qa)
Add a `qa_tier` profile key and corresponding AskUserQuestion:
- **Quick**: Run existing tests only + lint via `lint_command` on changed files. Minimal output.
- **Standard** (default): + test gap analysis + test plan generation with categorized proposals
- **Exhaustive**: + edge case brainstorming + regression test suggestions + verification gate

The tier controls which steps of the skill are executed:
- Quick: Steps 3-4 only (discovery + execution), then skip to Step 7
- Standard: Steps 2-6 (full workflow)
- Exhaustive: Steps 2-6 + additional sub-steps for edge cases and verification

### 2. Health Score (from gstack-qa)
After test execution (Step 4), compute and display a health score:
- Lint results: 20% weight (0 issues = 100%, deductions per severity)
- Test pass rate: 30% weight (all pass = 100%)
- Test coverage of changed files: 30% weight (% of changed source files with corresponding tests)
- Edge case coverage: 20% weight (agent assessment based on test plan)
- Framework-agnostic: uses `test_command` / `lint_command` from project_config

Display format:
```
QA Health Score: 78/100
  Lint: 95/100 (1 warning)
  Tests: 100/100 (12/12 passed)
  Coverage: 60/100 (3/5 changed files have tests)
  Edge cases: 50/100 (basic coverage, missing error paths)
```

### 3. Verification Gate (from superpowers/verification-before-completion)
In Exhaustive tier, after test execution:
- Before claiming "tests pass": run all tests fresh, read full output, verify zero failures
- Map each test assertion to its verification evidence
- Flag any unverified claims (uses "should", "probably", etc.)
- Require explicit evidence for each test result claim

### 4. Regression Test Hints (from superpowers/test-driven-development)
When analyzing a bug fix task (`issue_type: bug`):
- Suggest red-green verification cycle: write test → verify fails without fix → verify passes with fix
- Include this as a specific recommendation in the test plan proposal
- In Exhaustive tier: prompt user to actually perform the red-green cycle during "Implement tests now" mode

## Reference Files for Patterns

- External references (already fetched and analyzed in parent task planning):
  - gstack-qa: Tiered testing (Quick/Standard/Exhaustive), health score rubric, diff-aware mode
  - gstack-qa-only: Report-only mode, evidence requirements
  - superpowers/verification-before-completion: 5-step verification gate, evidence-before-claims table
  - superpowers/test-driven-development: Red-green-refactor, regression test verification
- `.claude/skills/aitask-qa/SKILL.md` — Base skill to extend (created in t428_1)
- `.claude/skills/task-workflow/profiles.md` — Profile schema to update

## Verification Steps

1. Test Quick tier: `/aitask-qa <task_id>` with `qa_tier: quick` in profile — should only run existing tests
2. Test Standard tier: verify full workflow including test plan generation
3. Test Exhaustive tier: verify edge case brainstorming and verification gate
4. Test with a `bug` issue_type task: verify regression test hints appear
5. Verify health score displays correctly with various test results
