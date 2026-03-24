---
priority: medium
effort: medium
depends: [t448_3]
issue_type: feature
status: Implementing
labels: [aitask_board, task-archive]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-24 09:00
updated_at: 2026-03-24 12:31
---

## Context

This is child task 4 of t448 (Completed Tasks History View in Codebrowser). It creates the HistoryScreen that composes the left pane (t448_2) and detail pane (t448_3) into a full screen, and integrates it into CodeBrowserApp with the `h` keybinding.

Depends on t448_2 (left pane) and t448_3 (detail widget).

## Key Files to Create/Modify
- Create: `.aitask-scripts/codebrowser/history_screen.py`
- Modify: `.aitask-scripts/codebrowser/codebrowser_app.py` — add `h` binding, `action_toggle_history`, import

## Reference Files
- `.aitask-scripts/codebrowser/codebrowser_app.py` — existing app with BINDINGS, compose(), screen patterns
- `.aitask-scripts/codebrowser/history_list.py` — left pane from t448_2
- `.aitask-scripts/codebrowser/history_detail.py` — detail pane from t448_3
- `.aitask-scripts/codebrowser/history_data.py` — data layer from t448_1

## Implementation

### HistoryScreen(Screen)

```python
class HistoryScreen(Screen):
    BINDINGS = [
        Binding("h", "dismiss_screen", "Back to browser"),
        Binding("escape", "dismiss_screen", "Back to browser"),
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_focus", "Toggle Focus"),
    ]
```

**Composition:**
```python
def compose(self):
    yield Header(show_clock=True)
    with Horizontal():
        yield HistoryLeftPane(id="history_left")   # ~40 cols wide
        yield HistoryDetailPane(id="history_detail") # 1fr
    yield Footer()
```

**CSS (embedded in screen):**
```css
#history_left { width: 40; border-right: thick $primary; }
#history_detail { width: 1fr; }
```

**Data loading:**
- On screen mount (first time): call `load_task_index()` in a `@work` worker thread
- Show a loading indicator while scanning (Textual `LoadingIndicator` or simple "Loading..." static)
- Pass loaded index to the left pane's `set_index()` method
- Cache the index on the screen instance so it persists across screen pushes/pops

**Message wiring:**
- `on(TaskSelected)` from left pane:
  1. Call `detail_pane.show_task(task_id, is_explicit_browse=True)` — loads commits via `@work`
  2. The detail pane posts `HistoryBrowseEvent` which the screen forwards to the left pane's `add_to_history()`
- `on(HistoryBrowseEvent)` from detail pane:
  1. Call `left_pane.recently_opened.add_to_history(task_id)`
- `on(NavigateToFile)` from detail pane:
  1. Store the file path
  2. Call `self.dismiss(result=file_path)` to return to codebrowser with the file

**Tab focus cycling:** Cycle between left pane and detail pane.

### CodeBrowserApp Changes

Add to `BINDINGS`:
```python
Binding("h", "toggle_history", "History"),
```

Add instance variable:
```python
self._history_screen: HistoryScreen | None = None
```

Add action:
```python
def action_toggle_history(self):
    if self._history_screen is None:
        self._history_screen = HistoryScreen()
    self.push_screen(self._history_screen, callback=self._on_history_dismiss)

def _on_history_dismiss(self, result):
    # result is a file path if user selected an affected file, else None
    if result:
        self._open_file_by_path(result)  # implemented in t448_5
```

**State preservation:** The `HistoryScreen` instance is cached in `self._history_screen`. Using `push_screen` preserves the codebrowser's state underneath. The history screen's internal state (loaded index, selected task, recently opened, navigation stack) persists because the same instance is reused.

## Verification

1. Launch `ait codebrowser`
2. Press `h` — history screen appears with loading indicator, then task list
3. Select a task — detail pane shows full info
4. Press `h` or Escape — returns to codebrowser with file still open
5. Press `h` again — returns to history with same state (same task selected, same loaded chunks)
6. Tab cycles focus between left pane and detail pane
7. Footer shows correct keybinding hints
