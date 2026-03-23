---
priority: medium
effort: medium
depends: [t428_1, t428_2, t428_4]
issue_type: documentation
status: Implementing
labels: [testing, qa, documentation]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-22 11:23
updated_at: 2026-03-23 19:31
---

## Context

Add website documentation for the new aitask-qa skill and update existing docs that reference the removed test-followup-task procedure. Also document the new `test_command` and `lint_command` project config keys.

## Key Files to Create/Modify

- **Create: `website/content/docs/skills/aitask-qa.md`** — New skill documentation page
- **Modify: `website/content/docs/skills/aitask-pick/_index.md`** — Remove/update Step 8b / test-followup references, add reference to aitask-qa
- **Modify: `website/content/docs/skills/aitask-pick/execution-profiles.md`** — Remove `test_followup_task` key, add `qa_mode`, `qa_run_tests`, `qa_tier` keys
- **Modify or create: `website/content/docs/skills/aitask-pick/build-verification.md`** or new page — Document `test_command`/`lint_command`
- **Any other docs** referencing test-followup: search and update

## Implementation Steps

### 1. Create new skill page: `website/content/docs/skills/aitask-qa.md`

Follow the pattern of `website/content/docs/skills/aitask-review.md`:

```yaml
---
title: "aitask-qa"
linkTitle: "aitask-qa"
weight: <appropriate weight>
description: "Run QA analysis on any task: discover tests, run them, identify gaps, and create follow-up test tasks."
---
```

Content should cover:
- Overview and purpose
- Usage: `/aitask-qa [task_id]` — optional argument, interactive selection from recently archived tasks
- Workflow steps (abbreviated version of SKILL.md)
- Profile configuration keys: `qa_mode`, `qa_run_tests`, `qa_tier`
- Project configuration: `test_command`, `lint_command`
- Examples

### 2. Update aitask-pick docs

In `website/content/docs/skills/aitask-pick/_index.md`:
- Find references to Step 8b, test-followup, or test follow-up
- Replace with reference to `/aitask-qa` as the dedicated testing skill
- Add a note: "Test coverage analysis has been moved to the standalone `/aitask-qa` skill."

### 3. Update execution profiles docs

In `website/content/docs/skills/aitask-pick/execution-profiles.md`:
- Remove `test_followup_task` row from the profile keys table
- Add new rows:
  - `qa_mode`: `"ask"` | `"create_task"` | `"implement"` | `"plan_only"` — used by aitask-qa Step 5
  - `qa_run_tests`: `true` | `false` — used by aitask-qa Step 4
  - `qa_tier`: `"quick"` | `"standard"` | `"exhaustive"` — used by aitask-qa (extensions, t428_3)

### 4. Document test_command/lint_command

Either add to `build-verification.md` or create a new page. Document:
- What these keys do (distinct from `verify_build`)
- Examples per project type
- How aitask-qa uses them
- Auto-detection fallback when keys are not configured

### 5. Search for other docs referencing test-followup

```bash
grep -r "test.followup\|test_followup\|Step 8b" website/content/
```
Update any found references.

## Reference Files

- `website/content/docs/skills/aitask-review.md` — Pattern for new skill page
- `website/content/docs/skills/aitask-pick/_index.md` — Docs to update
- `website/content/docs/skills/aitask-pick/execution-profiles.md` — Profile docs to update
- `website/content/docs/skills/aitask-pick/build-verification.md` — Related config docs
- `.claude/skills/aitask-qa/SKILL.md` — Source of truth for skill docs

## Verification Steps

1. Build website: `cd website && hugo build --gc --minify` — verify no errors
2. Verify new page renders: check `website/public/docs/skills/aitask-qa/index.html` exists
3. Verify no broken references: search for "test-followup" in built output
4. Run local dev server: `cd website && ./serve.sh` and visually verify pages
