---
title: "Feature Reference"
linkTitle: "Reference"
weight: 20
description: "Keyboard shortcuts, configuration, and technical details"
---

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
| `s` | Sync task data with remote | Board |
| `O` | Open board options/settings dialog | Board |

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
│ 🔒 alice@example.com            │  ← Lock indicator (if locked)
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
    {"id": "now", "title": "Now", "color": "#FF5555"},
    {"id": "next", "title": "Next Week", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog", "color": "#BD93F9"}
  ],
  "column_order": ["now", "next", "backlog"],
  "settings": {
    "auto_refresh_minutes": 5,
    "sync_on_refresh": false
  }
}
```

- **id** — Unique identifier (auto-generated from title on creation)
- **title** — Display name (can include emojis)
- **color** — Hex color code for the column header and border
- **column_order** — Controls left-to-right display order
- **settings.auto_refresh_minutes** — Interval in minutes for periodic board refresh (0 to disable, default 5)
- **settings.sync_on_refresh** — Enable automatic sync with remote on each auto-refresh interval (default false). Requires `.aitask-data` worktree (data branch mode). When enabled, the board subtitle shows "+ sync"

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
| `issue_type` | string | Yes (cycle) | Loaded from `task_types.txt` (defaults: bug, chore, documentation, feature, performance, refactor, style, test) |
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

### Lock Status Display

Lock information is not stored in task files -- it is fetched from the remote `aitask-locks` branch via `aitask_lock.sh --list` and maintained in memory as a lock map. The board refreshes the lock map on startup, on every manual/auto refresh, and after lock/unlock operations.

| Display Location | Locked | Unlocked |
|------------------|--------|----------|
| **Task card** | `🔒 user@example.com` (additional line) | No lock line shown |
| **Task detail** | `🔒 Locked: user@co on hostname since timestamp` | `🔓 Lock: Unlocked` (dimmed) |

Locks older than 24 hours show a `(may be stale)` warning in the detail view.

**Button states in detail dialog:**

| Button | Enabled when | Disabled when |
|--------|-------------|---------------|
| 🔒 Lock | Task is unlocked AND status is not Done/Folded AND not read-only | Task is already locked, or Done/Folded/read-only |
| 🔓 Unlock | Task is locked | Task is not locked |

For details on the underlying lock mechanism, see the [`ait lock` command reference]({{< relref "/docs/commands/lock" >}}).

### Modal Dialogs Reference

| Dialog | Trigger | Purpose |
|--------|---------|---------|
| **Task Detail** | `Enter` on card / double-click | View/edit task metadata, lock status, and content; access Pick, Lock, Unlock, Save, Revert, Edit, Delete, Close buttons |
| **Column Edit** | Command palette "Add/Edit Column" / click column header | Set column title and color |
| **Column Select** | Command palette "Edit/Delete Column" | Pick which column to edit or delete |
| **Delete Column Confirm** | After selecting column to delete | Confirm column deletion; warns about task count |
| **Commit Message** | `c` or `C` key | Enter commit message for modified task(s) |
| **Delete Confirm** | "Delete" button in task detail | Confirm task deletion; lists all files to be removed |
| **Dependency Picker** | `Enter` on Depends field (multiple deps) | Select which dependency to open |
| **Remove Dep Confirm** | `Enter` on missing dependency | Offer to remove stale dependency reference |
| **Child Picker** | `Enter` on Children field (multiple children) | Select which child task to open |
| **Folded Task Picker** | `Enter` on Folded Tasks field (multiple) | Select which folded task to view (read-only) |
| **Lock Email** | "🔒 Lock" button in task detail | Enter email for lock ownership; confirms to acquire lock via `aitask_lock.sh` |
| **Unlock Confirm** | "🔓 Unlock" button (when lock belongs to different user) | Shows lock details (who, where, when); offers "Force Unlock" or "Cancel" |
| **Sync Conflict** | Sync detects merge conflicts | Shows conflicted files; offers "Resolve Interactively" (opens terminal) or "Dismiss" |
| **Settings** | `O` key / command palette "Options" | Configure board settings (auto-refresh interval, sync on refresh) |

### Git Integration Details

The board auto-detects whether task data lives on a separate `aitask-data` branch (via the `.aitask-data/` worktree) or on the current branch (legacy mode). All git operations are routed through a worktree-aware helper, so the board works transparently in both modes.

**Modified file detection:**

The board queries `git status --porcelain -- aitasks/` on startup and after each refresh to identify modified `.md` files. Modified tasks show an orange asterisk (*) next to their task number. In branch mode, this targets the `aitask-data` worktree automatically.

**Commit workflow:**

1. Selected files are staged with `git add <filepath>`
2. A commit is created with the user-provided message
3. The board refreshes git status after commit

In branch mode, commits target the `aitask-data` branch, not the main code branch.

**Revert workflow:**

Runs `git checkout -- <filepath>` to discard local changes and restore the last committed version.

**Delete workflow:**

1. Files are removed with `git rm -f <filepath>` (falls back to `os.remove` for untracked files)
2. Empty child task/plan directories are cleaned up
3. An automatic commit is created: "Delete task t<N> and associated files"

### Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `aitasks/metadata/board_config.json` | JSON | Board column definitions, order, and settings (auto-refresh) |
| `aitasks/metadata/task_types.txt` | Text (one per line) | Valid issue types for the Type cycle field |

Both files are auto-created with defaults if they don't exist.

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EDITOR` | `nano` (Linux/macOS), `notepad` (Windows) | External editor opened by the "Edit" button |
| `TERMINAL` | Auto-detected | Terminal emulator for "New Task" and "Pick" actions |
| `PYTHON` | `python3` | Python interpreter (used by launcher if shared venv is unavailable) |

**Terminal auto-detection order:** `$TERMINAL`, then `x-terminal-emulator`, `xdg-terminal-exec`, `gnome-terminal`, `konsole`, `xfce4-terminal`, `lxterminal`, `mate-terminal`, `xterm`. If none found, the board suspends to run commands in the current terminal.
