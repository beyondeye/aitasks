---
Task: t200_update_aitask_explain_skill_for_new_file_select_mechanism.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Update aitask-explain docs for user-file-select mechanism (t200)

## Context

The `user-file-select` skill was created to provide interactive file search (keyword, fuzzy name, functionality). It's already integrated into both the `.claude/skills/aitask-explain/SKILL.md` and `.claude/skills/aitask-explore/SKILL.md` skill files. The explore **website docs** already have a dedicated "File Selection" section, but the explain website docs do not. The explain workflow walkthrough also only demonstrates the "Enter paths directly" method.

## Changes

### 1. Add "File Selection" section to `website/content/docs/skills/aitask-explain.md`

Insert a new `## File Selection` section after the existing `## Key Capabilities` section (after line 34) and before `## Run Management` (line 36). Content describes the three file selection methods including the user-file-select search modes.

- [x] Completed

### 2. Add search tip to walkthrough in `website/content/docs/workflows/explain.md`

After the "Enter paths directly" instruction in the walkthrough, add a tip callout mentioning the search alternative with a link to the new File Selection section.

- [x] Completed

## Verification

1. `cd website && hugo build --gc --minify` — site builds without errors ✅
2. Verify the new "File Selection" section renders on the explain skill page ✅
3. Verify cross-reference links work (explain → explore, workflow → explain#file-selection) ✅

## Final Implementation Notes
- **Actual work done:** Added a "File Selection" section to the explain skill website docs and a tip callout to the explain workflow walkthrough, matching the pattern already established in the explore skill docs.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** The explain "File Selection" section differs slightly from the explore version because the explain skill has the additional "Use existing analysis" option and exposes search/enter-paths at the top level rather than nested under a specific exploration mode.
