---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Step-by-step guides for common board operations"
---

### How to Organize Tasks into Columns

**Moving a task to a different column:**

1. Focus the task card using arrow keys
2. Press **Shift+Right** to move it to the next column, or **Shift+Left** to move it to the previous column

The task is appended to the end of the target column. Column order follows the configured order, with "Unsorted / Inbox" on the far left.

**Reordering tasks within a column:**

1. Focus the task card
2. Press **Shift+Up** to swap it with the task above, or **Shift+Down** to swap it with the task below

Task positions are stored in the `boardidx` field of each task file's frontmatter. After any move, indices are automatically normalized to 10, 20, 30, etc. to prevent drift.

> **Note:** Child tasks cannot be moved between columns or reordered — only parent tasks can be repositioned.

### How to Customize Columns

<!-- SCREENSHOT: Column edit dialog with title input and color palette -->

**Adding a new column:**

1. Open the command palette with **Ctrl+Backslash**
2. Select "Add Column"
3. Enter a column title (e.g., "In Review")
4. Click a color swatch to select the column color
5. Click "Save"

A unique column ID is auto-generated from the title (lowercased, non-ASCII stripped, spaces replaced with underscores).

**Editing an existing column:**

- **Option A:** Click the column header directly to open the edit dialog
- **Option B:** Open the command palette (**Ctrl+Backslash**), select "Edit Column", then pick the column to edit

You can change the title and color. The column ID is preserved.

**Deleting a column:**

1. Open the command palette (**Ctrl+Backslash**)
2. Select "Delete Column"
3. Pick the column to delete
4. Confirm the deletion

Any tasks in the deleted column are moved to the "Unsorted / Inbox" column.

### How to Reorder Columns

To change the position of a column on the board:

1. Focus any task card in the column you want to move
2. Press **Ctrl+Right** to move the column one position to the right
3. Press **Ctrl+Left** to move it one position to the left

The "Unsorted / Inbox" column cannot be reordered — it always appears on the far left when it contains tasks.

### How to Edit Task Metadata

<!-- SCREENSHOT: Task detail dialog showing editable cycle fields -->

1. Focus a task card and press **Enter** to open the detail dialog
2. Use **Up/Down** arrows to navigate between fields
3. For editable fields (Priority, Effort, Status, Type), press **Left/Right** arrows to cycle through options:
   - **Priority:** low ↔ medium ↔ high
   - **Effort:** low ↔ medium ↔ high
   - **Status:** Ready → Editing → Implementing → Postponed (cycles)
   - **Type:** Loaded from `aitasks/metadata/task_types.txt` (defaults: bug, chore, documentation, feature, performance, refactor, style, test)
4. When you've made changes, the "Save Changes" button becomes enabled
5. Click "Save Changes" or navigate to it and press Enter

The current option is highlighted with bold reverse text. Arrows (◀ ▶) on either side indicate that you can cycle.

**Important:** The board reloads the task file from disk before saving, then applies only the fields you changed. This prevents overwriting changes made externally (e.g., by Claude Code) to other fields.

> **Note:** Tasks with status "Done" or "Folded" are displayed in read-only mode — the cycle fields are replaced with static text and action buttons are disabled.

### How to Search and Filter Tasks

1. Press **Tab** to focus the search box (or click it)
2. Type your search query — filtering happens in real-time as you type
3. Cards that don't match are hidden; matching cards remain visible
4. Press **Escape** to return focus to the board (the filter stays active)
5. Clear the search box text to show all tasks again

The search is case-insensitive and matches against both the task filename and the entire metadata dictionary. This means you can search by task number (e.g., "t47"), title words, labels, status, assigned person, or any other metadata value.

### How to Commit Changes from the Board

When you edit task metadata from the board, the changes are saved to disk but not committed to git. Modified files are indicated by an orange asterisk (*) next to the task number.

**Committing a single task:**

1. Focus the modified task card (the one with *)
2. Press **c**
3. A commit dialog appears showing the file to commit and a pre-filled message (e.g., "Update t47: playlists support")
4. Edit the commit message if needed
5. Click "Commit"

**Committing all modified tasks at once:**

1. Press **C** (Shift+c) from anywhere on the board
2. The commit dialog shows all modified files and a combined message
3. Click "Commit"

<!-- SCREENSHOT: Commit message dialog -->

> **Note:** The "Commit" and "Commit All" keybindings only appear in the footer when applicable — i.e., when the focused task is modified or when any tasks are modified, respectively.

### How to Revert a Task

If you want to discard changes to a task file and restore it to the last committed version:

1. Open the task detail dialog (**Enter**)
2. Click the "Revert" button

This runs `git checkout -- <filepath>` to restore the file. The button is only enabled when the task has uncommitted modifications. It is disabled for tasks with status "Done" or "Folded".

### How to Create a New Task

Press **n** to create a new task. The board will:

1. Detect an available terminal emulator (checking `$TERMINAL`, then common emulators like `gnome-terminal`, `konsole`, `xterm`, etc.)
2. If a terminal is found, open `ait create` in a new terminal window
3. If no terminal is available, suspend the board and run `ait create` in the current terminal

After creation, the board refreshes automatically to show the new task.

### How to Delete a Task

1. Open the task detail dialog (**Enter**)
2. Click the "Delete" button
3. A confirmation dialog shows all files that will be deleted:
   - The task file itself
   - Associated plan file (if it exists in `aiplans/`)
   - All child task files and their plans (for parent tasks)
4. Click "Delete" to confirm

