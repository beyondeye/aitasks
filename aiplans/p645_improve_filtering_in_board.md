---
Task: t645_improve_filtering_in_board.md
Base branch: main
plan_verified: []
---

# Plan: Add issue-type filter view to ait board TUI (t645)

## Context

`ait board` currently has three filter views — All, Git, Impl — exposed via the `ViewSelector` widget at the top of the board (`.aitask-scripts/board/aitask_board.py:577`) and the `a` / `g` / `i` key bindings on the main `KanbanApp` (`.aitask-scripts/board/aitask_board.py:3258-3262`). The user wants a fourth view that filters tasks by `issue_type` (one or more values: `bug`, `feature`, `chore`, `documentation`, `performance`, `refactor`, `style`, `test`, `manual_verification`).

When the new view is activated, a modal dialog opens letting the user multi-select which types to show. The current selection is shown in the filter widget area while the view is active, and is persisted across sessions in user-level settings so re-entering the view restores the previous picks (and is the initial state of the dialog when re-opened).

User's clarifying answers (already captured):

1. First-time activation → open dialog immediately.
2. Confirm with zero types selected → revert to All view (clears the type filter).
3. Pressing the Type shortcut while already in Type mode → re-open the dialog.
4. Display selected types on a separate line below the ViewSelector.

## Approach

All changes are confined to `.aitask-scripts/board/aitask_board.py`. We follow the existing `SelectionList`-based modal pattern from `.aitask-scripts/stats/modals/pane_selector.py:14` (space toggles, Enter saves, Esc cancels — exactly what was requested), the existing `ViewSelector` rendering pattern, and the existing per-mode `_*_visible_set()` filter pattern.

No changes to scripts, tests, configs, or the `seed/` tree are required — `manager.settings` already persists to the gitignored user-level layer via `_USER_KEYS = {"settings"}` (`.aitask-scripts/board/aitask_board.py:40`).

### File to modify

- `.aitask-scripts/board/aitask_board.py`

### Changes

#### 1. Add `IssueTypeFilterScreen` modal (new class, near the other ModalScreens around line 1762)

A `ModalScreen` that mirrors `PaneSelectorModal`:

- `__init__(self, task_types: list[str], initial: list[str])`.
- `compose()` yields a `Container` with id `dep_picker_dialog` (reuse existing CSS), a title Label `"Filter by issue type — space to toggle, Enter to confirm, Esc to cancel"`, a `SelectionList[str]` populated from `task_types` with each item's `initial_state = (value in initial)`, and Save / Cancel buttons.
- `BINDINGS` includes `Binding("escape", "cancel", "Cancel", show=False)`.
- `on_mount()` focuses the SelectionList.
- `on_key()` dismisses with the current selection list when Enter is pressed (Enter is unused by SelectionList itself, which uses space to toggle).
- `action_cancel()` dismisses with `None`.
- `dismiss(value)` returns either `None` (cancel) or a `list[str]` of selected types.

Required imports (extend the existing `from textual.widgets import …` line near the top of the file): add `SelectionList`, plus `from textual.widgets.selection_list import Selection`.

#### 2. Extend `ViewSelector` (`.aitask-scripts/board/aitask_board.py:577`)

- Add a new mode tuple to `MODES`: `("t", "Type", "type")`.
- Update `on_click()` so the `x < N` thresholds account for the extra `" │ t Type"` segment (each `KEY LABEL` segment + ` │ ` divider widens the rendered text by `len(KEY LABEL) + 3`). Replace the hardcoded chain with a small loop that walks `MODES` summing widths and dispatches based on the cumulative offset, so the click-hit math stays correct if more modes are added later.

#### 3. Show the active type list under the selector

In `KanbanApp.compose()` (`.aitask-scripts/board/aitask_board.py:3324`), inside the `view_col` Container, add a third widget after `ViewSelector`:

```python
yield Static("", id="type_filter_summary", classes="type-filter-summary")
```

Add CSS rules near the other `view_col` rules (`.aitask-scripts/board/aitask_board.py:3087`):

```
.type-filter-summary { height: auto; padding: 0 1; color: $text-muted; }
.type-filter-summary.hidden { display: none; }
```

A helper `_refresh_type_filter_summary()` writes `"types: bug, feature"` (sorted, comma-joined) when the type view is active and there is a non-empty selection, otherwise hides the widget by toggling the `hidden` class.

#### 4. Persist the selection in `manager.settings`

Use a single key, `filter_issue_types` (list of strings), inside `manager.settings`. Read it with `self.manager.settings.get("filter_issue_types", [])`; write it with `self.manager.settings["filter_issue_types"] = sorted(...)` followed by `self.manager.save_metadata()`.

This piggybacks on the existing settings round-trip — no schema changes needed because `_USER_KEYS = {"settings"}` already routes `settings` to the user-level layer.

#### 5. Add the `t` binding and `action_view_type` (`.aitask-scripts/board/aitask_board.py:3258`)

Add `Binding("t", "view_type", "Type", show=False)` to the View modes section of `KanbanApp.BINDINGS`.

Add `action_view_type(self)` which:

- Reads the persisted selection: `current = self.manager.settings.get("filter_issue_types", [])`.
- If the active view is already `"type"`, OR the persisted selection is empty (first-time activation): open the dialog (see step 6) before flipping the mode. The mode flip happens inside the dismiss callback once we know the user confirmed.
- Otherwise (already had a saved selection and we are switching INTO type mode for the first time this session): just call `self._set_view_mode("type")` and let `_refresh_type_filter_summary()` show the persisted picks immediately.

