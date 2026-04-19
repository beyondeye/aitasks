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

Line selection lets you highlight a range of code, which is also used as context when launching Explain (**e**).

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

The annotation data comes from the same [explain pipeline]({{< relref "/docs/skills/aitask-explain" >}}) used by `/aitask-explain`. It runs `git blame` and `git log` to map lines to commits, then resolves commits to aitask IDs. Cached data is stored under `.aitask-explain/codebrowser/` and reused across sessions.

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

### How to Launch Explain from the Browser

The codebrowser integrates directly with the [`/aitask-explain`]({{< relref "/docs/skills/aitask-explain" >}}) workflow for deeper analysis.

1. Open a file and optionally select a line range (using **Shift+Up/Down** or mouse drag)
2. Press **e**
3. The configured code agent launches the explain action for the current file (or the selected line range if lines are selected)
4. A terminal emulator opens automatically. If none is found, the codebrowser suspends and runs in the current terminal
5. After the explain session, return to the codebrowser to continue browsing

This is the recommended workflow for going deeper: use the codebrowser's visual annotations to identify interesting code sections, then press **e** to get a full narrative explanation from your configured agent.

### How to Create a Task from a Selection

Capture a task whose `file_references` frontmatter points at exactly the lines you're looking at:

1. Open a file in the code viewer
2. Optionally select a range (**Shift+Up / Shift+Down** or mouse drag). No selection is fine — the cursor line is used as a fallback
3. Press **n**
4. An `AgentCommandScreen` appears with the title `Create task — <relpath> (lines N-M)` and a pre-filled command `aitask_create.sh --file-ref <relpath>:N-M`
5. Choose **Run** (new terminal) or **Run in tmux** (tmux window). You can also edit the command before running — for example, append `--auto-merge` to fold pending tasks that already reference this file
6. Walk through the interactive create flow as usual. At the top you will see a `Pre-populated file references: <relpath>:N-M` banner

The finalized task file contains `file_references: [<relpath>:N-M]` in its frontmatter. Fallback behavior: no selection produces `path:<cursor_line>`; a single-line selection produces `path:N` (not `path:N-N`). For the full story — including how auto-merge detects and folds overlapping pending tasks — see [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}).

### How to Navigate from Code to Task History

When viewing annotated code, you can jump directly to a specific task in the history screen:

1. Navigate to a line annotated with a task ID
2. Press **H** (capital H) to open the history screen, pre-navigated to that task
3. The history detail pane shows the full task info: commits, affected files, child tasks, etc.
4. Press **h** or **Escape** to return to the code browser

If the detail pane is open, **H** uses its current task. Otherwise, it resolves the task from the annotation at the cursor line. This is the reverse of the existing flow where you press **Enter** on an affected file in history to open it in the browser.

### How to Browse Completed Tasks

The history screen lets you explore all archived tasks that have been completed in the project.

**Opening the history screen:**

1. Press **h** to open the history view
2. The first time, data is loaded from git history (a loading indicator appears briefly)
3. Subsequent opens are instant — data is cached and your previous view state is restored

**Browsing the task list:**

1. The left pane shows completed tasks in reverse-chronological order (most recent first)
2. The **Recently Opened** section at the top shows tasks you've previously viewed (persistent across sessions)
3. Scroll down through the task list to browse
4. At the bottom of each chunk, a "Load more" button fetches the next batch of older tasks
5. Use **Left** arrow to cycle focus between the full task list and the recently opened list

**Viewing task details:**

1. Select a task in the list (click or press **Enter**) to see its full details in the right pane
2. The detail pane shows: issue type, priority, effort, labels, completion date, commits, affected files, and linked issues/PRs
3. Press **v** to toggle between the task description and its implementation plan
4. Use **Up** / **Down** arrows to navigate between focusable fields in the detail pane

**Opening commits, issues, and PRs in the browser:**

1. Use **Right** arrow or **Tab** to focus the detail pane
2. Navigate to a commit link, issue link, or PR link field using **Up** / **Down**
3. Press **Enter** to open it in your default browser

**Navigating to affected files:**

1. In the detail pane, navigate to an affected file field
2. Press **Enter** — the history screen closes and the codebrowser opens that file
3. Press **h** to return to history — your previous position is preserved

**Browsing sibling tasks:**

When viewing a child task (e.g., t448_3), you can browse its sibling tasks:

1. Focus the sibling count field in the detail pane
2. Press **Enter** or **s** to open the sibling picker modal
3. Select a sibling to view its details
4. Press **Escape** to close the picker

**Filtering by labels:**

1. Press **l** to open the label filter dialog
2. Select one or more labels to filter the task list
3. Press **o** to confirm, or **r** to reset (show all tasks)
4. Press **Escape** to cancel without changing the filter

**Returning to the code browser:**

- Press **h** or **Escape** to close the history screen and return to browsing code

### How to Launch QA from the History Screen

You can run QA analysis on any completed task directly from the history screen:

1. Press **h** to open the history screen
2. Select a completed task from the list
3. Press **a** to launch the configured QA agent for that task
4. A terminal opens with the `/aitask-qa` skill pre-loaded for the selected task
5. If no terminal is detected, the codebrowser suspends and runs QA in the current terminal

The QA agent uses the model configured for the `qa` operation in `ait settings` (Agent Defaults tab). By default, this is `claudecode/sonnet4_6`.

### tmux integration

When you run `ait codebrowser` inside tmux, you can jump to any other integrated TUI with a single keystroke via the **TUI switcher**:

1. Press **`j`** to open the TUI switcher dialog.
2. Select the target TUI — Monitor, Minimonitor, Board, Settings, or Brainstorm — or one of the running code agent windows.
3. The switcher either focuses the existing tmux window running that TUI or creates a new window and launches it.

A typical flow is: pick a task on the board, let a code agent implement it, then press **`j`** in the codebrowser to hop to **monitor** and watch the agent, or back to **board** to move the task to the next column once the review is complete.

<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->

The TUI switcher requires a tmux session. If you are not running inside tmux yet, see [Terminal Setup]({{< relref "/docs/installation/terminal-setup" >}}). For the full daily workflow, see [The tmux IDE workflow]({{< relref "/docs/workflows/tmux-ide" >}}).

---

**Next:** [Reference](../reference/) — keybindings, annotation pipeline, and configuration.
