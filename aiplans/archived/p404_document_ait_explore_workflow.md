---
Task: t404_document_ait_explore_workflow.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Task t404 asks to better document `/aitask-explore` as a capture mechanism in the website docs. The user discovered that `/aitask-explore` is more useful than expected for idea capture, and wants it referenced in two key pages where users learn about capturing ideas and setting up their terminal.

## Changes

### 1. `website/content/docs/workflows/capturing-ideas.md`

**Line 18 — "1. Capture" step:** Add `/aitask-explore` as an alternative capture method alongside `ait create` and `/aitask-create`.

### 2. `website/content/docs/installation/terminal-setup.md`

- Tab 1 updated to mention supported code agents (Claude Code, Gemini CLI, Codex CLI, OpenCode)
- Added Tab 5 for `/aitask-explore` session
- Added Tab 6+ for running multiple code agents in parallel on different tasks
- Added `/aitask-explore` mention in the "Capture new ideas" bullet

## Verification

1. Hugo build passes with `cd website && hugo build --gc --minify`
2. All links use correct relative paths matching existing conventions

## Post-Review Changes

### Change Request 1 (2026-03-17)
- **Requested by user:** Also add to the tab list multiple tabs with code agents (Claude Code, Gemini CLI, Codex CLI, OpenCode, etc.)
- **Changes made:** Updated Tab 1 to list supported code agents; added Tab 6+ row for parallel multi-agent sessions
- **Files affected:** `website/content/docs/installation/terminal-setup.md`

## Final Implementation Notes
- **Actual work done:** Added `/aitask-explore` references to capturing-ideas workflow page and terminal-setup page. Also expanded tab layout to mention multi-agent parallel sessions per user request.
- **Deviations from plan:** Added Tab 6+ and updated Tab 1 description per user feedback (not in original plan).
- **Issues encountered:** None.
- **Key decisions:** Used existing link format conventions (`../../skills/aitask-explore/` from workflows, `../skills/aitask-explore/` from installation).
