---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board, task-archive]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-24 08:59
updated_at: 2026-03-24 11:57
---

## Context

This is child task 3 of t448 (Completed Tasks History View in Codebrowser). It creates the right-pane detail widget that shows full information for a selected completed task. This task can run in parallel with t448_2 (left pane).

Depends on t448_1 which provides `CompletedTask`, `TaskCommitInfo`, `PlatformInfo` dataclasses and functions like `find_commits_for_task()`, `detect_platform_info()`, `load_task_content()`, `load_plan_content()`, `find_sibling_tasks()`.

## Key Files to Create
- `.aitask-scripts/codebrowser/history_detail.py`

## Reference Files
- `.aitask-scripts/board/aitask_board.py` lines 858-868 (`ReadOnlyField`), lines 1113-1137 (`IssueField`), lines 1139-1164 (`PullRequestField`), lines 1681-2135 (`TaskDetailScreen` with `read_only` mode and `v` plan toggle)
- `.aitask-scripts/codebrowser/detail_pane.py` — existing right-pane pattern in codebrowser
- `.aitask-scripts/codebrowser/history_data.py` — data layer from t448_1

## Implementation

### HistoryDetailPane(VerticalScroll)

The main detail widget. Sections rendered top-to-bottom:

#### 1. Header
- Task number + full name, styled like the board's TaskDetailScreen title

#### 2. Back Button
- Only visible when the navigation stack has >1 entry
- Text: "< Back to t{previous_task_id}"
- Focusable, Enter pops the navigation stack
- Does NOT update the "recently opened" history

#### 3. Metadata Block
- Focusable `ReadOnlyField`-style widgets for: priority, effort, issue_type, labels, commit date
- Follow the board's pattern: `can_focus=True`, focus highlighting via CSS class

#### 4. Commit Links Section
- Header: "Commits"
- For each commit from `find_commits_for_task()`:
  - `CommitLinkField(Static)` — focusable, renders: `[hash_short] commit message (date)`
  - On Enter: construct URL via `PlatformInfo.commit_url_template` and open with `webbrowser.open()`
  - Color: accent for hash, muted for message

#### 5. Children Section (for parent tasks only)
- Header: "Children"
- For each child from `find_child_tasks()`:
  - Focusable field: `t{child_id} - {child_name} [{status}]`
  - On Enter: push child onto navigation stack, load its detail (updates "recently opened")

#### 6. Sibling Tasks Field (for child tasks only)
- Single focusable field: "N siblings" (or "No siblings" if only child)
- On Enter (or keybinding `s`): open `SiblingPickerModal`

#### 7. Affected Files Section
- Header: "Affected Files"
- For each file from the commit's affected_files list:
  - `AffectedFileField(Static)` — focusable, renders file path
  - On Enter: post `NavigateToFile` Textual message with the file path
  - This message will be handled by the screen to navigate to the codebrowser

#### 8. Task/Plan Body
- Textual `Markdown` widget rendering the task description
- Handle `on(Markdown.LinkClicked)` — open URLs in browser via `webbrowser.open()`
- **Toggle button/keybinding `v`**: switches between task file content and plan file content
  - Default: show task content
  - Press `v`: load plan via `load_plan_content()`, display it
  - Press `v` again: switch back to task content
  - If no plan exists, show "No plan file found" message
  - Follow the board's `TaskDetailScreen` pattern (which has identical `v` binding)

### Navigation Stack

The detail pane maintains an internal `_nav_stack: list[str]` of task IDs:
- `show_task(task_id, is_explicit_browse=True)`:
  - Push task_id onto stack
  - Load and render task details
  - If `is_explicit_browse=True`, post `HistoryBrowseEvent(task_id)` message (for the screen to update "recently opened")
- `go_back()`:
  - Pop current from stack
  - Show previous task (with `is_explicit_browse=False`)
- `clear_stack()`:
  - Reset to empty

### SiblingPickerModal(ModalScreen)

A modal dialog for browsing sibling tasks:
- **Layout**: Input field at top (fuzzy search), scrollable list below
- **Input**: Filters siblings by name as user types (case-insensitive substring match)
- **List items**: Same format as main task list items (task number, name, type badge, labels)
- **Keyboard**: Up/Down to navigate, Enter to select, Escape to close
- **On select**: Dismiss modal with selected task_id as result. The detail pane handles this by calling `show_task(task_id, is_explicit_browse=True)`.

### Custom Textual Messages

Define these messages in the module:
- `class NavigateToFile(Message)` — carries `file_path: str`
- `class HistoryBrowseEvent(Message)` — carries `task_id: str` (for updating recently opened)

## Verification

1. Create a minimal test app with mock CompletedTask data
2. Verify all sections render correctly
3. Verify commit links open browser (test with a known archived task)
4. Verify task/plan toggle with `v` keybinding
5. Verify navigation stack: navigate to child, back button appears, press back returns
6. Verify SiblingPickerModal: opens on Enter/s, fuzzy search works, selection updates detail
7. Verify Markdown links are clickable
