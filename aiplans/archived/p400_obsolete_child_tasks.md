---
Task: t400_obsolete_child_tasks.md
Worktree: (none — working on current branch)
Branch: (none — working on current branch)
Base branch: main
---

# Plan: Delete/Archive for All Tasks from Board

## Context

Child tasks can become obsolete when their functionality is covered by another task, but the board's delete button is completely disabled for child tasks. Additionally, the existing delete flow for parent tasks only offers destructive deletion. This plan adds a unified "Delete/Archive" flow for both parent and child tasks, with dependency checks and a choice between deletion and archival.

## Design Decisions

1. **Unified button label "(D)elete/Archive"** for both parent and child tasks — same button ID, keybinding, and variant.

2. **Unified flow:** When pressed, both parent and child tasks go through: dependency check → confirmation dialog with choice of "Delete" or "Archive as superseded" → execute chosen action.

3. **Reuse `aitask_archive.sh`** with a new `--superseded` flag. The existing archive flow (metadata update, file move, parent update, lock release, commit) is reused — only adds `archived_reason: superseded` to frontmatter.

4. **Dependency checking in the board (Python side):** For parent tasks, check if other tasks list this task in `depends`. For child tasks, check siblings' `depends`.

## Implementation Steps

### Step 1: Extend `aitask_archive.sh` with `--superseded` flag

**File:** `.aitask-scripts/aitask_archive.sh`

1a. Add `SUPERSEDED=false` global variable (line ~31, next to `NO_COMMIT`)

1b. Add `--superseded` to `parse_args()` case statement (line ~73):
```bash
--superseded)
    SUPERSEDED=true
    shift
    ;;
```

1c. Update `show_help()` to document `--superseded`:
```
  --superseded    Mark task as superseded (adds archived_reason: superseded)
```

1d. Modify `archive_metadata_update()` (after the `completed_at` insertion, line ~122) to add `archived_reason: superseded` when the flag is set:
```bash
if [[ "$SUPERSEDED" == true ]]; then
    if ! grep -q "^archived_reason:" "$file_path"; then
        awk '/^status:/{print; print "archived_reason: superseded"; next}1' \
            "$file_path" > "$file_path.tmp" && mv "$file_path.tmp" "$file_path"
    fi
fi
```

### Step 2: Add `DeleteArchiveConfirmScreen` to the board

**File:** `.aitask-scripts/board/aitask_board.py`

Add a new modal screen class near `DeleteConfirmScreen` (after line ~1233). This replaces the existing `DeleteConfirmScreen` usage for the unified flow:

```python
class DeleteArchiveConfirmScreen(ModalScreen):
    """Confirmation dialog offering Delete or Archive for a task."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_name: str, files_to_delete: list[str],
                 dep_warnings: list[str], related_tasks: list[str],
                 is_child: bool):
        super().__init__()
        self.task_name = task_name
        self.files_to_delete = files_to_delete
        self.dep_warnings = dep_warnings
        self.related_tasks = related_tasks
        self.is_child = is_child

    def compose(self):
        lines = []
        if self.dep_warnings:
            lines.append("Dependency warnings:")
            for w in self.dep_warnings:
                lines.append(f"  ! {w}")
            lines.append("")
        if self.related_tasks:
            label = "Sibling tasks" if self.is_child else "Tasks to review"
            lines.append(f"{label} (check for implicit dependencies):")
            for t in self.related_tasks:
                lines.append(f"  - {t}")
            lines.append("")
        file_list = "\n".join(f"  - {f}" for f in self.files_to_delete)
        lines.append(f"Files affected:\n{file_list}")
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Delete or Archive '{self.task_name}'?\n\n" + "\n".join(lines),
                id="dep_picker_title",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_do_delete")
                yield Button("Archive", variant="warning", id="btn_do_archive")
                yield Button("Cancel", variant="default", id="btn_do_cancel")

    @on(Button.Pressed, "#btn_do_delete")
    def do_delete(self):
        self.dismiss("delete")

    @on(Button.Pressed, "#btn_do_archive")
    def do_archive(self):
        self.dismiss("archive")

    @on(Button.Pressed, "#btn_do_cancel")
    def do_cancel(self):
        self.dismiss("cancel")

    def action_cancel(self):
        self.dismiss("cancel")
```

### Step 3: Rename button to "(D)elete/Archive" and enable for child tasks

**File:** `.aitask-scripts/board/aitask_board.py`

3a. Change initial button creation in `compose()` (lines 1791-1796):
```python
is_child = self.task_data.filepath.parent.name.startswith("t")
can_delete = (not is_done and not is_folded and not self.read_only
              and self.task_data.metadata.get("status", "") != "Implementing")
yield Button("(D)elete/Archive", variant="error", id="btn_delete",
             disabled=not can_delete)
```

Remove the `and not is_child` from the `can_delete` condition.

3b. Update `_update_delete_button()` (lines 1809-1813) — remove `or is_child`:
```python
def _update_delete_button(self):
    status = self._current_values.get("status", "")
    btn_delete = self.query_one("#btn_delete", Button)
    btn_delete.disabled = (status == "Implementing")
```

### Step 4: Change `delete_task()` to use unified dismiss

**File:** `.aitask-scripts/board/aitask_board.py`

The `delete_task()` handler (line ~1864) now always dismisses with `"delete_archive"`:
```python
@on(Button.Pressed, "#btn_delete")
def delete_task(self):
    self.dismiss("delete_archive")
```

### Step 5: Replace `delete` handling in main app with unified flow

**File:** `.aitask-scripts/board/aitask_board.py`

Replace the existing `elif result == "delete":` block (lines 3045-3054) with:

