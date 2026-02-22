---
priority: medium
effort: medium
depends: ['189']
issue_type: refactor
status: Implementing
labels: [aitasks, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 09:27
updated_at: 2026-02-22 13:11
boardcol: now
boardidx: 20
---

Refactor `aitask-explain` file selection (Step 1 in `.claude/skills/aitask-explain/SKILL.md`) to use the new `user-file-select` skill instead of the current simple free-text path input.

## Context
Task t91 implemented `aitask-explain` with intentionally simple file selection (direct path input via `AskUserQuestion` free text). Task t189 creates the `user-file-select` skill with fuzzy keyword/name/functionality search and ranked selection. This task integrates them.

## Current State (Step 1 in aitask-explain)
The current file selection in `.claude/skills/aitask-explain/SKILL.md` Step 1:
1. Checks for existing aiexplain runs (`aiexplains/*/files.txt`)
2. If existing runs exist: offers "Use existing analysis" or "Specify new files"
3. If "Specify new files" or no runs: asks user to type file/directory paths via free text ("Other")
4. Expands directories via `git ls-files`

## Required Changes

### Modify `.claude/skills/aitask-explain/SKILL.md` Step 1

Replace the "Specify new files" path (and the "no runs" case) with:

1. **Keep existing run reuse logic** — the "Use existing analysis" / "Refresh references" flow stays unchanged
2. **Replace "Specify new files"** — instead of asking for free text paths, invoke the `user-file-select` skill:
   - If aitask-explain was invoked with arguments (file paths), still use those directly (skip file selection)
   - If no arguments: offer three options via `AskUserQuestion`:
     - "Use existing analysis" (only if runs exist)
     - "Search for files" (description: "Find files by keywords, names, or functionality")
     - "Enter paths directly" (description: "Type file/directory paths manually")
   - If "Search for files": read and follow `.claude/skills/user-file-select/SKILL.md` to get file paths, then return to aitask-explain's "Proceed with files" section
   - If "Enter paths directly": keep current free-text behavior as fallback
3. **Remove the Note** at the top of Step 1 that says "File selection is kept simple here..." — this is no longer applicable

### Files to Modify
- `.claude/skills/aitask-explain/SKILL.md` — Step 1 only, rest of the workflow unchanged

### Reference Files
- `.claude/skills/user-file-select/SKILL.md` — the skill to integrate (created by t189)
- `.claude/skills/aitask-explain/SKILL.md` — current implementation (created by t91)

## Verification
1. Test `/aitask-explain` with no arguments — should offer search option
2. Test `/aitask-explain aiscripts/lib/task_utils.sh` — should still work directly (bypass file selection)
3. Test "Search for files" path — should invoke user-file-select and return selected files to aitask-explain
4. Test "Enter paths directly" fallback — should work as before
5. Test existing run reuse — should still work unchanged
