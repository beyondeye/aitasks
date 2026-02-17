---
Task: t161_board_docs_cross_reference.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Board Docs Cross-Reference (t161)

## Context

The `docs/board.md` file contains comprehensive board documentation (556 lines, tutorials, how-to guides, feature reference), but no other documentation file links to it. The `ait board` section in `docs/commands.md` doesn't reference it, the README doesn't list it, and `docs/workflows.md` only links to `commands.md#ait-board`. This makes the detailed board docs effectively undiscoverable.

## Changes

### 1. `README.md` — Add board docs to Documentation section and link TUI Board mention

- Add a new bullet for board documentation in the Documentation section
- Update the TUI Board mention to link to the docs

### 2. `docs/commands.md` — Add cross-reference in `ait board` section

- After the description paragraph, add a link to the full board documentation

### 3. `docs/workflows.md` — Add board doc references where board operations are described

- In "Capturing Ideas Fast", update the Organize step to reference board docs
- In "Monitoring While Implementing", add board doc reference to triage tasks bullet

### 4. `docs/task-format.md` — Add board reference in Customizing Task Types

- Update the `ait board` mention to link to the board docs

## Files to Modify

1. `README.md` — lines 43, 142-153
2. `docs/commands.md` — lines 287-301
3. `docs/workflows.md` — lines 30, 137-138
4. `docs/task-format.md` — line 95

## Final Implementation Notes

- **Actual work done:** Added cross-references to `docs/board.md` in all 4 planned files, exactly as planned
- **Deviations from plan:** None — all changes matched the plan
- **Issues encountered:** None
- **Key decisions:** Used relative paths (`board.md`) in docs/ files and `docs/board.md` from README.md root; added board docs as a new bullet in the README Documentation section positioned between Command Reference and Skills

## Step 9: Post-Implementation

Archive task and plan files per the standard workflow.
