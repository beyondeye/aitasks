---
Task: t237_document_board_lock_feature_and_lockbeforepick_workflow.md
Branch: main
Base branch: main
---

# Plan: Document Board Lock/Unlock Feature (t237)

## Context

Task t237 requests documenting the board TUI's lock/unlock controls in the website docs. The lock feature was added in recent commits (t227_3) but the board documentation pages have not been updated. The `ait lock` CLI command is already documented in `commands/lock.md`, so board docs should cross-reference it rather than duplicate CLI details.

## Changes

### File 1: `website/content/docs/board/_index.md`

**1A — Add lock indicator bullet to "Reading a Task Card"**
- After the "Children count" bullet (line 67), before the border color paragraph
- New bullet: `**Lock indicator** — Shows "🔒 user@example.com" if the task is currently locked`
- Link to how-to guide

**1B — Update "Opening Task Details" paragraph**
- Expand to mention lock status display and lock/unlock buttons
- Add cross-reference link to the new lock how-to section

### File 2: `website/content/docs/board/how-to.md`

Three new sections, inserted after "How to Pick a Task for Implementation" (line 203):

**2A — "How to Lock and Unlock Tasks"**
- Important callout: pre-locking is NOT required before `/aitask-pick` — it handles locks automatically
- Locking steps: Enter → Lock button → email dialog → confirm
- Unlocking steps: Enter → Unlock button → force-unlock confirmation if different user
- Visual indicators on cards and in detail dialog

**2B — "How to Pre-Lock a Task for Claude Web Execution"**
- Clarify this is specifically for `/aitask-pickweb` (Web cannot acquire locks)
- Workflow: lock from board → pickweb on Web → merge locally → unlock

**2C — "How to Use Locks for Multi-Agent Coordination"**
- Reserving tasks to signal intent
- Checking who is working on what
- Reiterate: pick skills handle locks automatically

### File 3: `website/content/docs/board/reference.md`

**3A — Update Task Card Anatomy ASCII art** with lock indicator line
**3B — New "Lock Status Display" section** with display/button state tables
**3C — Add Lock Email and Unlock Confirm to Modal Dialogs table**
**3D — Update Task Detail row** to include Lock/Unlock buttons

## Verification
1. Run `cd website && hugo build --gc --minify`
2. Check cross-reference links resolve
3. Verify formatting matches existing patterns

## Final Implementation Notes
- **Actual work done:** All planned changes implemented across 3 files (99 insertions, 2 deletions). Added lock indicator to card anatomy, lock how-to guides, pre-lock workflow guide, multi-agent coordination guide, lock status reference section, and modal dialog entries.
- **Deviations from plan:** Initial `relref` shortcodes used relative paths (`commands/lock`) which failed Hugo build. Fixed to absolute paths (`/docs/commands/lock`) to resolve cross-section references correctly.
- **Issues encountered:** Hugo `relref` shortcodes from `board/` subdirectory cannot resolve sibling directories like `commands/` or `skills/` with relative paths. Must use absolute paths from content root.
- **Key decisions:** Placed prominent callout in "How to Lock and Unlock Tasks" section clarifying that `/aitask-pick` handles locks automatically, aligning with messaging in `commands/lock.md`.
