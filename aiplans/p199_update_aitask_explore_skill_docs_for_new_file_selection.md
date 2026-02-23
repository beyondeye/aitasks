---
Task: t199_update_aitask_explore_skill_docs_for_new_file_selection.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t191 integrated the `user-file-select` skill into the `aitask-explore` SKILL.md (the source of truth). However, the website documentation page (`website/content/docs/skills/aitask-explore.md`) was not updated to reflect this change. The "Explore codebase area" option now offers two sub-options ("Search for files" via user-file-select, or "Describe the area" via free text), but the website docs still just say "Understand a module, map its structure and dependencies" without mentioning the file search capability.

## Changes

**File:** `website/content/docs/skills/aitask-explore.md`

1. **Update "Explore codebase area" bullet in Workflow Overview (line 23)** — Add mention that this mode now offers file search via an interactive file-select interface, alongside the original free-text area description.

2. **Add a "File Selection" section** after the "Key Capabilities" section — Brief explanation that the "Explore codebase area" mode provides two ways to specify the target: searching for files (by keyword, name, or functionality) or describing the area in free text. This mirrors how aitask-explain already mentions "search the project using the file-select interface" in its docs.

## Verification

- Run `cd website && hugo build --gc --minify` to verify the site builds without errors
- Visually check the rendered page content is coherent

## Final Implementation Notes
- **Actual work done:** Updated `website/content/docs/skills/aitask-explore.md` with two changes: (1) expanded the "Explore codebase area" bullet in Workflow Overview to mention the file search option, (2) added a new "File Selection" section between Key Capabilities and Folded Tasks describing the three search modes and cross-referencing `/aitask-explain`
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Added cross-reference to `/aitask-explain` since both skills share the same file search interface, mirroring how aitask-explain already references its file selection capability
