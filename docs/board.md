# Kanban Board (`ait board`)

The `ait board` command launches an interactive terminal-based kanban board for managing your tasks visually. Built with [Textual](https://textual.textualize.io/), it provides a full-featured TUI with columns, task cards, inline metadata editing, git integration, and keyboard-driven navigation.

<!-- SCREENSHOT: Full board overview showing multiple columns with task cards -->

## Table of Contents

- [Tutorial](#tutorial)
  - [Prerequisites](#prerequisites)
  - [Launching the Board](#launching-the-board)
  - [Understanding the Layout](#understanding-the-layout)
  - [Navigating the Board](#navigating-the-board)
  - [Reading a Task Card](#reading-a-task-card)
  - [Opening Task Details](#opening-task-details)
- [How-To Guides](#how-to-guides)
  - [How to Organize Tasks into Columns](#how-to-organize-tasks-into-columns)
  - [How to Customize Columns](#how-to-customize-columns)
  - [How to Reorder Columns](#how-to-reorder-columns)
  - [How to Edit Task Metadata](#how-to-edit-task-metadata)
  - [How to Search and Filter Tasks](#how-to-search-and-filter-tasks)
  - [How to Commit Changes from the Board](#how-to-commit-changes-from-the-board)
  - [How to Revert a Task](#how-to-revert-a-task)
  - [How to Create a New Task](#how-to-create-a-new-task)
  - [How to Delete a Task](#how-to-delete-a-task)
  - [How to Work with Child Tasks](#how-to-work-with-child-tasks)
  - [How to Navigate Task Relationships](#how-to-navigate-task-relationships)
  - [How to Pick a Task for Implementation](#how-to-pick-a-task-for-implementation)
  - [How to Use the External Editor](#how-to-use-the-external-editor)
  - [How to Open Linked Issues](#how-to-open-linked-issues)
- [Feature Reference](#feature-reference)
  - [Keyboard Shortcuts](#keyboard-shortcuts)
  - [Task Card Anatomy](#task-card-anatomy)
  - [Priority Color Coding](#priority-color-coding)
  - [Issue Platform Indicators](#issue-platform-indicators)
  - [Column Configuration](#column-configuration)
  - [Color Palette](#color-palette)
  - [Task Metadata Fields](#task-metadata-fields)
  - [Board Data Fields](#board-data-fields)
  - [Modal Dialogs Reference](#modal-dialogs-reference)
  - [Git Integration Details](#git-integration-details)
  - [Configuration Files](#configuration-files)
  - [Environment Variables](#environment-variables)

---

## Tutorial

### Prerequisites

The board requires Python 3 with the following packages:

- `textual` — TUI framework
- `pyyaml` — YAML frontmatter parsing
- `linkify-it-py` — URL detection in markdown rendering

Running `ait setup` installs all dependencies into a shared virtual environment at `~/.aitask/venv/`. If you prefer a manual installation:

```bash
pip install textual pyyaml linkify-it-py
```

### Launching the Board

```bash
ait board
```

The board reads all task files from `aitasks/*.md` and displays them as cards organized into kanban columns. On first launch, it creates a default configuration with three columns: **Now**, **Next Week**, and **Backlog**.

### Understanding the Layout

The board has four main areas from top to bottom:

1. **Header** — Application title bar
2. **Search box** — Text input for filtering tasks (starts unfocused)
3. **Board area** — Horizontally scrollable columns, each containing vertically stacked task cards
4. **Footer** — Dynamic keybinding help that changes based on context

<!-- SCREENSHOT: Annotated board layout showing header, search box, columns, and footer -->

**Columns** are displayed left to right. Each column has:
- A colored header showing the column title and task count (e.g., "Now (5)")
- Task cards stacked vertically below the header

An **Unsorted / Inbox** column appears automatically on the left when there are tasks that haven't been assigned to any column.

### Navigating the Board

All navigation is keyboard-driven:

- **Arrow Up / Down** — Move between task cards within a column
- **Arrow Left / Right** — Jump to the adjacent column (skips empty columns, tries to preserve your vertical position)
- **Tab** — Toggle focus to the search box
- **Escape** — Return focus from the search box to the board, or dismiss an open dialog
- **q** — Quit the application

When you focus a card, it receives a double cyan border to indicate selection. The card also scrolls into view automatically.

### Reading a Task Card

Each task card displays a summary of the task information:

<!-- SCREENSHOT: Close-up of a single task card with annotations -->

From top to bottom, a card shows:

- **Task number and title** — e.g., "t47 playlists support". The number appears in cyan. If the file has uncommitted git changes, an orange asterisk (*) appears after the number.
- **Info line** — Shows effort level (e.g., "💪 medium"), labels (e.g., "🏷️ ui,backend"), and issue platform indicator (e.g., "GH" in blue for GitHub issues).
- **Status line** — Shows either "🚫 blocked" (if the task has unresolved dependencies) or "📋 Ready" (or other status). If assigned, shows "👤 name".
- **Dependency links** — If blocked, shows "🔗 t12, t15" linking to blocking tasks.
- **Folded indicator** — Shows "📎 folded into t42" if this task was merged into another.
- **Children count** — Shows "👶 3 children" for parent tasks with subtasks.

The card's **border color** indicates priority:
- **Red** — High priority
- **Yellow** — Medium priority
- **Gray** — Low or normal priority

### Opening Task Details

Press **Enter** on any focused card to open the task detail dialog. This modal shows the full task metadata and markdown content. See [How to Edit Task Metadata](#how-to-edit-task-metadata) for details on what you can do in this dialog.

---

## How-To Guides

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
3. Enter a column title (e.g., "In Review 🔍")
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
   - **Type:** Loaded from `aitasks/metadata/task_types.txt` (defaults: bug, feature, refactor)
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

---

## Feature Reference

### Keyboard Shortcuts

#### Board Navigation

| Key | Action | Context |
|-----|--------|---------|
| `q` | Quit the application | Global |
| `Tab` | Toggle focus between search box and board | Global |
| `Escape` | Return to board from search / dismiss modal | Global |
| `Up` | Navigate to previous task in column | Board |
| `Down` | Navigate to next task in column | Board |
| `Left` | Navigate to previous column | Board |
| `Right` | Navigate to next column | Board |
| `Enter` | Open task detail dialog | Board (focused card) |
| `r` | Refresh board from disk | Board |

#### Task Operations

| Key | Action | Context |
|-----|--------|---------|
| `Shift+Right` | Move task to next column | Board (parent cards only) |
| `Shift+Left` | Move task to previous column | Board (parent cards only) |
| `Shift+Up` | Swap task with one above | Board (parent cards only) |
| `Shift+Down` | Swap task with one below | Board (parent cards only) |
| `n` | Create a new task | Board |
| `x` | Toggle expand/collapse child tasks | Board (parent or child card) |
| `c` | Commit focused modified task | Board (shown when task is modified) |
| `C` | Commit all modified tasks | Board (shown when any task is modified) |

#### Column Operations

| Key | Action | Context |
|-----|--------|---------|
| `Ctrl+Right` | Move column one position right | Board |
| `Ctrl+Left` | Move column one position left | Board |
| `Ctrl+Backslash` | Open command palette | Global |

#### Modal Navigation

| Key | Action | Context |
|-----|--------|---------|
| `Up` | Focus previous field | Inside modal dialogs |
| `Down` | Focus next field | Inside modal dialogs |
| `Left` | Cycle to previous option | On CycleField |
| `Right` | Cycle to next option | On CycleField |
| `Enter` | Activate focused button / navigate to linked task | Inside modal dialogs |
| `Escape` | Close the dialog | Inside modal dialogs |

### Task Card Anatomy

```
┌─────────────────────────────────┐  ← Border color = priority
│ t47 *  playlists support        │  ← Task number (cyan), * if modified (orange), title (bold)
│ 💪 medium | 🏷️ ui,api | GH     │  ← Effort, labels, issue indicator
│ 🚫 blocked | 👤 alice           │  ← Status/blocked, assigned to
│ 🔗 t12, t15                     │  ← Blocking dependency links
│ 📎 folded into t42              │  ← Folded indicator (if applicable)
│ 👶 3 children                   │  ← Child task count (if parent)
└─────────────────────────────────┘
```

Not all lines are shown on every card — lines only appear when the corresponding data exists.

### Priority Color Coding

| Priority | Border Color |
|----------|-------------|
| High | Red |
| Medium | Yellow |
| Low / Normal | Gray |

The focused card always shows a double cyan border, regardless of priority.

### Issue Platform Indicators

The board detects the issue tracking platform from the URL hostname:

| Platform | Indicator | Color |
|----------|-----------|-------|
| GitHub (`github` in hostname) | GH | Blue |
| GitLab (`gitlab` in hostname) | GL | Orange (#e24329) |
| Bitbucket (`bitbucket` in hostname) | BB | Blue |
| Other | Issue | Blue |

### Column Configuration

Columns are stored in `aitasks/metadata/board_config.json`:

```json
{
  "columns": [
    {"id": "now", "title": "Now ⚡", "color": "#FF5555"},
    {"id": "next", "title": "Next Week 📅", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog 🗄️", "color": "#BD93F9"}
  ],
  "column_order": ["now", "next", "backlog"]
}
```

- **id** — Unique identifier (auto-generated from title on creation)
- **title** — Display name (can include emojis)
- **color** — Hex color code for the column header and border
- **column_order** — Controls left-to-right display order

The "Unsorted / Inbox" column is a special dynamic column (ID: `unordered`) that appears automatically when tasks exist without a `boardcol` assignment.

### Color Palette

When adding or editing a column, you can choose from 8 predefined colors:

| Color | Hex Code | Name |
|-------|----------|------|
| ● | `#FF5555` | Red |
| ● | `#FFB86C` | Orange |
| ● | `#F1FA8C` | Yellow |
| ● | `#50FA7B` | Green |
| ● | `#8BE9FD` | Cyan |
| ● | `#BD93F9` | Purple |
| ● | `#FF79C6` | Pink |
| ● | `#6272A4` | Gray |

### Task Metadata Fields

The board reads and displays the following frontmatter fields from task files:

| Field | Type | Editable from Board | Description |
|-------|------|---------------------|-------------|
| `priority` | string | Yes (cycle) | `low`, `medium`, or `high` |
| `effort` | string | Yes (cycle) | `low`, `medium`, or `high` |
| `status` | string | Yes (cycle) | `Ready`, `Editing`, `Implementing`, `Postponed`, `Done`, `Folded` |
| `issue_type` | string | Yes (cycle) | Loaded from `task_types.txt` (defaults: bug, feature, refactor) |
| `labels` | list | Read-only | Tag list, displayed comma-separated |
| `depends` | list | Read-only* | Task IDs this task depends on. *Can remove stale references. |
| `assigned_to` | string | Read-only | Person assigned to the task |
| `issue` | string | Read-only | URL to external issue tracker |
| `created_at` | string | Read-only | Creation timestamp (YYYY-MM-DD HH:MM) |
| `updated_at` | string | Auto-updated | Updated automatically on save |
| `children_to_implement` | list | Read-only | Child task IDs for parent tasks |
| `folded_tasks` | list | Read-only | Task IDs that were merged into this task |
| `folded_into` | string | Read-only | Task ID this task was folded into |
| `boardcol` | string | Auto-managed | Column ID (set by board operations) |
| `boardidx` | integer | Auto-managed | Sort index within column (set by board operations) |

### Board Data Fields

Two metadata fields are managed internally by the board:

- **`boardcol`** — The column ID where the task is placed (e.g., `"now"`, `"backlog"`, `"unordered"`). Tasks without this field appear in the "Unsorted / Inbox" column.
- **`boardidx`** — The sort index within a column. Lower values appear higher. After any movement operation, indices are normalized to 10, 20, 30, etc.

These fields are always written last in the frontmatter and are updated using a reload-and-save mechanism that prevents overwriting other metadata fields changed externally.

### Modal Dialogs Reference

| Dialog | Trigger | Purpose |
|--------|---------|---------|
| **Task Detail** | `Enter` on card / double-click | View/edit task metadata and content; access Pick, Save, Revert, Edit, Delete, Close buttons |
| **Column Edit** | Command palette "Add/Edit Column" / click column header | Set column title and color |
| **Column Select** | Command palette "Edit/Delete Column" | Pick which column to edit or delete |
| **Delete Column Confirm** | After selecting column to delete | Confirm column deletion; warns about task count |
| **Commit Message** | `c` or `C` key | Enter commit message for modified task(s) |
| **Delete Confirm** | "Delete" button in task detail | Confirm task deletion; lists all files to be removed |
| **Dependency Picker** | `Enter` on Depends field (multiple deps) | Select which dependency to open |
| **Remove Dep Confirm** | `Enter` on missing dependency | Offer to remove stale dependency reference |
| **Child Picker** | `Enter` on Children field (multiple children) | Select which child task to open |
| **Folded Task Picker** | `Enter` on Folded Tasks field (multiple) | Select which folded task to view (read-only) |

### Git Integration Details

**Modified file detection:**

The board queries `git status --porcelain -- aitasks/` on startup and after each refresh to identify modified `.md` files. Modified tasks show an orange asterisk (*) next to their task number.

**Commit workflow:**

1. Selected files are staged with `git add <filepath>`
2. A commit is created with the user-provided message
3. The board refreshes git status after commit

**Revert workflow:**

Runs `git checkout -- <filepath>` to discard local changes and restore the last committed version.

**Delete workflow:**

1. Files are removed with `git rm -f <filepath>` (falls back to `os.remove` for untracked files)
2. Empty child task/plan directories are cleaned up
3. An automatic commit is created: "Delete task t<N> and associated files"

### Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `aitasks/metadata/board_config.json` | JSON | Board column definitions and order |
| `aitasks/metadata/task_types.txt` | Text (one per line) | Valid issue types for the Type cycle field |

Both files are auto-created with defaults if they don't exist.

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EDITOR` | `nano` (Linux/macOS), `notepad` (Windows) | External editor opened by the "Edit" button |
| `TERMINAL` | Auto-detected | Terminal emulator for "New Task" and "Pick" actions |
| `PYTHON` | `python3` | Python interpreter (used by launcher if shared venv is unavailable) |

**Terminal auto-detection order:** `$TERMINAL`, then `x-terminal-emulator`, `xdg-terminal-exec`, `gnome-terminal`, `konsole`, `xfce4-terminal`, `lxterminal`, `mate-terminal`, `xterm`. If none found, the board suspends to run commands in the current terminal.
