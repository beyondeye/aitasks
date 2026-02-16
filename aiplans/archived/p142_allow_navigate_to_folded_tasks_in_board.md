---
Task: t142_allow_navigate_to_folded_tasks_in_board.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The `folded_tasks` metadata field was introduced in the aitask-explore skill. When a new task consolidates existing tasks, the folded task IDs are stored in frontmatter (e.g., `folded_tasks: [138]`). The board's task detail screen currently ignores this field. The goal is to display folded tasks and allow navigating to them in read-only mode (Pick/Delete/Edit/Save disabled, CycleFields shown as read-only).

## File to Modify

- `aiscripts/board/aitask_board.py`

## Implementation Plan

### 1. Normalize `folded_tasks` in `Task.load()` (~line 123)

Add normalization alongside `depends` and `children_to_implement`:

```python
if 'folded_tasks' in self.metadata:
    self.metadata['folded_tasks'] = _normalize_task_ids(self.metadata['folded_tasks'])
```

### 2. Add `read_only` parameter to `TaskDetailScreen.__init__()` (~line 957)

```python
def __init__(self, task: Task, manager: TaskManager = None, read_only: bool = False):
```

Store as `self.read_only = read_only`.

In `compose()`:
- When `read_only` is True, treat it like `is_done` for rendering: show all metadata fields as `ReadOnlyField` instead of `CycleField`
- Disable Pick, Save, Revert, Edit, Delete buttons (same as `is_done` behavior, plus also disable Delete)

Change the button section (~line 1037-1051):
```python
is_done_or_ro = is_done or self.read_only
# ...
yield Button("Pick", ..., disabled=is_done_or_ro)
yield Button("Save Changes", ..., disabled=True)
yield Button("Revert", ..., disabled=is_done_or_ro or not is_modified)
yield Button("Edit", ..., disabled=is_done_or_ro)
# For Delete, also check read_only
can_delete = (not is_done and not self.read_only
              and self.task_data.metadata.get("status", "") != "Implementing"
              and not is_child)
```

Also in `compose()` editable metadata section (~line 977-997): use `is_done_or_ro` instead of `is_done` to show ReadOnlyField instead of CycleField.

### 3. Create `FoldedTasksField` widget (after `ChildrenField`, ~line 691)

Follow the `ChildrenField` pattern (lines 645-691). Key aspects:
- Label: `"Folded Tasks:"`
- Read-only (no removal capability)
- Navigate: single item → open directly with `read_only=True`, multiple items → picker
- Pass `read_only=True` to `TaskDetailScreen` when opening folded tasks

### 4. Create `FoldedTaskPickerItem` and `FoldedTaskPickerScreen` (after `ChildPickerScreen`, ~line 947)

Follow the `ChildPickerItem`/`ChildPickerScreen` pattern (lines 892-947):
- `FoldedTaskPickerItem`: Same as `ChildPickerItem` but passes `read_only=True` to `TaskDetailScreen`
- `FoldedTaskPickerScreen`: Title "Select folded task to open:"
- Reuse existing CSS classes (`dep-item-focused`, `dep_picker_dialog`)

### 5. Add `folded_tasks` to `TaskDetailScreen.compose()` (after children field, ~line 1032)

```python
# Folded tasks field
if meta.get("folded_tasks"):
    folded_ids = meta["folded_tasks"]
    if folded_ids and self.manager:
        yield FoldedTasksField(folded_ids, self.manager, self.task_data,
                              classes="meta-ro")
    elif folded_ids:
        folded_str = ", ".join(str(f) for f in folded_ids)
        yield ReadOnlyField(f"[b]Folded Tasks:[/b] {folded_str}", classes="meta-ro")
```

## Existing Code to Reuse

- `_normalize_task_ids()` — for normalizing folded task IDs (~line 118)
- `TaskManager.find_task_by_id()` — resolves task ID to Task object
- `TaskCard._parse_filename()` — extracts task number and name for display
- `ChildrenField` pattern — template for the new widget
- `ChildPickerItem`/`ChildPickerScreen` — template for picker
- CSS classes: `.meta-ro`, `.ro-focused`, `.dep-item-focused`, `#dep_picker_dialog`

## Verification

1. Run the board: `python aiscripts/board/aitask_board.py`
2. Open task t140 (which has `folded_tasks: [138]`) in detail view
3. Verify "Folded Tasks: t138" is displayed as a focusable field
4. Press Enter on the folded tasks field → opens t138's detail in read-only mode
5. Verify Pick, Delete, Edit buttons are disabled in the read-only detail
6. Verify CycleFields show as read-only labels
7. Press Escape → returns to t140 detail

## Final Implementation Notes

- **Actual work done:** All 5 planned changes implemented exactly as planned in `aiscripts/board/aitask_board.py`
- **Deviations from plan:** Fixed hardcoded `"Done"` in the read-only status display — now shows actual status value from metadata (important for folded tasks that may have non-Done statuses like "Ready")
- **Issues encountered:** None
- **Key decisions:** The `read_only` parameter on `TaskDetailScreen` is a general-purpose mechanism that could be reused by other features needing view-only task display

## Step 9 Reference

Post-implementation: archive task and plan files per task-workflow Step 9.
