---
priority: medium
effort: medium
depends: ['189']
issue_type: refactor
status: Done
labels: [aitasks, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 09:28
updated_at: 2026-02-22 13:43
completed_at: 2026-02-22 13:43
boardcol: now
boardidx: 30
---

Refactor `aitask-explore` area/file selection (Step 1 in `.claude/skills/aitask-explore/SKILL.md`) to optionally use the new `user-file-select` skill alongside the existing exploration intent flow.

## Context
Task t189 creates a `user-file-select` skill with fuzzy keyword/name/functionality search and ranked selection. The `aitask-explore` skill currently uses a purely intent-based flow in Step 1 (Exploration Setup): the user selects an intent (investigate problem, explore area, scope idea, explore docs) and provides free-text descriptions. Claude then explores iteratively.

Unlike `aitask-explain` (which needs explicit file paths as input), `aitask-explore` is more open-ended — it often starts without knowing which files are relevant. However, the "Explore codebase area" option asks "Which module or directory should we focus on?" via free text, which could benefit from file selection.

## Current State (Step 1 in aitask-explore)
`.claude/skills/aitask-explore/SKILL.md` Step 1:
- AskUserQuestion: "What would you like to explore?"
  - "Investigate a problem" → free text: "Describe the symptom"
  - "Explore codebase area" → free text: "Which module or directory should we focus on?"
  - "Scope an idea" → free text: "Describe the idea briefly"
  - "Explore documentation" → select docs type (project/code/both)

## Required Changes

### Modify `.claude/skills/aitask-explore/SKILL.md` Step 1

Enhance the "Explore codebase area" option to offer file selection:

1. **Keep all four intent options** unchanged in the main AskUserQuestion
2. **Enhance "Explore codebase area" follow-up**: instead of only free text, offer:
   - Use `AskUserQuestion`:
     - Question: "How would you like to specify the area?"
     - Header: "Area"
     - Options:
       - "Search for files" (description: "Find files by keywords, names, or functionality using file search")
       - "Describe the area" (description: "Type a module name, directory, or description")
   - If "Search for files": read and follow `.claude/skills/user-file-select/SKILL.md` to get specific files, then use those as the focus area for exploration
   - If "Describe the area": keep current free-text behavior (unchanged)
3. **Optionally enhance "Scope an idea"**: after the user describes the idea, offer to use file search to narrow down which files might be affected — this is optional and lower priority
4. **Leave other options unchanged**: "Investigate a problem" and "Explore documentation" don't benefit from file selection

### Files to Modify
- `.claude/skills/aitask-explore/SKILL.md` — Step 1 only (the "Explore codebase area" sub-flow)

### Reference Files
- `.claude/skills/user-file-select/SKILL.md` — the skill to integrate (created by t189)
- `.claude/skills/aitask-explore/SKILL.md` — current implementation
- `.claude/skills/aitask-explain/SKILL.md` — reference for how aitask-explain integrates user-file-select (t190)

## Verification
1. Test `/aitask-explore` → "Explore codebase area" → "Search for files" — should invoke user-file-select and use results as focus
2. Test `/aitask-explore` → "Explore codebase area" → "Describe the area" — should work as before (free text)
3. Test other options ("Investigate a problem", "Scope an idea", "Explore documentation") — should be unchanged
4. Verify the exploration loop (Step 2) works correctly with file-selected focus areas
