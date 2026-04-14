---
Task: t549_tab_focusing_bugs_in_browser.md
Base branch: main
---

# t549: Fix tab focusing bugs in codebrowser

## Context

Task 541 added Tab-based focus cycling to the `ait codebrowser` TUI. Three bugs
remain:

1. **Main screen — extra pane in the cycle.** Tab cycles through 4 panes
   (opened-file history, file tree, file content, detail) plus one additional
   widget that should not be focusable (user suspects header/footer or similar).
2. **Main screen — Tab inside opened-files pane moves to next item, not next
   pane.** When the recent-files pane has focus, pressing Tab advances to the
   next `RecentFileItem` child instead of cycling to the next pane.
3. **History screen — detail pane does not appear to receive focus.** When
   tab-cycling through `completed tasks → recently opened → detail`, the detail
   pane either doesn't get focus or focuses the scroll container itself, so
   up/down arrow keys do not move between focusable fields inside it.

Root causes (identified by reading the source):

### Causes 1 & 2 — missing `priority=True` on the main screen's tab binding

`.aitask-scripts/codebrowser/codebrowser_app.py:156`:

```python
Binding("tab", "toggle_focus", "Toggle Focus"),
```

Without `priority=True`, Textual evaluates bindings from the focused widget
outward. The focused widget (or its scroll container) consumes Tab via
Textual's built-in `focus_next`/`focus_previous` behavior before the app-level
`action_toggle_focus` runs. That produces both observable bugs:

- Bug 1: Tab walks every focusable descendant (including scroll containers and
  auto-focusable widgets that aren't one of the 4 panes).
- Bug 2: When focus is inside `RecentFilesList` (a `VerticalScroll` whose
  children are focusable `RecentFileItem` rows), `focus_next` moves between
  siblings inside the list.

The history screen's equivalent binding already uses `priority=True` on
`.aitask-scripts/codebrowser/history_screen.py:32`, which is why it doesn't
suffer from bugs 1 & 2.

### Cause 3 — `detail.focus()` called on a `VerticalScroll` container

Both screens' `action_toggle_focus` call `.focus()` directly on the detail
pane instance (`DetailPane` / `HistoryDetailPane`), which extends
`VerticalScroll`:

- `codebrowser_app.py:815` — `self.query_one("#detail_pane", DetailPane).focus()`
- `history_screen.py:341` — `detail.focus()`

`VerticalScroll` is focusable as a scroll container, so focus lands on the
container itself, not on one of its concrete focusable child widgets
(metadata fields, markdown body, etc.). The container highlights but
up/down arrows have nothing focusable to move between, matching the user's
description on the history screen. The same latent bug exists on the main
screen's detail pane path.

`HistoryDetailPane` already has a `_focus_first_field()` helper
(`history_detail.py:639`) that iterates `self.children` and focuses the first
`can_focus && display` one — the correct pattern. `action_focus_right` on the
history screen (`history_screen.py:351-363`) uses the same inline pattern.
The main screen's `DetailPane` does not have an equivalent helper yet.

## Files to modify

- `.aitask-scripts/codebrowser/codebrowser_app.py`
- `.aitask-scripts/codebrowser/history_screen.py`
- `.aitask-scripts/codebrowser/detail_pane.py`

## Implementation

### 1. Add `priority=True` to the main screen Tab binding

File: `.aitask-scripts/codebrowser/codebrowser_app.py` line 156

```python
Binding("tab", "toggle_focus", "Toggle Focus", priority=True),
```

This mirrors `history_screen.py:32` and ensures `action_toggle_focus` runs
before Textual's default focus-next behavior, fixing bugs 1 and 2.

### 2. Add a `_focus_first_field` helper to `DetailPane`

File: `.aitask-scripts/codebrowser/detail_pane.py` — add a method on
`DetailPane` mirroring `HistoryDetailPane._focus_first_field`:

```python
def _focus_first_field(self) -> bool:
    """Focus the first focusable child widget. Returns True if focused."""
    for child in self.children:
        if child.can_focus and child.display and child.styles.display != "none":
            child.focus()
            return True
    return False
```

Rationale: keeping the helper on the pane class (not a utility elsewhere)
matches the existing pattern on `HistoryDetailPane` and keeps the focus logic
co-located with the widget's compose tree.

### 3. Main screen — focus first focusable child of the detail pane

File: `.aitask-scripts/codebrowser/codebrowser_app.py` — inside
`action_toggle_focus` (line 789), replace the `.focus()` call on the detail
pane with the new helper, falling back to the container only if nothing
focusable exists:

```python
# was: self.query_one("#detail_pane", DetailPane).focus()
detail = self.query_one("#detail_pane", DetailPane)
if not detail._focus_first_field():
    detail.focus()
```

The fallback to `detail.focus()` is defensive — if the detail pane currently
has no focusable children (e.g., placeholder state), at least the container
gets focus so `has_focus_within` on the next Tab press still routes correctly.

### 4. History screen — use `_focus_first_field` for the detail pane

File: `.aitask-scripts/codebrowser/history_screen.py` — inside
`action_toggle_focus` (line 323), replace the `detail.focus()` call at line
341:

```python
if recent_list.has_focus_within:
    if not detail._focus_first_field():
        detail.focus()
    return
```

This directly fixes bug 3 by focusing an actual focusable child widget in
the detail pane, so up/down arrow navigation works as expected.

## Non-goals / things intentionally not changed

- **Do not** add `priority=True` to the history screen's tab binding — it's
  already set.
- **Do not** rewrite `action_focus_right` (which already uses the inline
  iteration pattern). It works and is on the left/right arrow path, not the
  Tab path.
- **Do not** touch `_focus_neighbor` in `file_tree.py` — it handles arrow-key
  navigation between `RecentFileItem` siblings and is not involved in the
  Tab cycle bugs.

## Verification

1. Launch codebrowser in the current tmux session:
   ```bash
   ./ait codebrowser
   ```
2. **Main screen Tab cycle** — with a file open and the detail pane visible
   (press `d` if needed):
   - Press Tab repeatedly. Focus should cycle through exactly 4 panes in this
     order: recent files → file tree → code viewer → detail pane → recent
     files. No other widget (header, footer, scrollbar container, etc.)
     should receive focus in between.
   - Confirm that when the recent files pane has focus, Tab moves to the file
     tree, **not** to the next recent file entry. Up/down arrows should still
     walk between `RecentFileItem` rows via the existing `_focus_neighbor`
     handler.
3. **Main screen without detail pane** — press `d` to hide the detail pane
   and repeat the Tab cycle. Expect 3 panes: recent → tree → code → recent.
4. **History screen** — press `h` to open the history screen, then press Tab
   repeatedly. Focus should cycle: completed tasks → recently opened → detail
   pane. When the detail pane is reached, a concrete field inside it must
   appear focused (highlight visible), and pressing up/down must move between
   focusable fields. Press `h` or Escape to return.
5. **Regression check for existing focus entry points** on the history screen:
   - Left/right arrow keys (`action_focus_left` / `action_focus_right`) still
     work correctly.
   - Escape / `h` still dismiss the history screen.
6. Run `shellcheck` (not needed — only Python files modified) and the
   existing test suite is bash-only, so there are no Python unit tests to
   re-run. Confirm no new imports or syntax errors by letting the codebrowser
   launch cleanly (step 1 above).

## Step 9 — Post-Implementation

- Commit with message: `bug: Fix codebrowser tab focus cycling (t549)`
- Run archive via shared task-workflow Step 9 (`aitask_archive.sh 549`)
- Push via `./ait git push`