Also add `def action_view_type` rendering hooks in `ViewSelector.on_click()` so clicking the "t Type" segment goes through the same entry point (call `self.app.action_view_type()` from the click handler instead of `_set_view_mode("type")` directly, so the dialog-open semantics match keyboard activation).

#### 6. Open-dialog helper

```python
def _open_type_filter_dialog(self):
    types = _load_task_types()
    initial = self.manager.settings.get("filter_issue_types", [])
    def on_dismiss(result):
        if result is None:
            return  # Esc / Cancel — keep current view & selection unchanged
        if not result:
            # Empty confirm → clear the type filter and revert to All
            self.manager.settings["filter_issue_types"] = []
            self.manager.save_metadata()
            self._set_view_mode("all")
            self._refresh_type_filter_summary()
            return
        self.manager.settings["filter_issue_types"] = sorted(result)
        self.manager.save_metadata()
        # If we weren't already in type mode, switch into it
        if self.view_mode != "type":
            self._set_view_mode("type")
        else:
            # Already in type mode — re-apply filter and update the summary line
            self._refresh_type_filter_summary()
            self.apply_filter()
    self.app.push_screen(
        IssueTypeFilterScreen(types, initial),
        on_dismiss,
    )
```

#### 7. Wire the new view into `_set_view_mode` and `apply_filter`

In `_set_view_mode()` (`.aitask-scripts/board/aitask_board.py:3555`):

- After updating `self.view_mode`, refresh the `ViewSelector` and call `_refresh_type_filter_summary()` so the summary line appears/disappears whenever we enter/leave type mode.
- Extend the `placeholders` dict with `"type": "Search tasks filtered by issue type (a to exit Type view)"`.

In `apply_filter()` (`.aitask-scripts/board/aitask_board.py:3487`):

- Add an `elif self.view_mode == "type":` branch that calls `visible_set = self._type_visible_set()`.
- The existing search-filter logic and `card.styles.display = ...` loop work unchanged.

Add `_type_visible_set()`:

```python
def _type_visible_set(self) -> set:
    selected = set(self.manager.settings.get("filter_issue_types", []))
    if not selected:
        return set()  # nothing selected → no tasks; defensively, but the
                      # action handler should keep us out of type mode in
                      # this case (it reverts to All on empty confirm)
    visible = set()
    for filename, task in self.manager.task_datas.items():
        if task.metadata.get('issue_type', 'feature') in selected:
            visible.add(filename)
    for filename, task in self.manager.child_task_datas.items():
        if task.metadata.get('issue_type', 'feature') in selected:
            visible.add(filename)
    return visible
```

The default `'feature'` matches existing behavior at `.aitask-scripts/board/aitask_board.py:2008` and `:2044` for tasks with no explicit `issue_type`.

#### 8. Re-press behavior

`_set_view_mode()` early-returns when the new mode equals the current mode (`.aitask-scripts/board/aitask_board.py:3556-3557`). That is correct for `a/g/i`, but for `t` we want re-press to re-open the dialog. We do NOT change `_set_view_mode`; instead, `action_view_type()` (step 5) opens the dialog before delegating to `_set_view_mode`, so re-press automatically opens the dialog regardless of current mode. This keeps `_set_view_mode`'s contract intact.

## Verification

1. **Launch the board:** `./ait board` (or `python3 .aitask-scripts/board/aitask_board.py`). Initial view should still be All; no regression visible — `a / g / i` keys still work, the new `t Type` segment is visible in the selector and the summary line is hidden.
2. **First activation (no persisted selection):** press `t` → dialog opens immediately. Toggle `bug` and `feature` with space → press Enter → board now shows only those tasks; the line under the selector reads `types: bug, feature`; the selector highlights `t Type`.
3. **Persistence:** quit (`q`) and relaunch the board, then press `t`. The dialog should re-open pre-checked with `bug` and `feature` (because we are re-pressing while in the previously-restored mode? Actually after quit/relaunch the active mode is `all`, so first press should switch into type mode without opening the dialog and immediately show those tasks; press `t` again to confirm the dialog re-opens with `bug` + `feature` pre-checked). Confirm with no changes (Enter) → still shows the same tasks.
4. **Re-press in mode:** while in type mode, press `t` again → dialog re-opens with the current selection pre-checked.
5. **Empty confirm:** press `t`, uncheck everything, press Enter → view reverts to All, summary line hides, persisted selection is now empty. Press `t` again → dialog opens immediately (because persisted selection is empty).
6. **Cancel (Esc):** press `t` from a non-type view, then Esc → view stays unchanged, persisted selection unchanged.
7. **Click hit-test:** click each segment of the selector text (`a All`, `g Git`, `i Impl`, `t Type`) → each switches to the corresponding mode (clicking `t Type` opens the dialog when needed, per the same logic as the keyboard shortcut).
8. **Search interaction:** with type filter active, type a substring in the search box → both filters apply (intersection).
9. **Settings layer:** `cat aitasks/metadata/board_config.local.json` (or wherever `local_path_for(METADATA_FILE)` resolves) should contain `"filter_issue_types": [...]` under `settings`. The tracked `aitasks/metadata/board_config.json` should NOT contain it.
10. **Lint:** `shellcheck` is not relevant (Python). Run `python3 -m py_compile .aitask-scripts/board/aitask_board.py` to catch syntax errors.

## Step 9: Post-Implementation

After implementation, follow the standard archival flow per `.claude/skills/task-workflow/SKILL.md` Step 9. Since `create_worktree: false` (profile `fast`), there is no branch to merge — the standard `aitask_archive.sh 645` invocation handles metadata, file moves, lock release, and commit.
