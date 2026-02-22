---
Task: t191_refactor_aitask_explore_area_selection.md
---

## Context

Task t191 enhances the `aitask-explore` skill's "Explore codebase area" option to offer file search (via `user-file-select`) as an alternative to free-text area description. Currently the option only asks for a free-text module/directory name. This follows the pattern established by t190 which integrated `user-file-select` into `aitask-explain`.

## Plan

### Modify `.claude/skills/aitask-explore/SKILL.md` — Step 1, "Explore codebase area" section (lines 68-74)

Replace the current single free-text follow-up with a two-step flow offering either file search or free-text description.

The exploration strategy and task defaults remain unchanged.

### Files to modify
- `.claude/skills/aitask-explore/SKILL.md` — lines 68-74 only (the "Explore codebase area" subsection)

### What stays unchanged
- All other Step 1 options (Investigate a problem, Scope an idea, Explore documentation, Other)
- Step 2 exploration loop, Step 2b related task discovery, Steps 3-5
- All other files

## Verification
1. Read modified SKILL.md and confirm the "Explore codebase area" section has both options
2. Confirm other options are untouched
3. Confirm user-file-select integration follows the same pattern as aitask-explain

## Final Implementation Notes
- **Actual work done:** Modified the "Explore codebase area" subsection in `.claude/skills/aitask-explore/SKILL.md` (lines 68-78) to replace the single free-text follow-up with a two-option AskUserQuestion ("Search for files" / "Describe the area"), with the file search path invoking `user-file-select` and the describe path preserving the original free-text behavior.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Kept the same integration pattern as aitask-explain (read and follow the skill file) for consistency.
