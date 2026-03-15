---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [testing]
created_at: 2026-03-15 09:19
updated_at: 2026-03-15 09:19
---

## Context

Task t376_2 extracted duplicated task folding logic into two shared procedures:
- `.claude/skills/task-workflow/task-fold-content.md` — Content incorporation (structured `## Merged from t<N>` headers)
- `.claude/skills/task-workflow/task-fold-marking.md` — Fold marking (set folded_tasks, handle transitive, update statuses)

These procedures are referenced by 4 skills: aitask-fold, aitask-explore, aitask-pr-import, aitask-contribution-review.

This task tests the fold procedures end-to-end and verifies the bug fixes (structured merge format + transitive handling) applied to aitask-explore and aitask-pr-import.

## Test Ideas

### 1. Structured Merge Format Verification
- Create 2-3 test tasks with distinct descriptions
- Run `/aitask-fold` on them and verify the primary task's description has:
  - Primary description unchanged at top
  - `## Merged from t<N>: <task_name>` header for each folded task
  - `## Folded Tasks` reference section at the end
  - Full description body of each folded task under its header

### 2. Transitive Fold Handling
- Create task A, fold task B into A (A now has `folded_tasks: [B]`)
- Then fold A into task C
- Verify C has `folded_tasks: [A, B]`
- Verify B's `folded_into` was updated to point to C (not still pointing to A)

### 3. aitask_update.sh Flag Verification
- Test `--folded-tasks` with comma-separated IDs (e.g., `--folded-tasks "12,15"`)
- Test `--status Folded --folded-into <N>` together
- Test appending to existing `folded_tasks` (merge, not replace)

### 4. Contribution-Review Integration (Manual Trace)
- Read the updated `aitask-contribution-review/SKILL.md` and trace through:
  - No overlap case: Step 5b returns empty → Step 6 runs normally
  - Fold case: Step 5b returns tasks → Step 6 imports + runs fold procedures
  - Ignore case: Step 5b returns tasks but user says "Ignore" → Step 6 runs normally
  - Update existing case: redirects to Step 6b (placeholder for t376_3)

## Key Files
- `.claude/skills/task-workflow/task-fold-content.md`
- `.claude/skills/task-workflow/task-fold-marking.md`
- `.claude/skills/aitask-fold/SKILL.md`
- `.claude/skills/aitask-explore/SKILL.md`
- `.claude/skills/aitask-pr-import/SKILL.md`
- `.claude/skills/aitask-contribution-review/SKILL.md`
- `.aitask-scripts/aitask_update.sh`