Deletion performs `git rm` on all listed files and creates an automatic commit. If any task had folded tasks, those folded tasks are unfolded (their status is reset to "Ready" and `folded_into` is cleared).

**Delete is disabled for:**
- Tasks with status "Done", "Folded", or "Implementing"
- Child tasks (must delete the parent instead)
- Read-only views

### How to Work with Child Tasks

Parent tasks can have child subtasks stored in `aitasks/t<N>/`. The board supports expanding and collapsing child tasks inline.

<!-- SCREENSHOT: Expanded parent task showing child tasks with connectors -->

**Expanding children:**

1. Focus a parent task that shows "👶 N children"
2. Press **x** to expand — child task cards appear below the parent, indented with a "↳" connector

**Collapsing children:**

1. Press **x** again on the parent (or on any of its child cards) to collapse

**Navigating children:**

- Use **Up/Down** arrows to move between child cards
- Child cards show the same information as parent cards
- Press **Enter** on a child card to view its full details
- In the child detail dialog, a "Parent" field links back to the parent task

**Restrictions:**

- Child tasks cannot be moved between columns or reordered with Shift+arrows
- Child tasks cannot be deleted individually from the board (delete the parent to remove all)

### How to Navigate Task Relationships

The task detail dialog shows several relationship fields. Each is focusable — use Up/Down to navigate to them, then press **Enter** to follow the link:

| Field | Behavior on Enter |
|-------|-------------------|
| **Depends** | Opens the dependency task's detail dialog. If multiple dependencies exist, shows a picker list. If a dependency is not found (archived), offers to remove the stale reference. |
| **Children** | Opens the child task's detail dialog. If multiple children, shows a picker list. |
| **Parent** | Opens the parent task's detail dialog. |
| **Folded Tasks** | Opens the folded task's detail dialog in **read-only** mode. If multiple, shows a picker list. |
| **Folded Into** | Opens the target task that this task was folded into. |
| **Issue** | Opens the issue URL in your default web browser. |

### How to Pick a Task for Implementation

From the task detail dialog:

1. Click the "Pick" button
2. The board launches `claude /aitask-pick <task_number>` in a terminal emulator (or suspends and runs it in the current terminal if no emulator is found)

This starts the full aitask-pick workflow: assignment, planning, implementation, and archival. The board refreshes after the pick session completes (when running in suspend mode).

The "Pick" button is disabled for tasks with status "Done" or "Folded".

### How to Use the External Editor

To edit a task file in your preferred text editor:

1. Open the task detail dialog (**Enter**)
2. Click the "Edit" button
3. The board suspends and opens the file in your `$EDITOR` (defaults to `nano` on Linux/macOS, `notepad` on Windows)
4. Make your changes, save, and exit the editor
5. The board resumes and reloads the task data

The "Edit" button is disabled for tasks with status "Done" or "Folded".

### How to Open Linked Issues

If a task has an `issue` field in its frontmatter (a URL to a GitHub, GitLab, or Bitbucket issue):

1. Open the task detail dialog (**Enter**)
2. Navigate to the "Issue" field (it shows the URL with "(Enter to open)" hint)
3. Press **Enter** to open the URL in your default web browser

### How to Configure Auto-Refresh

The board can periodically reload task files from disk so that changes made externally (e.g., by an AI agent or on another machine) appear automatically without pressing **r**.

**Opening the settings dialog:**

- Press **O** from the board, or
- Open the command palette (**Ctrl+Backslash**) and select "Options"

**Changing the auto-refresh interval:**

1. In the settings dialog, use **Left/Right** arrows on the "Auto-refresh (min)" field to cycle through the available intervals: **0**, **1**, **2**, **5**, **10**, **15**, **30** minutes
2. Select **0** to disable auto-refresh entirely
3. Click "Save" to apply

Changes take effect immediately — the timer is restarted (or stopped) as soon as you save. The setting is persisted to `aitasks/metadata/board_config.json`, so it survives restarts.

The default interval is **5 minutes**.

> **Note:** Auto-refresh is skipped when a modal dialog is open (e.g., task detail, column editor). The refresh will occur at the next interval after the modal is closed. You can always press **r** to refresh manually at any time.

### How to Sync with Remote

When working across multiple machines, task files can get out of sync. The board integrates with `ait sync` to push local changes and pull remote changes automatically.

**Manual sync:**

1. Press **s** from the board, or open the command palette (**Ctrl+Backslash**) and select "Sync with Remote"
2. A notification appears showing the result: "Synced (pushed N, pulled M)", "Pushed N commits", "Pulled M commits", "Already up-to-date", or an error message

**Enabling auto-sync:**

1. Press **O** to open the options/settings dialog
2. Toggle "Sync on refresh" to **yes**
3. Click "Save"

When enabled, the board runs `ait sync` silently on each auto-refresh interval instead of just reloading from disk. The subtitle bar shows "+ sync" to indicate auto-sync is active.

> **Note:** Auto-sync requires the data branch mode (`.aitask-data` worktree). If task data lives on the main branch (legacy mode), the sync option is not available.

**Handling conflicts:**

If the sync detects merge conflicts (e.g., the same task was edited on two machines), a conflict dialog appears listing the affected files. You have two options:

- **Resolve Interactively** — Opens `ait sync` in a terminal where you can edit each conflicted file in `$EDITOR` and complete the rebase
- **Dismiss** — Closes the dialog without resolving; the conflicts remain for the next sync attempt

**No network:**

If the remote is unreachable (timeout after 10 seconds), the board shows a warning notification and continues working with local data. No partial state is left behind.
