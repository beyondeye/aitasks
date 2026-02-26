---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Step-by-step guides for code browser operations"
---

### How to Navigate Files in the Tree

1. Press **Tab** to focus the file tree (if not already focused)
2. Use **Up / Down** arrows to move between files and directories
3. Press **Enter** or click a file to open it in the code viewer
4. Directories expand and collapse as you navigate into them

The tree shows only git-tracked files, automatically excluding `__pycache__`, `node_modules`, and `.git` directories. Dotfiles (like `.gitignore`) are included.

### How to Navigate Code

Once a file is open in the code viewer:

- **Up / Down** arrows move the cursor one line at a time
- **PageUp / PageDown** moves the cursor by one screen height
- **g** opens the go-to-line dialog: type a line number and press **Enter** (or **Escape** to cancel). The dialog shows the valid range (e.g., "Go to line (1-342):")
- **Mouse click** positions the cursor on the clicked line
- **Tab** cycles focus between the file tree, code viewer, and detail pane

### How to Select Lines

Line selection lets you highlight a range of code, which is also used as context when launching Claude Explain (**e**).

**Keyboard selection:**

1. Navigate to the start of the range
2. Hold **Shift** and press **Up** or **Down** to extend the selection
3. The selected range is highlighted and shown in the info bar (e.g., "Sel 10-25")

**Mouse selection:**

1. Click on the starting line
2. Drag up or down to extend the selection
3. Edge scrolling activates when dragging near the top or bottom of the viewer

**Clearing selection:**

- Press **Escape** to clear the selection

### How to View Task Annotations

Annotations show which aitasks contributed to each section of a file. They are generated automatically from git history when you open a file.

**Viewing annotations:**

1. Open any file — the codebrowser checks for cached explain data for the file's directory
2. If no cache exists, data is generated automatically (the info bar shows "(generating...)")
3. Once ready, the annotation gutter appears in the code viewer showing color-coded task IDs per line range

**Toggling annotations:**

- Press **t** to show or hide the annotation gutter

**Refreshing annotations:**

- Press **r** to regenerate explain data for the current file's directory. This is useful after new commits have been made that change the file

**How it works:**

The annotation data comes from the same [explain pipeline]({{< relref "/docs/skills/aitask-explain" >}}) used by `/aitask-explain`. It runs `git blame` and `git log` to map lines to commits, then resolves commits to aitask IDs. Cached data is stored under `aiexplains/codebrowser/` and reused across sessions.

### How to Use the Detail Pane

The detail pane shows the plan or task content for the annotation at your cursor position, giving you immediate context about why that code exists.

**Showing the detail pane:**

1. Press **d** to toggle the detail pane on the right side of the screen
2. Press **D** to toggle between default width (30 columns) and expanded (half screen)

**Reading task context:**

1. Navigate to a line that has an annotation in the gutter
2. The detail pane automatically shows:
   - **Plan content** (if the task has an associated plan file) — header shows "Plan for t\<ID\>"
   - **Task description** (fallback if no plan exists) — header shows "Task t\<ID\>"
3. Move the cursor to a different annotated line to update the pane

**Multi-task selections:**

When your selection spans lines annotated by different tasks, the detail pane shows a summary listing all task IDs in the range instead of a single task's content.

**Placeholder state:**

When no file is selected or the cursor is on a non-annotated line, the pane shows: "Move cursor to an annotated line to see task/plan details."

### How to Launch Claude Explain from the Browser

The codebrowser integrates directly with the [`/aitask-explain`]({{< relref "/docs/skills/aitask-explain" >}}) skill for deeper analysis.

1. Open a file and optionally select a line range (using **Shift+Up/Down** or mouse drag)
2. Press **e**
3. Claude Code launches with `/aitask-explain <file>` (or `/aitask-explain <file>:<start>-<end>` if lines are selected)
4. A terminal emulator opens automatically. If none is found, the codebrowser suspends and runs in the current terminal
5. After the Claude session, return to the codebrowser to continue browsing

This is the recommended workflow for going deeper: use the codebrowser's visual annotations to identify interesting code sections, then press **e** to get a full narrative explanation from Claude.
