---
Task: t425_enter_to_confirm_in_dialogs_with_text_input.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Modal dialogs with single-line text Input fields require clicking the OK button to confirm. Users expect Enter to also confirm, as is standard UX. `GoToLineScreen` in codebrowser already implements this pattern via `on_input_submitted()` — we apply it to all other dialogs.

## Approach

Add an `on_input_submitted` handler to each ModalScreen that delegates to the existing confirm logic. In Textual, pressing Enter on a focused `Input` widget fires `Input.Submitted` — the `on_input_submitted` handler catches this at the screen level.

## Changes

### 1. `.aitask-scripts/board/aitask_board.py`

**LockEmailScreen** (line ~1515): Add `on_input_submitted` that calls `confirm_lock()`:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    self.confirm_lock()
```

**CommitMessageScreen** (line ~2168): Add `on_input_submitted` that calls `do_commit()`:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    self.do_commit()
```

**ColumnEditScreen** (line ~2290): Add `on_input_submitted` that calls `save()`:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    self.save()
```

### 2. `.aitask-scripts/diffviewer/merge_screen.py`

**SaveMergeDialog** (line ~92): Has 2 Input fields (filename + dir). Enter on either should confirm. Add:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    self.on_save()
```

### 3. `.aitask-scripts/settings/settings_app.py`

**ExportScreen** (line ~1126): Add:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    self.do_export()
```

**ImportScreen** (line ~1232): Two-step flow. Step 1 input triggers "Next", step 2 has no Input. Add:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    if self.query_one("#import_step1").display:
        self.do_next()
```

**EditStringScreen** (line ~1344): Add:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    self.do_save()
```

**NewProfileScreen** (line ~1542): Add:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    self.do_create()
```

### 4. No changes needed

- **GoToLineScreen** — already has Enter support
- **EditVerifyBuildScreen** — uses TextArea (multiline), not Input. Enter inserts newline, not confirm.

## Verification

1. Run each TUI manually and test Enter key in each dialog:
   - `python .aitask-scripts/board/aitask_board.py` — test Lock, Commit, Column Edit dialogs
   - `python .aitask-scripts/settings/settings_app.py` — test Export, Import, EditString, NewProfile dialogs
   - Diffviewer merge dialog — test via the brainstorm merge flow
2. Verify Escape still dismisses all dialogs
3. Run shellcheck (no shell files changed, but sanity): N/A — all changes are Python

## Final Implementation Notes
- **Actual work done:** Added `on_input_submitted` handlers to all 8 modal dialogs with single-line Input widgets across 3 files, matching the existing GoToLineScreen pattern exactly.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None. All files compiled cleanly.
- **Key decisions:** For ImportScreen (two-step flow), the handler checks `#import_step1` display state to only trigger on step 1. For SaveMergeDialog with 2 Input fields, a single handler works because Textual's `on_input_submitted` fires for any Input in the screen.
