---
Task: t747_up_down_arrow_navigate_in_compare_tab.md
Base branch: main
plan_verified: []
---

# Plan: Up/Down arrow navigation in brainstorm Compare tab

## Context

In `ait brainstorm` TUI's **Compare** tab, after the user selects nodes via `r` and a comparison `DataTable` is built, there is currently no way to navigate between the rows (sections/dimensions) using up/down arrows:

- The compare table is a single `DataTable(id="compare_table")` widget mounted in `#compare_content` (`brainstorm_app.py:3013`).
- After the modal closes, focus typically rests on the **tab bar** (`Tabs`).
- The `tab_to_container` mapping that handles "Down from tab bar focuses first row" (`brainstorm_app.py:1733-1737`) only knows about `tab_dashboard`, `tab_actions`, `tab_status` — Compare is not in it, so Down on the tab bar is a no-op.
- The catch-all "Up on Graph/Compare tab → focus tab bar" handler (`brainstorm_app.py:1769-1775`) only fires when the up event reaches the App (i.e., focus is on the tab bar — already a no-op).
- Even if the user were able to focus the `DataTable`, the default cursor is **cell-level**, which doesn't match the user's mental model of navigating between sections.

User-confirmed behaviors (Q&A above):
1. Up at the **first row** of the compare table should return focus to the tab bar (matches Dashboard's NodeRow pattern).
2. Cursor should be **row-level** (highlights whole row).
3. Compare table should be **auto-focused** when freshly built so the user can start navigating immediately.

## Implementation

**Single file modified:** `.aitask-scripts/brainstorm/brainstorm_app.py`

### Step 1 — Define a `CompareDataTable` subclass

Add a small `DataTable` subclass that overrides `action_cursor_up` to escape back to the tab bar when the cursor is already at row 0. Place it just above `BrainstormApp` (or near other brainstorm-internal widgets such as `OperationRow` / `DimensionRow` defined earlier in the file).

```python
class CompareDataTable(DataTable):
    """DataTable for the Compare tab.

    When the cursor is at row 0 and Up is pressed, focus returns to the
    tab bar (matching the Dashboard's NodeRow escape behavior). Otherwise
    Up moves the row cursor as normal.
    """

    def action_cursor_up(self) -> None:
        if self.cursor_row == 0:
            try:
                tabbed = self.app.query_one(TabbedContent)
                tabbed.query_one(Tabs).focus()
                return
            except Exception:
                pass
        super().action_cursor_up()
```

`Tabs` is already imported (used at `brainstorm_app.py:1731`, `1740`, `1771`, etc.).

### Step 2 — Use `CompareDataTable` with row cursor in `_build_compare_matrix`

Replace the table construction at `brainstorm_app.py:3013`:

```python
# Before
table = DataTable(id="compare_table")

# After
table = CompareDataTable(id="compare_table", cursor_type="row")
```

### Step 3 — Auto-focus the compare table after it is mounted

At the end of `_build_compare_matrix` (`brainstorm_app.py:3060-3061`), schedule focus after the next refresh so the table is fully realized:

```python
container.mount(table)
self._compare_nodes = selected_nodes
self.call_after_refresh(table.focus)
```

`call_after_refresh` is already used elsewhere in this file (e.g. `brainstorm_app.py:3331`).

### Step 4 — Wire "Down from tab bar" to focus the compare table

In the `on_key` handler (`brainstorm_app.py:1729-1743`), add a Compare-tab special case before the existing `tab_to_container` lookup. The compare view is a single `DataTable` widget, not row widgets, so it can't piggyback on `_navigate_rows`.

```python
if event.key == "down":
    tabs_widget = tabbed.query_one(Tabs)
    if self.focused is tabs_widget:
        # Compare tab: single DataTable, focus it directly.
        if tabbed.active == "tab_compare":
            try:
                table = self.query_one("#compare_table", DataTable)
            except Exception:
                table = None
            if table is not None:
                table.focus()
                event.prevent_default()
                event.stop()
                return
        # Existing row-based mapping
        tab_to_container = {
            "tab_dashboard": ("node_list_pane", (NodeRow,)),
            "tab_actions": ("actions_content", (OperationRow,)),
            "tab_status": ("status_content", (GroupRow, AgentStatusRow, StatusLogRow)),
        }
        ...
```

The `try/except` guard handles the case where the user opens the Compare tab before pressing `r` (only the `compare_hint` Label is mounted, no table yet).

### Step 5 — Leave the existing "Up on Graph/Compare tab → focus tabs" handler as-is

The handler at `brainstorm_app.py:1769-1775` already does the right thing for the Graph tab (`tab_dag`) and is a harmless no-op for `tab_compare` once the table consumes Up via its own binding (`CompareDataTable.action_cursor_up`). No change needed.

## Files modified

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - Add `CompareDataTable(DataTable)` subclass (~12 lines, near other widget defs)
  - `_build_compare_matrix`: switch to `CompareDataTable(..., cursor_type="row")` and add `call_after_refresh(table.focus)`
  - `on_key`: add Compare-tab special case in the down-from-tab-bar branch

## Verification

Manual TUI verification (no automated test harness for the brainstorm Textual app):

1. Pick a brainstorm session with at least 2 nodes that have dimensions:
   ```bash
   ./ait brainstorm <task_num>
   ```
2. Switch to the Compare tab (`c`), press `r`, select 2+ nodes, confirm with `c` in the modal.
3. **Auto-focus**: confirm the compare table receives focus immediately and the first row is highlighted (row-cursor style).
4. **Down/Up navigation**: press Down repeatedly — the row cursor moves through each dimension and the similarity-score row at the bottom; press Up to move back up.
5. **Escape to tab bar**: with cursor on the first row, press Up — focus returns to the tab bar (Tab/Shift+Tab cycles tabs as usual).
6. **Re-entry**: press Down on the tab bar with Compare tab active — focus returns to the compare table.
7. **No-table edge case**: switch to Compare tab without pressing `r`. Press Down on the tab bar — no-op (no error). Press `r`, select nodes, navigation works as in steps 3-6.
8. **Other tabs unaffected**: switch through Dashboard / Graph / Actions / Status tabs and confirm their navigation still works.
9. **Other Compare features unaffected**: press `r` again to re-select nodes (modal opens), press `D` to open the Diff viewer.

## Step 9 — Post-Implementation

After review/approval, follow Step 9 of `task-workflow/SKILL.md`:
- Run `./.aitask-scripts/aitask_archive.sh 747`
- `./ait git push`
