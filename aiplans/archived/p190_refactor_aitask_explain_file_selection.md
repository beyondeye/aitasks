---
Task: t190_refactor_aitask_explain_file_selection.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t189 created a reusable `user-file-select` skill with keyword, fuzzy name, and functionality search. Task t190 integrates it into `aitask-explain`'s Step 1 (file selection), replacing the simple free-text path input while keeping existing-run reuse and direct-argument paths unchanged.

## File to Modify

- `.claude/skills/aitask-explain/SKILL.md` — Step 1 only

## Reference

- `.claude/skills/user-file-select/SKILL.md` — the skill to integrate

## Changes

### 1. Remove the Note at the top of Step 1

Delete the `> **Note:** File selection is kept simple here...` block.

### 2. Rewrite "no arguments + existing runs" flow

Replace the current 2-option AskUserQuestion with 3 options:
- "Use existing analysis" (unchanged — reuse a previous run)
- "Search for files" (NEW — description: "Find files by keywords, names, or functionality")
- "Enter paths directly" (description: "Type file/directory paths manually")

### 3. Rewrite "no arguments + no existing runs" flow

Replace the current free-text-only AskUserQuestion with 2 options:
- "Search for files" (description: "Find files by keywords, names, or functionality")
- "Enter paths directly" (description: "Type file/directory paths manually")

### 4. Rewrite "Specify new files" handling

Remove the old "Specify new files" block. Replace with handlers for the two new options:

**If "Search for files":**
- Read and follow `.claude/skills/user-file-select/SKILL.md` to get file paths
- Once file paths are returned, proceed to "Proceed with files" below

**If "Enter paths directly":**
- Use AskUserQuestion with free text ("Other"): "Enter file or directory paths (space-separated):"
- Proceed to "Proceed with files" below

### 5. Keep unchanged

- "invoked with arguments" path — still bypasses file selection
- "Use existing analysis" sub-flow — unchanged
- "Proceed with files" section — unchanged
- Steps 2-6 — unchanged

## Verification

1. Read the modified SKILL.md and verify the flow is coherent
2. Verify "invoked with arguments" path is untouched
3. Verify "Use existing analysis" sub-flow is preserved
4. Verify "Search for files" path references user-file-select correctly
5. Verify "Enter paths directly" keeps the free-text fallback

## Final Implementation Notes
- **Actual work done:** Modified Step 1 of `.claude/skills/aitask-explain/SKILL.md` to integrate the `user-file-select` skill. Removed the outdated Note, replaced "Specify new files" with "Search for files" + "Enter paths directly" options, and added the delegation to `user-file-select/SKILL.md` for the search path.
- **Deviations from plan:** None — all 5 planned changes were applied exactly as specified.
- **Issues encountered:** None.
- **Key decisions:** Kept both flows (existing runs / no runs) consistent by offering "Search for files" and "Enter paths directly" in both, with "Use existing analysis" only appearing when runs exist.

## Post-Implementation

- Step 9: Archive task and plan
