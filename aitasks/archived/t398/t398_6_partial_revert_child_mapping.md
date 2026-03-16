---
priority: medium
effort: medium
depends: [t398_5]
issue_type: feature
status: Done
labels: [aitask_revert]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-16 18:32
updated_at: 2026-03-16 19:10
completed_at: 2026-03-16 19:10
---

When a partial revert is selected for a parent task that has children, map the areas/files selected for revert back to the specific child tasks that originated them. This enables reverting by child task granularity rather than by directory area alone.

## Context
Currently, the partial revert flow in the aitask-revert skill (Step 3b) presents areas grouped by directory from `--task-areas`. The user selects which areas to revert. However, for parent tasks with children, the `--task-commits` output already tags each commit with its originating child task ID (e.g., `COMMIT|...|50_1`). This information is not surfaced during the partial revert area selection.

For parent tasks with children, a more natural revert granularity is "revert child task X's changes" rather than "revert directory Y". This task adds that mapping.

## Key Files to Modify
- `.claude/skills/aitask-revert/SKILL.md` — Update Step 2 (analysis display) and Step 3b (partial revert) to show per-child breakdown and allow child-level selection
- `.aitask-scripts/aitask_revert_analyze.sh` — Potentially add a `--task-children-areas <id>` subcommand that groups areas by child task ID

## Reference Files for Patterns
- `.aitask-scripts/aitask_revert_analyze.sh` — existing `--task-areas` and `--task-commits` implementations; commits already carry child task IDs in the output
- `.claude/skills/aitask-revert/SKILL.md:127-150` — Step 2 already shows per-child commit breakdown for parent tasks
- `.claude/skills/aitask-revert/SKILL.md:189-230` — Step 3b partial revert area selection

## Implementation Plan

### 1. Enhance analysis display for parent tasks (Step 2)
When displaying the analysis summary for a parent task with children, show a per-child area breakdown:
```
### Per-Child Breakdown
- t<id>_1 (<name>): <N> commits, areas: src/, lib/
- t<id>_2 (<name>): <N> commits, areas: tests/, docs/
```

### 2. Update Step 3b partial revert for parent tasks with children
When the target task is a parent with children:
- Present child tasks as the primary selection unit (instead of or in addition to areas)
- Use `AskUserQuestion` with `multiSelect: true` to let the user select which child tasks to revert
- After child selection, cross-reference with areas to show a confirmation summary
- Map the selected children's commits to the revert instructions

### 3. Update revert task template
The generated revert task description for partial reverts of parent tasks should:
- List which child tasks are being reverted vs kept
- Include per-child commit lists
- Include disposition instructions that reference the specific child task files

### 4. Handle edge cases
- Mixed commits: some commits may touch areas from multiple children
- Parent-level commits (tagged with parent ID, not child ID): present separately
- Standalone tasks (no children): fall back to current area-based selection

## Verification Steps
- Test with a known parent task that has multiple children with distinct areas
- Verify child-level selection produces correct revert task descriptions
- Verify standalone tasks still use area-based selection (no regression)
- Verify mixed commits (touching multiple children's areas) are handled correctly
