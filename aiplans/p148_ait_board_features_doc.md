---
Task: t148_ait_board_features_doc.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `ait board` Python TUI (Textual-based kanban board) has a rich set of features — column management, task card navigation, inline metadata editing, git integration, search, child task expansion, and more — but zero documentation. This plan creates a comprehensive markdown documentation file at `docs/board.md` structured as: Tutorial, How-To Guides, and Feature Reference.

## File to Create

- `docs/board.md` — Single comprehensive documentation file

## Source Files Analyzed

- `aiscripts/board/aitask_board.py` (2397 lines) — The entire TUI application
- `aiscripts/aitask_board.sh` — Launcher script

## Document Structure

The document will follow the Diataxis framework sections requested by the task:

### 1. Tutorial (Getting Started)
- Launching the board (`ait board`)
- Prerequisites (Python, textual, pyyaml, linkify-it-py; or `ait setup`)
- Understanding the board layout: columns, task cards, search bar, footer keybindings
- First steps: navigating between columns and tasks with arrow keys
- Opening a task detail dialog (Enter)
- Understanding task card information (priority border colors, effort, labels, status, blocked indicators, modified asterisk, child count)

### 2. How-To Guides
- **How to organize tasks into columns** — Moving tasks between columns (Shift+Left/Right), reordering within a column (Shift+Up/Down)
- **How to customize columns** — Adding/editing/deleting columns via command palette (Ctrl+Backslash) or clicking column headers. Color palette selection.
- **How to edit task metadata** — Opening detail screen, using CycleField (Left/Right to cycle Priority, Effort, Status, Type), saving changes
- **How to search and filter tasks** — Tab to focus search box, type to filter, Esc to return
- **How to commit changes from the board** — Modified file indicator (*), commit single (c) or all (C) modified tasks, commit message dialog
- **How to revert a task** — Revert button in detail screen (git checkout)
- **How to create a new task** — n key to launch ait create
- **How to delete a task** — Delete button in detail screen, confirmation with file list
- **How to work with child tasks** — Expand/collapse (x key), navigating to child/parent tasks via detail screen fields
- **How to navigate task relationships** — Dependencies (Enter on Depends field), Children, Folded Tasks, Folded Into, Parent fields — all navigable
- **How to pick a task for implementation** — Pick button in detail screen (launches claude /aitask-pick)
- **How to reorder columns** — Ctrl+Left/Ctrl+Right to move column position
- **How to use the external editor** — Edit button in detail screen (uses $EDITOR)
- **How to open linked issues** — Enter on Issue field opens in browser

### 3. Feature Reference
- **Keyboard shortcuts** — Complete table of all bindings
- **Task card anatomy** — Each visual element explained
- **Priority color coding** — Red (high), Yellow (medium), Gray (low/normal)
- **Issue platform indicators** — GH (GitHub), GL (GitLab), BB (Bitbucket), Issue (other)
- **Column configuration** — board_config.json format, default columns, column IDs
- **Task metadata fields** — Full list of all frontmatter fields the board reads/writes
- **Modal dialogs reference** — All dialog types
- **Color palette** — 8 colors available for columns
- **Board data fields** — boardcol, boardidx
- **Git integration details** — Modified file detection, commit workflow
- **Configuration files** — board_config.json, task_types.txt
- **Environment variables** — EDITOR, TERMINAL, PYTHON

## Implementation Steps

- [x] Create `docs/board.md` with complete TOC linking to all sections
- [x] Write Tutorial section
- [x] Write How-To Guides section
- [x] Write Feature Reference section
- [x] Include screenshot placeholders

## Verification

- [x] Check that all keyboard shortcuts from BINDINGS are documented
- [x] Check that all modal dialog types are referenced
- [x] Check that all metadata fields are listed
- [x] Verify TOC links match section anchors

## Final Implementation Notes

- **Actual work done:** Created `docs/board.md` (555 lines) covering all features of the `ait board` TUI. Organized into Tutorial (getting started), How-To Guides (14 task-oriented guides), and Feature Reference (keyboard shortcuts, metadata fields, modal dialogs, git integration, configuration).
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Used ASCII art diagram for task card anatomy instead of screenshot. Included `<!-- SCREENSHOT: description -->` placeholders (6 total) for the user to add actual screenshots later.