```python
elif result == "delete_archive":
    task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
    is_child = focused.task_data.filepath.parent.name.startswith("t")
    display_names, paths = self._collect_delete_files(focused.task_data)
    dep_warnings, related = self._check_task_dependencies(focused.task_data, is_child)

    def on_action_chosen(action):
        if action == "delete":
            self._execute_delete(task_num, paths, focused.task_data)
        elif action == "archive":
            self._execute_archive(task_num, focused.task_data)
        else:
            self.refresh_board(refocus_filename=focused.task_data.filename)

    self.push_screen(
        DeleteArchiveConfirmScreen(
            focused.task_data.filename, display_names,
            dep_warnings, related, is_child,
        ),
        on_action_chosen,
    )
    return
```

### Step 6: Add unified dependency checking method

**File:** `.aitask-scripts/board/aitask_board.py`

Add `_check_task_dependencies()` method to the main app class (near `_collect_delete_files`):

```python
def _check_task_dependencies(self, task: Task, is_child: bool):
    """Check if other tasks depend on this task.
    Returns (dep_warnings: list[str], related_summaries: list[str])."""
    task_num_str, _ = TaskCard._parse_filename(task.filename)
    dep_warnings = []
    related_summaries = []

    if is_child:
        # Check sibling dependencies
        parent_num = self.manager.get_parent_num_for_child(task)
        siblings = self.manager.get_child_tasks_for_parent(parent_num)
        child_local = task_num_str.split("_")[-1]

        for sib in siblings:
            if sib.filepath == task.filepath:
                continue
            sib_num, _ = TaskCard._parse_filename(sib.filename)
            sib_status = sib.metadata.get("status", "Ready")
            sib_depends = [str(d) for d in sib.metadata.get("depends", [])]
            if child_local in sib_depends:
                dep_warnings.append(
                    f"{sib.filename} ({sib_status}) explicitly depends on this task"
                )
            related_summaries.append(f"{sib.filename} [{sib_status}]")
    else:
        # Check all parent tasks for dependencies on this task number
        task_local = task_num_str.lstrip("t")
        for fname, other in self.manager.task_datas.items():
            if other.filepath == task.filepath:
                continue
            other_num, _ = TaskCard._parse_filename(other.filename)
            other_status = other.metadata.get("status", "Ready")
            other_depends = [str(d) for d in other.metadata.get("depends", [])]
            if task_local in other_depends:
                dep_warnings.append(
                    f"{other.filename} ({other_status}) explicitly depends on this task"
                )

    return dep_warnings, related_summaries
```

### Step 7: Add archive execution method

**File:** `.aitask-scripts/board/aitask_board.py`

Add `_execute_archive()` method (near `_execute_delete`):

```python
def _execute_archive(self, task_num: str, task: Task):
    """Archive a task as superseded via aitask_archive.sh --superseded."""
    try:
        result = subprocess.run(
            ["./.aitask-scripts/aitask_archive.sh", "--superseded", task_num],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            self.notify(f"Archived {task_num} as superseded", severity="information")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            self.notify(f"Archive failed: {error}", severity="error")
    except subprocess.TimeoutExpired:
        self.notify("Archive operation timed out", severity="error")
    except FileNotFoundError:
        self.notify("Archive script not found", severity="error")

    self.manager.load_tasks()
    self.refresh_board()
```

## Files Modified

| File | Change |
|------|--------|
| `.aitask-scripts/aitask_archive.sh` | Add `--superseded` flag, `archived_reason` metadata |
| `.aitask-scripts/board/aitask_board.py` | Unified Delete/Archive flow for parent and child tasks: new confirmation dialog with dep checks, archive execution method |

## Verification

1. Run `shellcheck .aitask-scripts/aitask_archive.sh` — no new warnings
2. Run `python -c "import sys; sys.path.insert(0, '.aitask-scripts/board'); import aitask_board"` — imports without error
3. Manual test: open board with `./ait board`, verify:
   - All tasks (parent and child) show "(D)elete/Archive" button
   - Pressing it shows dep warnings + choice of Delete/Archive/Cancel
   - "Delete" performs existing deletion behavior
   - "Archive" calls `aitask_archive.sh --superseded` and archives the task
4. Run existing tests: `bash tests/test_claim_id.sh`, etc.

## Final Implementation Notes

- **Actual work done:** Implemented unified Delete/Archive flow for all tasks (parent and child) in the board. Extended `aitask_archive.sh` with `--superseded` flag. Added `DeleteArchiveConfirmScreen` dialog with dependency checks, `_check_task_dependencies()`, and `_execute_archive()` to the board.
- **Deviations from plan:**
  - Fixed `_collect_delete_files()` to handle child tasks properly (was incorrectly finding the child task as its own "child" due to filename prefix matching)
  - Dependency check now uses set intersection against multiple format variants (`"1"`, `"t398_1"`, `"398_1"`) since actual task files use full-ID format (`depends: [t398_1]`)
  - Siblings with explicit dependencies are excluded from the implicit review list to avoid duplication
  - Dialog label uses a separate CSS ID (`delarch_label`) for left-alignment instead of reusing the centered `dep_picker_title`
- **Issues encountered:** The `depends` field in child tasks uses full child IDs like `t398_1` rather than bare numbers. Initial implementation only checked bare numbers, causing no explicit dependencies to be detected.
- **Key decisions:** Used set intersection for dependency matching to handle all possible `depends` formats. Used `archived_reason: superseded` frontmatter field (inserted after `status:` line) to distinguish superseded tasks from normally completed ones in the archive.

## Step 9 (Post-Implementation)

After implementation: commit, archive task t400, push.
