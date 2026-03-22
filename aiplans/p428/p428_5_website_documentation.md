---
Task: t428_5_website_documentation.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_1_*.md, aitasks/t428/t428_2_*.md, aitasks/t428/t428_4_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Website Documentation

## Overview

Add website docs for the new aitask-qa skill and update existing docs that reference the removed test-followup procedure.

## Steps

### 1. Create `website/content/docs/skills/aitask-qa.md`

Follow the pattern of `website/content/docs/skills/aitask-review.md`:
- Frontmatter with title, linkTitle, weight, description
- Overview: purpose, when to use
- Usage: `/aitask-qa [task_id]`, interactive vs direct
- Workflow steps (abbreviated)
- Profile keys: `qa_mode`, `qa_run_tests`, `qa_tier`
- Project config: `test_command`, `lint_command`
- Examples

### 2. Update `website/content/docs/skills/aitask-pick/_index.md`

- Find and remove/update references to Step 8b, test-followup
- Add note: "Test coverage analysis is now handled by the dedicated `/aitask-qa` skill."

### 3. Update `website/content/docs/skills/aitask-pick/execution-profiles.md`

- Remove `test_followup_task` row
- Add `qa_mode`, `qa_run_tests`, `qa_tier` rows

### 4. Document test_command/lint_command

Add section to `website/content/docs/skills/aitask-pick/build-verification.md` or create new page for test/lint configuration.

### 5. Search and update other docs

`grep -r "test.followup\|test_followup\|Step 8b" website/content/`

## Verification

1. `cd website && hugo build --gc --minify` — no errors
2. Check `website/public/docs/skills/aitask-qa/index.html` exists
3. No broken references to test-followup in built output

## Post-Implementation

Step 9 of task-workflow for archival.
